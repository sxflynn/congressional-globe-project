"""Source-bound date proposals, with host-declared scope stops and no provider calls."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

_SHA = r"^[0-9a-f]{64}$"
_MONTHS: list[str] = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class DateParagraph(Contract):
    alias: str = Field(min_length=1)
    source_paragraph_id: str = Field(min_length=1)
    item_identifier: str = Field(min_length=1)
    scan_leaf: int = Field(ge=0)
    raw_text: str
    raw_sha256: str = Field(pattern=_SHA)
    region_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def check_hash(self) -> Self:
        if text_hash(self.raw_text) != self.raw_sha256:
            raise ValueError("paragraph raw hash mismatch")
        return self


class DatePacket(Contract):
    """Host input: regions are explicit bounded context, never provider assertions."""

    window_id: str = Field(min_length=1)
    paragraphs: list[DateParagraph] = Field(min_length=1)
    scope_basis: str = Field(min_length=1)
    scope_evidence_sha256: str = Field(pattern=_SHA)

    @model_validator(mode="after")
    def check_identity(self) -> Self:
        _unique_paragraphs(self.paragraphs)
        _contiguous_regions(self.paragraphs)
        return self


def _unique_paragraphs(paragraphs: list[DateParagraph]) -> None:
    aliases = [p.alias for p in paragraphs]
    ids = [p.source_paragraph_id for p in paragraphs]
    if len(set(aliases)) != len(aliases) or len(set(ids)) != len(ids):
        raise ValueError("paragraph aliases and source IDs must be unique")


def _contiguous_regions(paragraphs: list[DateParagraph]) -> None:
    regions = [p.region_id for p in paragraphs]
    runs = [region for i, region in enumerate(regions) if i == 0 or region != regions[i - 1]]
    if len(runs) != len(set(runs)):
        raise ValueError("scope regions must be contiguous")


class DateValue(Contract):
    start: str
    end: str
    precision: Literal["day", "month", "year"]
    extent: Literal["point", "range"]

    @model_validator(mode="after")
    def check_interval(self) -> Self:
        _check_iso(self.start, self.precision)
        _check_iso(self.end, self.precision)
        if self.start > self.end:
            raise ValueError("date range is reversed")
        if (self.start == self.end) != (self.extent == "point"):
            raise ValueError("point/range extent disagrees with endpoints")
        return self


def _check_iso(value: str, precision: str) -> None:
    patterns = {"day": r"\d{4}-\d{2}-\d{2}", "month": r"\d{4}-\d{2}", "year": r"\d{4}"}
    if re.fullmatch(patterns[precision], value) is None:
        raise ValueError("date value does not match precision")
    suffix = {"day": "", "month": "-01", "year": "-01-01"}[precision]
    date.fromisoformat(value + suffix)


class DateEvidence(Contract):
    paragraph_id: str = Field(min_length=1)
    raw_sha256: str = Field(pattern=_SHA)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)


class DateAlternative(Contract):
    value: DateValue
    evidence: list[DateEvidence] = Field(min_length=1)
    basis: str = Field(min_length=1)


class DateAssignment(Contract):
    target_ids: list[str] = Field(min_length=1)
    value: DateValue | None
    date_kind: Literal["explicit", "implicit", "none"]
    context_kind: Literal["proceeding", "mentioned", "unknown"]
    status: Literal["proposed", "unknown", "mixed", "needs_review"]
    method: Literal["explicit_text", "scoped_continuation", "no_supported_date"]
    evidence: list[DateEvidence]
    alternatives: list[DateAlternative]
    unknowns: list[str]
    basis: str = Field(min_length=1)

    @model_validator(mode="after")
    def check_assignment(self) -> Self:
        _check_unknown(self)
        _check_known(self)
        return self


def _check_unknown(item: DateAssignment) -> None:
    if item.date_kind != "none":
        return
    if item.value is not None or item.evidence or item.alternatives:
        raise ValueError("no-date assignment cannot supply a value or date evidence")
    _check_unknown_state(item)


def _check_unknown_state(item: DateAssignment) -> None:
    if item.status not in {"unknown", "needs_review"} or not item.unknowns:
        raise ValueError("no-date assignment requires explicit unknowns and unresolved status")
    if item.method != "no_supported_date" or item.context_kind != "unknown":
        raise ValueError("no-date assignment cannot claim a known context/method")


def _check_known(item: DateAssignment) -> None:
    if item.date_kind == "none":
        return
    if item.value is None or not item.evidence:
        raise ValueError("known date requires value and evidence")
    _check_known_state(item)


def _check_known_state(item: DateAssignment) -> None:
    expected = {"explicit": "explicit_text", "implicit": "scoped_continuation"}
    if item.method != expected[item.date_kind] or item.status == "unknown":
        raise ValueError("known date method/status mismatch")
    if item.alternatives and item.status not in {"mixed", "needs_review"}:
        raise ValueError("date alternatives require unresolved status")


class DateResult(Contract):
    dates: list[DateAssignment] = Field(min_length=1)


def date_result_schema() -> dict:
    """JSON Schema transport shape; host checks add source and scope semantics."""
    return DateResult.model_json_schema()


def _check_refs(values: list[str], allowed: set[str]) -> None:
    if len(values) != len(set(values)) or not set(values) <= allowed:
        raise ValueError("duplicate or unknown target alias")


def _bound_evidence(evidence: DateEvidence, paragraphs: dict[str, DateParagraph]) -> DateParagraph:
    paragraph = paragraphs.get(evidence.paragraph_id)
    if paragraph is None:
        raise ValueError("unknown evidence paragraph")
    if evidence.raw_sha256 != paragraph.raw_sha256:
        raise ValueError("evidence raw hash mismatch")
    if paragraph.raw_text[evidence.start : evidence.end] != evidence.quote:
        raise ValueError("evidence quote/offset mismatch")
    if not evidence.start < evidence.end <= len(paragraph.raw_text):
        raise ValueError("evidence offsets outside paragraph")
    return paragraph


def _supports(value: str, precision: str, quote: str) -> bool:
    if precision == "year":
        return re.search(rf"(?<!\d){re.escape(value)}(?!\d)", quote) is not None
    month_pattern = "|".join(_MONTHS)
    if precision == "month":
        return _supports_month(value, quote, month_pattern)
    pattern = rf"\b({month_pattern})\s+(\d{{1,2}}),\s+(\d{{4}})\b"
    return any(
        _day_value(month, day, year) == value
        for month, day, year in re.findall(pattern, quote, re.I)
    )


def _supports_month(value: str, quote: str, months: str) -> bool:
    pattern = rf"\b({months})\s+(\d{{4}})\b"
    return any(
        _month_value(month, year) == value for month, year in re.findall(pattern, quote, re.I)
    )


def _month_value(month: str, year: str) -> str:
    index = [name.lower() for name in _MONTHS].index(month.lower()) + 1
    return f"{year}-{index:02d}"


def _day_value(month: str, day: str, year: str) -> str:
    index = [name.lower() for name in _MONTHS].index(month.lower()) + 1
    return f"{year}-{index:02d}-{int(day):02d}"


def _check_support(value: DateValue, evidence: list[DateEvidence]) -> None:
    for endpoint in (value.start, value.end):
        if not any(_supports(endpoint, value.precision, e.quote) for e in evidence):
            raise ValueError("date endpoint not explicitly supported by quoted text")


def _check_scope(targets: list[str], evidence: list[DateEvidence], packet: DatePacket) -> None:
    paragraphs = {p.alias: p for p in packet.paragraphs}
    _check_refs(targets, set(paragraphs))
    sources = [_bound_evidence(e, paragraphs) for e in evidence]
    regions = {paragraphs[alias].region_id for alias in targets} | {p.region_id for p in sources}
    if len(regions) != 1:
        raise ValueError("date scope crosses a host-declared boundary")
    _check_direction(targets, sources, packet)


def _check_direction(targets: list[str], sources: list[DateParagraph], packet: DatePacket) -> None:
    order = {p.alias: i for i, p in enumerate(packet.paragraphs)}
    positions = [order[alias] for alias in targets]
    if positions != list(range(min(positions), max(positions) + 1)):
        raise ValueError("date targets must be ordered and contiguous")
    if sources and min(order[p.alias] for p in sources) > min(positions):
        raise ValueError("date cannot propagate backward from later evidence")


def _check_item(item: DateAssignment, packet: DatePacket) -> None:
    _check_scope(item.target_ids, item.evidence, packet)
    if item.value is not None:
        _check_support(item.value, item.evidence)
    if item.date_kind == "explicit" and not all(
        e.paragraph_id in item.target_ids for e in item.evidence
    ):
        raise ValueError("explicit date evidence must occur within target scope")
    for alternative in item.alternatives:
        _check_scope(item.target_ids, alternative.evidence, packet)
        _check_support(alternative.value, alternative.evidence)


def validate_date_result(result: dict, packet: DatePacket | dict) -> DateResult:
    """Validate proposals without accepting history or altering any source text."""
    source = DatePacket.model_validate(packet)
    parsed = DateResult.model_validate(result)
    assigned: set[str] = set()
    for item in parsed.dates:
        _check_item(item, source)
        if assigned.intersection(item.target_ids):
            raise ValueError("overlapping assignments must be represented as alternatives")
        assigned.update(item.target_ids)
    if assigned != {p.alias for p in source.paragraphs}:
        raise ValueError("each input paragraph requires a date or explicit unknown")
    return parsed


def source_mapped_dates(result: dict, packet: DatePacket | dict) -> dict:
    """Export exact host source identities beside validated proposal records."""
    source = DatePacket.model_validate(packet)
    parsed = validate_date_result(result, source)
    return {
        "schema_version": "scoped-date-v1",
        "window_id": source.window_id,
        "offset_convention": "unicode_codepoints_half_open_within_raw_paragraph",
        "scope_basis": source.scope_basis,
        "scope_evidence_sha256": source.scope_evidence_sha256,
        "sources": [p.model_dump() for p in source.paragraphs],
        "dates": parsed.model_dump()["dates"],
        "historical_status": "proposal_only_not_human_reviewed",
    }
