"""Small all-target audit replies, preserving strict source-layer quote bindings."""

import copy
import json
from typing import Literal

from pydantic import Field, model_validator

from congressional_globe.bracket_cues import Contract
from congressional_globe.productive_ocr_binding import inverse_quote_support, unique_quote_span
from congressional_globe.productive_ocr_compact import _parse, decode_provider
from congressional_globe.productive_ocr_compact_measurement import (
    ORIGINAL_PROVIDER_SHA,
    load_compact_inputs,
)
from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
from congressional_globe.productive_ocr_reply import _alias_map, _layer, _layer_edits, _targets

REPLY_CONTRACT = "ocr-lean-audit-reply-v1"
PROMPT = (
    "Audit every assigned target against image I1 and the frozen saved proposal. "
    "Return the declared lean audit JSON, one targets record per paragraph alias. "
    "Inspect all words, names, punctuation, printed repetition, genuine hyphens, "
    "unflagged text, software edits and ALL numbers, including plausible/already repaired "
    "digits, dates, years, section/chapter numerals, Roman and written quantities. "
    "Numbers means quantities and numeric references, not counts of words. "
    "Raw OCR and the old proposal may both be wrong; neither overrides the print. "
    "For each source-supported discrepancy or unresolved concern, copy a short unique "
    "verbatim quote from its declared raw/static/saved_proposal layer. Set reading to "
    "what the image supports, or null if unreadable. An empty reading string explicitly "
    "proposes deleting the quoted text; whitespace-only readings are not allowed. "
    "Keep reasons brief and nonblank. Do not list unchanged readings. "
    "Do not invent what the image says, normalize away printed repetition or flag a "
    "correct old repair merely because it differs from raw OCR. "
    "coverage complete means the entire target was inspected, not that it has no errors. "
    "Use partial/unreadable and a reason if any target cannot be fully inspected or "
    "all concerns cannot be reported; do not conceal omissions to fit. "
    "Complete records have null reason and no unresolved null readings. "
    "No patches, corrected paragraphs, separate inspections or repeated checklists. "
    "This is source-bound unreviewed audit evidence, never accepted historical text."
)


class LeanConcern(Contract):
    layer: Literal["raw", "static", "saved_proposal"]
    quote: str = Field(min_length=1, max_length=6000, pattern=r"\S")
    reading: str | None = Field(max_length=6000, pattern=r"^$|\S")
    reason: str = Field(min_length=1, max_length=240, pattern=r"\S")

    @model_validator(mode="after")
    def not_noop(self):
        if not self.quote.strip() or not self.reason.strip() or self.reading == self.quote:
            raise ValueError(
                "concern needs a nonblank quote/reason and a changed or unknown reading"
            )
        return self


class LeanTarget(Contract):
    paragraph_alias: str = Field(pattern=r"^P([1-9]|[12][0-9]|3[0-2])$")
    coverage: Literal["complete", "partial", "unreadable"]
    reason: str | None = Field(min_length=1, max_length=240, pattern=r"\S")
    concerns: list[LeanConcern] = Field(max_length=16)

    @model_validator(mode="after")
    def coherent_coverage(self):
        complete = self.coverage == "complete"
        if (self.reason is None) != complete:
            raise ValueError("complete needs null reason; incomplete needs a reason")
        if complete and any(c.reading is None for c in self.concerns):
            raise ValueError("unresolved reading requires partial or unreadable coverage")
        return self


class LeanAuditReply(Contract):
    contract: Literal["ocr-lean-audit-reply-v1"]
    unit_id: str = Field(min_length=1)
    targets: list[LeanTarget] = Field(min_length=1, max_length=32)


def reply_schema(host):
    aliases = list(_targets(host, "audit_saved_proposal"))
    schema = copy.deepcopy(LeanAuditReply.model_json_schema())
    schema["properties"]["unit_id"] = {"const": host["payload"]["unit_id"]}
    schema["properties"]["targets"].update(minItems=len(aliases), maxItems=len(aliases))
    schema["$defs"]["LeanTarget"]["properties"]["paragraph_alias"]["enum"] = aliases
    return schema


def _quote_binding(concern, target):
    raw = target["raw"]["text"]
    text = _layer(target, concern.layer)
    if concern.layer == "raw":
        start, end = unique_quote_span(raw, concern.quote)
        span = (start, end, start, end)
    else:
        span = inverse_quote_support(raw, text, concern.quote, _layer_edits(target, concern.layer))
    return dict(
        source_id=target["source_id"],
        raw_sha256=target["raw"]["sha256"],
        layer=concern.layer,
        layer_start=span[0],
        layer_end=span[1],
        raw_start=span[2],
        raw_end=span[3],
        raw_support=raw[span[2] : span[3]],
        quote=concern.quote,
        reading=concern.reading,
        reason=concern.reason,
        quality="source positions only; image reading remains unverified AI evidence",
    )


