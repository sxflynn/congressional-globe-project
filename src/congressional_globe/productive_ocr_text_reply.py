"""Lean full-target replies with explicitly coarse, software-derived source support."""

import copy
import json
import re
from typing import Literal

from pydantic import Field, model_validator

from congressional_globe.bracket_cues import BracketSource, Contract, compare_brackets
from congressional_globe.deterministic_models import ExactEdit, replay_with_map
from congressional_globe.productive_ocr_host import sha256_bytes, text_sha256
from congressional_globe.productive_ocr_routing import TEXT_HOST


class TextReading(Contract):
    paragraph_alias: str = Field(pattern=r"^P([1-9]|[12][0-9]|3[0-2])$")
    coverage: Literal["complete", "incomplete"]
    corrected_text: str | None = Field(min_length=1, max_length=6000)
    reason: str | None = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def coherent_uncertainty(self):
        if self.reason is not None and not self.reason.strip():
            raise ValueError("uncertainty reason must contain nonblank text")
        expected = (self.corrected_text is not None, self.reason is None)
        complete = self.coverage == "complete"
        if expected != (complete, complete):
            raise ValueError("complete needs text/no reason; incomplete needs null text/reason")
        return self


class TextReply(Contract):
    contract: Literal["ocr-productive-repair-text-reply-v3"]
    unit_id: str = Field(min_length=1)
    readings: list[TextReading] = Field(min_length=1, max_length=32)


def _targets(host):
    payload = host["payload"]
    if payload["contract"] != TEXT_HOST or payload["role"] != "productive_repair_and_self_check":
        raise ValueError("text reply requires the frozen productive v3 host mode")
    image = payload["image"]
    _require_registered_image(image)
    return {p["alias"]: p for p in payload["paragraphs"] if p["role"] == "target"}


def _check_full_target(text, target, host):
    raw, static = target["raw"]["text"], target["static"]["text"]
    _check_fragments(text, raw, static)
    _check_context(text, target, host)
    _check_feedback_readings(text, target, host)
    _check_brackets(raw, text, target)


def _check_brackets(raw, text, target):
    source = BracketSource(source_id=target["source_id"], raw_text=raw, raw_sha256=text_sha256(raw))
    if compare_brackets(source, text).status != "same_literal_sequence":
        raise ValueError(
            "literal bracket sequence changed or malformed; withhold uncertain reading"
        )


def coarse_proposal(target, text):
    """One paragraph replacement replays insertions too; no token alignment is claimed."""
    raw = target["raw"]["text"]
    edits = (
        ()
        if raw == text
        else (
            ExactEdit(
                start=0,
                end=len(raw),
                raw_quote=raw,
                replacement=text,
                rule_id="software-whole-target-replacement-v3",
            ),
        )
    )
    replay, support = replay_with_map(raw, edits)
    if replay != text:
        raise ValueError("full target replay mismatch")
    return dict(
        paragraph_alias=target["alias"],
        source_id=target["source_id"],
        raw_sha256=target["raw"]["sha256"],
        deterministic_sha256=target["static"]["sha256"],
        text=text,
        sha256=text_sha256(text),
        raw_edits=[e.model_dump(mode="json") for e in edits],
        support_map=[s.model_dump(mode="json") for s in support],
        replay_verified=True,
        alignment="exact_copy" if raw == text else "coarse_whole_paragraph_not_token_alignment",
        acceptance="unreviewed_model_proposal",
        source_quality="not_verified",
    )


def validate_text_reply(raw_reply: str, host: dict) -> dict:
    targets = _targets(host)
    reply = TextReply.model_validate_json(raw_reply)
    _check_reply_scope(reply, host, targets)
    proposals = []
    for reading in reply.readings:
        if reading.corrected_text is not None:
            target = targets[reading.paragraph_alias]
            _check_source_word_boundary(target)
            _check_full_target(reading.corrected_text, target, host)
            proposals.append(coarse_proposal(target, reading.corrected_text))
    complete = len(proposals) == len(targets)
    changed = _changed(proposals, targets)
    return dict(
        proposal_status=_proposal_status(complete, changed),
        derived_proposals=proposals,
        provider_reply=reply.model_dump(mode="json"),
        inspection_quality="coverage_is_model_report_not_independent_proof; print_unverified",
    )


def _check_source_word_boundary(target):
    """Withhold complete readings for a conservative unresolved word-ending signal.

    This does not establish the missing letters or repair a source boundary. A rare
    legitimate terminal word-hyphen may need review; nonhyphen truncation is not detected.
    """
    if re.search(r"[^\W\d_]+-\s*$", target["raw"]["text"]):
        raise ValueError(
            "assigned target may end in a cut-off word; return incomplete coverage "
            "with null text and a reason"
        )


def _proposal_status(complete, changed):
    if not complete:
        return "unresolved"
    return "findings" if changed else "no_finding"


class TextHostExport(Contract):
    contract: Literal["source-bound-productive-ocr-text-v3"] = "source-bound-productive-ocr-text-v3"
    host_packet_sha256: str
    provider_request_sha256: str
    raw_reply_sha256: str
    raw_reply_text: str
    image_sha256: str
    model_digest: str
    source_layers_sha256: str
    response_schema_sha256: str
    diagnostics_sha256: str
    outcome: dict
    acceptance: Literal["unreviewed_ai_evidence"] = "unreviewed_ai_evidence"


