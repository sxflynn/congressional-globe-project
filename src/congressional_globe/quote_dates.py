"""Versioned exact-quote date replies with separately host-derived coordinates."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from congressional_globe.scoped_dates import (
    Contract,
    DatePacket,
    DateParagraph,
    DateValue,
    source_mapped_dates,
    validate_date_result,
)


class QuoteDateEvidence(Contract):
    paragraph_id: str = Field(min_length=1)
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    quote: str = Field(min_length=1)


class QuoteDateAlternative(Contract):
    value: DateValue
    evidence: list[QuoteDateEvidence] = Field(min_length=1)
    basis: str = Field(min_length=1)


class QuoteDateAssignment(Contract):
    target_ids: list[str] = Field(min_length=1)
    value: DateValue | None
    date_kind: Literal["explicit", "implicit", "none"]
    context_kind: Literal["proceeding", "mentioned", "unknown"]
    status: Literal["proposed", "unknown", "mixed", "needs_review"]
    method: Literal["explicit_text", "scoped_continuation", "no_supported_date"]
    evidence: list[QuoteDateEvidence]
    alternatives: list[QuoteDateAlternative]
    unknowns: list[str]
    basis: str = Field(min_length=1)


class QuoteDateResult(Contract):
    dates: list[QuoteDateAssignment] = Field(min_length=1)


def quote_date_schema() -> dict:
    return QuoteDateResult.model_json_schema()


def _unique_position(text: str, quote: str) -> int:
    start = text.find(quote)
    if start < 0:
        raise ValueError("exact quote not found in declared raw paragraph")
    if text.find(quote, start + 1) >= 0:
        raise ValueError("exact quote is ambiguous in declared raw paragraph")
    return start


def _bind_evidence(evidence: QuoteDateEvidence, paragraphs: dict[str, DateParagraph]) -> dict:
    paragraph = paragraphs.get(evidence.paragraph_id)
    if paragraph is None:
        raise ValueError("unknown quote evidence paragraph")
    if evidence.raw_sha256 != paragraph.raw_sha256:
        raise ValueError("quote evidence raw hash mismatch")
    start = _unique_position(paragraph.raw_text, evidence.quote)
    return {**evidence.model_dump(), "start": start, "end": start + len(evidence.quote)}


def _bind_alternative(item: QuoteDateAlternative, paragraphs: dict[str, DateParagraph]) -> dict:
    return {**item.model_dump(), "evidence": [_bind_evidence(e, paragraphs) for e in item.evidence]}


def _bind_assignment(item: QuoteDateAssignment, paragraphs: dict[str, DateParagraph]) -> dict:
    return {
        **item.model_dump(),
        "evidence": [_bind_evidence(e, paragraphs) for e in item.evidence],
        "alternatives": [_bind_alternative(a, paragraphs) for a in item.alternatives],
    }


def bind_quote_date_result(result: dict, packet: DatePacket | dict) -> dict:
    """Derive coordinates only for the new offset-free contract, then validate v1."""
    source = DatePacket.model_validate(packet)
    proposed = QuoteDateResult.model_validate(result)
    paragraphs = {p.alias: p for p in source.paragraphs}
    derived = {"dates": [_bind_assignment(item, paragraphs) for item in proposed.dates]}
    return validate_date_result(derived, source).model_dump()


def source_mapped_quote_dates(result: dict, packet: DatePacket | dict) -> dict:
    source = DatePacket.model_validate(packet)
    proposed = QuoteDateResult.model_validate(result)
    derived = bind_quote_date_result(proposed.model_dump(), source)
    return {
        **source_mapped_dates(derived, source),
        "schema_version": "source-mapped-scoped-date-quotes-v1",
        "model_contract": "scoped-date-quotes-v1",
        "derived_contract": "scoped-date-v1",
        "coordinate_binding": "host_unique_exact_quote_in_declared_raw_paragraph",
        "model_proposals": proposed.model_dump(),
    }
