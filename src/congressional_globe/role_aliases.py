"""Validate frozen span inputs and prepare short, request-local role aliases."""

from __future__ import annotations

import hashlib
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenSpan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    span_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    text: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    source_paragraph_id: str = Field(min_length=1)
    cue_origin: str | None


class FrozenInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: str
    offset_convention: str
    window_id: str = Field(min_length=1)
    source_anchor: dict[str, Any]
    raw_text: str
    raw_sha256: str
    spans: list[FrozenSpan]
    controlled_topic_ids: list[str]
    controlled_role_ids: list[str]
    statuses: list[str]

    @model_validator(mode="after")
    def verify_frozen_content(self) -> FrozenInput:
        if self.schema_version != "span-selection-input-v1":
            raise ValueError("unsupported input schema_version")
        if self.offset_convention != "unicode_codepoints_half_open":
            raise ValueError("unsupported offset convention")
        digest = hashlib.sha256(self.raw_text.encode("utf-8")).hexdigest()
        if self.raw_sha256 != digest:
            raise ValueError("raw_sha256 does not match raw_text")
        _validate_spans(self.raw_text, self.spans)
        return self


def _validate_spans(raw_text: str, spans: list[FrozenSpan]) -> None:
    ids = [span.span_id for span in spans]
    if len(ids) != len(set(ids)):
        raise ValueError("span_id values must be unique")
    for span in spans:
        _validate_span(raw_text, span)


def _validate_span(raw_text: str, span: FrozenSpan) -> None:
    if span.end < span.start or span.end > len(raw_text):
        raise ValueError("span offsets are outside raw_text")
    if raw_text[span.start : span.end] != span.text:
        raise ValueError("span text does not match raw_text offsets")


def _validate_assignment_status(
    status: str, candidate_id: str | None, evidence_ids: list[str]
) -> None:
    _validate_proposed(status, candidate_id, evidence_ids)
    _validate_unknown(status, candidate_id, evidence_ids)


def _validate_proposed(status: str, candidate_id: str | None, evidence_ids: list[str]) -> None:
    if status == "proposed" and (candidate_id is None or not evidence_ids):
        raise ValueError("proposed attribution requires a candidate and evidence")


def _validate_unknown(status: str, candidate_id: str | None, evidence_ids: list[str]) -> None:
    if status == "unknown" and (candidate_id is not None or evidence_ids):
        raise ValueError("unknown role attribution must have null candidate and no evidence IDs")


def prepare_aliases(row: dict[str, Any]) -> dict[str, Any]:
    """Return a short role packet and a reversible host-only alias map."""
    source = FrozenInput.model_validate(row)
    counters = {"paragraph": 0, "cue": 0}
    short_spans: list[dict[str, Any]] = []
    alias_map: dict[str, dict[str, Any]] = {}
    for span in source.spans:
        if span.kind == "paragraph":
            prefix, category = "P", "paragraph"
        else:
            prefix, category = "C", "cue"
        counters[category] += 1
        alias = f"{prefix}{counters[category]}"
        short_spans.append(
            {
                "id": alias,
                "kind": span.kind,
                "text": span.text,
                "start": span.start,
                "end": span.end,
            }
        )
        alias_map[alias] = {
            "span": span.model_dump(),
            "source_anchor": source.source_anchor,
            "raw_sha256": source.raw_sha256,
        }
    packet = {
        "window_id": source.window_id,
        "raw_text": source.raw_text,
        "spans": short_spans,
        "controlled_role_ids": source.controlled_role_ids,
        "statuses": source.statuses,
    }
    return {"input": packet, "alias_map": alias_map}


class SpeakerRole(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: str | None
    evidence_ids: list[str]
    target_ids: list[str] = Field(min_length=1)
    role: str
    status: str
    basis: str = Field(min_length=1)

    @model_validator(mode="after")
    def status_matches_assignment(self) -> SpeakerRole:
        _validate_assignment_status(self.status, self.candidate_id, self.evidence_ids)
        return self


class RoleResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    speaker_roles: list[SpeakerRole]


def _validate_role_references(
    attribution: SpeakerRole,
    roles: set[str],
    statuses: set[str],
    cues: set[str],
    paragraphs: set[str],
    evidence: set[str],
) -> None:
    if attribution.role not in roles or attribution.status not in statuses:
        raise ValueError("role or status is outside the supplied controlled vocabulary")
    _validate_candidate(attribution.candidate_id, cues)
    _validate_reference_set(attribution.evidence_ids, evidence, "evidence_ids", "paragraph or cue")
    _validate_reference_set(attribution.target_ids, paragraphs, "target_ids", "paragraph")


def _validate_candidate(candidate_id: str | None, cues: set[str]) -> None:
    if candidate_id is not None and candidate_id not in cues:
        raise ValueError("candidate_id must reference a supplied speaker/person cue alias")


def _validate_reference_set(values: list[str], allowed: set[str], label: str, kinds: str) -> None:
    if not set(values) <= allowed:
        raise ValueError(f"{label} must reference supplied {kinds} aliases")


def validate_alias_result(result: dict[str, Any], input_packet: dict[str, Any]) -> dict[str, Any]:
    """Validate result structure, role vocabulary, and request-local cue references."""
    parsed = RoleResult.model_validate(result)
    roles = set(input_packet["controlled_role_ids"])
    statuses = set(input_packet["statuses"])
    spans = input_packet["spans"]
    cues = {span["id"] for span in spans if span["kind"] in {"speaker_cue", "person_cue"}}
    paragraphs = {span["id"] for span in spans if span["kind"] == "paragraph"}
    evidence = paragraphs | {span["id"] for span in spans if span["kind"].endswith("cue")}
    for attribution in parsed.speaker_roles:
        _validate_role_references(attribution, roles, statuses, cues, paragraphs, evidence)
    return parsed.model_dump()


ROLE_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["speaker_roles"],
    "properties": {
        "speaker_roles": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "candidate_id",
                    "evidence_ids",
                    "target_ids",
                    "role",
                    "status",
                    "basis",
                ],
                "properties": {
                    "candidate_id": {"type": ["string", "null"]},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "target_ids": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"},
                    },
                    "role": {"type": "string"},
                    "status": {"type": "string"},
                    "basis": {"type": "string", "minLength": 1},
                },
            },
        }
    },
}