class ScopedTextHostExport(TextHostExport):
    boundary_scope: dict
    boundary_check: Literal["visible_context_exclusion_not_full_source_fidelity"] = (
        "visible_context_exclusion_not_full_source_fidelity"
    )


def export_text_reply(host, request_body_utf8, raw_reply_text) -> TextHostExport:
    from congressional_globe.productive_ocr_export import _verify_request_body
    from congressional_globe.productive_ocr_host import canonical_json
    from congressional_globe.productive_ocr_projection import source_layers_identity

    payload = host["payload"]
    _verify_request_body(host, request_body_utf8, payload["response_schema_sha256"])
    outcome = validate_text_reply(raw_reply_text, host)
    exported = TextHostExport(
        host_packet_sha256=host["packet_sha256"],
        provider_request_sha256=text_sha256(request_body_utf8),
        raw_reply_sha256=text_sha256(raw_reply_text),
        raw_reply_text=raw_reply_text,
        image_sha256=payload["image"]["sha256"],
        model_digest=payload["model_digest"],
        source_layers_sha256=source_layers_identity(payload),
        response_schema_sha256=payload["response_schema_sha256"],
        diagnostics_sha256=sha256_bytes(canonical_json(payload["diagnostics"])),
        outcome=outcome,
    )
    scope = payload["image"].get("scope")
    if scope is not None:
        return ScopedTextHostExport(**exported.model_dump(), boundary_scope=scope)
    return exported


def text_reply_schema(payload, *, conformance_v4: bool = False):
    schema = TextReply.model_json_schema()
    schema["properties"]["unit_id"] = {"const": payload["unit_id"]}
    aliases = [p["alias"] for p in payload["paragraphs"] if p["role"] == "target"]
    schema["$defs"]["TextReading"]["properties"]["paragraph_alias"]["enum"] = aliases
    schema["properties"]["readings"].update(minItems=len(aliases), maxItems=len(aliases))
    if conformance_v4:
        _specialize_reading(schema)
    return json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _specialize_reading(schema):
    definition = schema["$defs"]["TextReading"]
    complete = copy.deepcopy(definition)
    complete["properties"].update(
        coverage={"const": "complete"},
        corrected_text={"type": "string", "minLength": 1, "maxLength": 6000},
        reason={"type": "null"},
    )
    incomplete = copy.deepcopy(definition)
    incomplete["properties"].update(
        coverage={"const": "incomplete"},
        corrected_text={"type": "null"},
        reason={"type": "string", "minLength": 1, "maxLength": 1000},
    )
    schema["$defs"]["TextReading"] = {"oneOf": [complete, incomplete]}


def _require_registered_image(image):
    if image is None:
        raise ValueError("text inspection requires a registered source image")
    if (image["registration_status"], image["legibility_status"]) != ("verified", "checked"):
        raise ValueError("text inspection requires checked image evidence")


def _check_fragments(text, raw, static):
    if text not in (raw, static):
        _reject_substring(text, raw, static)
    if len(re.findall(r"\w+", text)) == 1 and len(re.findall(r"\w+", raw)) > 1:
        raise ValueError("word fragment is not a complete paragraph")


def _reject_substring(text, raw, static):
    if text in raw or text in static:
        raise ValueError("proper fragment is not a complete target reading")


def _check_context(text, target, host):
    contexts = [p["raw"]["text"] for p in host["payload"]["paragraphs"] if p["role"] == "context"]
    for context in contexts:
        allowed = max(target["raw"]["text"].count(context), target["static"]["text"].count(context))
        if text.count(context) > allowed:
            raise ValueError("context text cannot be included in a target reading")
    from congressional_globe.productive_ocr_scope import reject_context_copy

    reject_context_copy(text, target, host["payload"]["image"].get("scope", {}))


def _check_reply_scope(reply, host, targets):
    aliases = [r.paragraph_alias for r in reply.readings]
    if reply.unit_id != host["payload"]["unit_id"]:
        raise ValueError("text reply belongs to another unit")
    if len(set(aliases)) != len(aliases) or set(aliases) != set(targets):
        raise ValueError("reply must cover exactly every assigned target once")


def _changed(proposals, targets):
    return any(p["text"] != targets[p["paragraph_alias"]]["raw"]["text"] for p in proposals)


def _required_readings(host, alias):
    signals = host["payload"]["diagnostics"]["signals"]
    selected = [s for s in signals if s["paragraph_alias"] == alias]
    return [
        (s, flag.removeprefix("required_local_reading:"))
        for s in selected
        for flag in s["flags"]
        if flag.startswith("required_local_reading:")
    ]


def _check_feedback_readings(text, target, host):
    for signal, expected in _required_readings(host, target["alias"]):
        _check_local_feedback(text, target["raw"]["text"], signal, expected)


def _check_local_feedback(text, raw, signal, expected):
    # Conservative literal context guard, not a unique token alignment or image judgment.
    low, high = signal["raw_start"], signal["raw_end"]
    prefix = raw[max(0, low - 24) : low]
    suffix = raw[high : high + 24]
    original = prefix + signal["raw_quote"] + suffix
    corrected = prefix + expected + suffix
    if raw.count(original) != 1 or text.count(corrected) != 1:
        raise ValueError("named human feedback lacks unique local context; withhold reading")
    if original != corrected and original in text:
        raise ValueError("named human feedback retains the damaged local reading")