def _target_bindings(record, target):
    keys = [(c.layer, c.quote) for c in record.concerns]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate concern within target")
    return [_quote_binding(c, target) for c in record.concerns]


def validate_reply(raw_reply, host):
    reply = LeanAuditReply.model_validate(_parse(raw_reply))
    targets = _targets(host, "audit_saved_proposal")
    if reply.unit_id != host["payload"]["unit_id"]:
        raise ValueError("lean audit belongs to another unit")
    records = _alias_map(reply.targets, set(targets), "lean audit")
    bindings = {
        alias: _target_bindings(record, targets[alias]) for alias, record in records.items()
    }
    complete = all(r.coverage == "complete" for r in reply.targets)
    return dict(
        proposal_status=_outcome(complete, bindings),
        provider_reply=reply.model_dump(mode="json"),
        source_bindings=bindings,
        inspection_quality="coverage is a model claim, not independent accuracy evidence",
    )


def _outcome(complete, bindings):
    if not complete:
        return "unresolved"
    return "findings" if any(bindings.values()) else "no_finding"


def load_lean_inputs(repository):
    host, original, registry = load_compact_inputs(repository)
    body = json.loads(original.body_utf8)
    user = json.loads(body["messages"][1]["content"])
    user["reply_contract"] = REPLY_CONTRACT
    decoder_note = body["messages"][0]["content"].split("\nInput v3 proposal:", 1)[1]
    body["messages"][0]["content"] = PROMPT + "\nInput v3 proposal:" + decoder_note
    body["messages"][1]["content"] = canonical_json(user).decode()
    body["format"] = reply_schema(host)
    wire = canonical_json(body).decode()
    projection = original.model_copy(
        update=dict(
            body_utf8=wire,
            body_sha256=sha256_bytes(wire.encode()),
            prompt_sha256=sha256_bytes(body["messages"][0]["content"].encode()),
            schema_sha256=sha256_bytes(canonical_json(body["format"])),
        )
    )
    from congressional_globe.productive_ocr_measurement_inputs import load_audit_inputs

    _host, source, _registry = load_audit_inputs(repository, "D1")
    provider = json.loads(source.body_utf8)["messages"][1]["content"]
    _verify_source_preservation(original.body_utf8, wire, provider)
    return host, projection, registry


def _verify_source_preservation(original_wire, lean_wire, original_provider):
    before, after = json.loads(original_wire), json.loads(lean_wire)
    restored = json.loads(after["messages"][1]["content"])
    if restored["reply_contract"] != REPLY_CONTRACT:
        raise ValueError("lean reply contract metadata changed")
    restored["reply_contract"] = "ocr-productive-repair-reply-v2"
    if restored != json.loads(before["messages"][1]["content"]):
        raise ValueError("lean request changed original compact source fields")
    _same_request_metadata(before, after)
    decoded = decode_provider(
        canonical_json(restored).decode(), original_provider, ORIGINAL_PROVIDER_SHA
    )
    if decoded != original_provider:
        raise ValueError("lean source does not restore exact independently held original")


def _same_request_metadata(before, after):
    normalized = copy.deepcopy(after)
    normalized["messages"][0]["content"] = before["messages"][0]["content"]
    normalized["messages"][1]["content"] = before["messages"][1]["content"]
    normalized["format"] = before["format"]
    if normalized != before:
        raise ValueError("lean request changed image, role, model/options or unrelated fields")


def export_lean_reply(repository, packet, response, _elapsed):
    host, projection, _registry = load_lean_inputs(repository)
    if packet != {"window_id": "D1A", "host": host, "body_utf8": projection.body_utf8}:
        raise ValueError("lean export does not bind the exact actual request")
    raw = response.get("output_text", "")
    try:
        outcome = validate_reply(raw, host)
    except (ValueError, KeyError, TypeError) as error:
        outcome = "invalid"
        rejection = str(error)[:1000]
    else:
        rejection = None
    return dict(
        outcome=outcome,
        rejection_reason=rejection,
        actual_provider_request_sha256=projection.body_sha256,
        source_context_host_sha256=host["packet_sha256"],
        response_schema_sha256=projection.schema_sha256,
        image_sha256=host["payload"]["image"]["sha256"],
        raw_reply_sha256=sha256_bytes(raw.encode()),
        raw_reply_text=raw,
        acceptance="unreviewed_ai_evidence; no repair/production/native-fit acceptance",
    )
