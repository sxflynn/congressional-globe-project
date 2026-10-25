"""Versioned role-result contract allowing paragraph evidence for unknown roles."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SpeakerRoleV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: str | None
    evidence_ids: list[str]
    target_ids: list[str] = Field(min_length=1)
    role: str
    status: str
    basis: str = Field(min_length=1)

    @model_validator(mode="after")
    def status_relationships(self) -> SpeakerRoleV2:
        if self.status == "proposed" and (self.candidate_id is None or not self.evidence_ids):
            raise ValueError("proposed attribution requires candidate and evidence")
        if self.status == "unknown" and self.candidate_id is not None:
            raise ValueError("unknown attribution cannot name a candidate")
        return self


class RoleResultV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    speaker_roles: list[SpeakerRoleV2]


def role_result_schema() -> dict[str, Any]:
    """Return a generic transport schema; packet-specific aliases are host-checked."""
    common = {
        "type": "object",
        "additionalProperties": False,
        "required": ["candidate_id", "evidence_ids", "target_ids", "role", "status", "basis"],
        "properties": {
            "candidate_id": {"type": ["string", "null"]},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
            "target_ids": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "pattern": "^P[1-9][0-9]*$"},
            },
            "role": {"type": "string", "minLength": 1},
            "status": {"type": "string", "enum": ["proposed", "unknown"]},
            "basis": {"type": "string", "minLength": 1},
        },
    }
    proposed = {
        "allOf": [
            common,
            {
                "properties": {
                    "candidate_id": {"type": "string", "pattern": "^C[1-9][0-9]*$"},
                    "evidence_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "status": {"const": "proposed"},
                }
            },
        ]
    }
    unknown = {
        "allOf": [
            common,
            {
                "properties": {
                    "candidate_id": {"type": "null"},
                    "evidence_ids": {
                        "type": "array",
                        "items": {"type": "string", "pattern": "^P[1-9][0-9]*$"},
                    },
                    "status": {"const": "unknown"},
                }
            },
        ]
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["speaker_roles"],
        "properties": {"speaker_roles": {"type": "array", "items": {"oneOf": [proposed, unknown]}}},
    }


def validate_role_result_v2(result: dict[str, Any], input_packet: dict[str, Any]) -> dict[str, Any]:
    """Validate status semantics and every short alias against the frozen packet."""
    parsed = RoleResultV2.model_validate(result)
    spans = input_packet["spans"]
    paragraphs = _aliases(spans, {"paragraph"})
    cues = _aliases(spans, {"speaker_cue", "person_cue"})
    evidence = paragraphs | _aliases_by_suffix(spans, "cue")
    roles = set(input_packet["controlled_role_ids"])
    statuses = set(input_packet["statuses"])
    for item in parsed.speaker_roles:
        _validate_item(item, roles, statuses, cues, paragraphs, evidence)
    return parsed.model_dump()


def _aliases(spans: list[dict[str, Any]], kinds: set[str]) -> set[str]:
    return {span["id"] for span in spans if span["kind"] in kinds}


def _aliases_by_suffix(spans: list[dict[str, Any]], suffix: str) -> set[str]:
    return {span["id"] for span in spans if span["kind"].endswith(suffix)}


def _validate_item(
    item: SpeakerRoleV2,
    roles: set[str],
    statuses: set[str],
    cues: set[str],
    paragraphs: set[str],
    evidence: set[str],
) -> None:
    if item.role not in roles or item.status not in statuses:
        raise ValueError("role or status is outside the supplied controlled vocabulary")
    if item.candidate_id is not None and item.candidate_id not in cues:
        raise ValueError("candidate_id must reference a supplied speaker/person cue alias")
    _validate_refs(item.target_ids, paragraphs, "target_ids")
    allowed_evidence = paragraphs if item.status == "unknown" else evidence
    _validate_refs(item.evidence_ids, allowed_evidence, "evidence_ids")


def _validate_refs(values: list[str], allowed: set[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must not contain duplicate aliases")
    if not set(values) <= allowed:
        raise ValueError(f"{label} contains an alias of the wrong kind or an unknown alias")
