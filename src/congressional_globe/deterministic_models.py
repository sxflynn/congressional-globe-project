"""Strict source, ledger and support-map contracts for bounded offline repair."""

import hashlib
from typing import Literal

from pydantic import Field, model_validator

from congressional_globe.bracket_cues import BracketSource, Contract
from congressional_globe.scan_models import Sha256


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class ExactEdit(Contract):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    raw_quote: str = Field(min_length=1)
    replacement: str
    rule_id: str = Field(min_length=1)


class OCRLine(Contract):
    line_id: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1)


class ParagraphInput(Contract):
    source: BracketSource
    static_text: str = Field(max_length=6000)
    static_sha256: Sha256
    static_edits: tuple[ExactEdit, ...] = Field(max_length=128)
    lines: tuple[OCRLine, ...] = Field(max_length=256)
    line_status: Literal["declared_exact", "unavailable"]
    line_reason: str | None
    line_evidence_sha256: Sha256 | None

    @model_validator(mode="after")
    def verify_input(self) -> "ParagraphInput":
        if digest(self.static_text) != self.static_sha256:
            raise ValueError("static hash mismatch")
        replay, _ = replay_with_map(self.source.raw_text, self.static_edits)
        if replay != self.static_text:
            raise ValueError("static ledger does not replay from raw")
        _verify_lines(self)
        return self


def _verify_lines(source: ParagraphInput) -> None:
    if source.line_status == "unavailable":
        _check_unavailable_lines(source)
        return
    if not source.lines or source.line_evidence_sha256 is None:
        raise ValueError("verified lines require exact lines and provenance")
    _check_line_coverage(source.source.raw_text, source.lines)


def _check_unavailable_lines(source: ParagraphInput) -> None:
    if source.lines or not source.line_reason:
        raise ValueError("unavailable line geometry needs reason and empty lines")


def _check_line_coverage(raw: str, lines: tuple[OCRLine, ...]) -> None:
    cursor = 0
    ids = [line.line_id for line in lines]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate OCR line IDs")
    for line in lines:
        _check_line(raw, line, cursor)
        cursor = line.end
    if raw[cursor:].strip():
        raise ValueError("line geometry omits trailing raw text")


def _check_line(raw: str, line: OCRLine, cursor: int) -> None:
    if line.start < cursor or line.end <= line.start or line.end > len(raw):
        raise ValueError("invalid line interval")
    if raw[line.start : line.end] != line.text or raw[cursor : line.start].strip():
        raise ValueError("line geometry does not cover exact raw text")


class SupportSegment(Contract):
    raw_start: int = Field(ge=0)
    raw_end: int = Field(ge=0)
    derived_start: int = Field(ge=0)
    derived_end: int = Field(ge=0)
    mapping: Literal["exact_copy", "replacement"]


def _check_edit(raw: str, edit: ExactEdit, cursor: int) -> None:
    if edit.start < cursor or edit.end <= edit.start or edit.end > len(raw):
        raise ValueError("edit intervals must be ordered, nonempty and disjoint")
    if raw[edit.start : edit.end] != edit.raw_quote:
        raise ValueError("edit does not match its exact raw quote")
    if edit.raw_quote == edit.replacement:
        raise ValueError("no-op edit")


def _segment(
    start: int, end: int, derived: int, length: int, kind: Literal["exact_copy", "replacement"]
) -> SupportSegment:
    return SupportSegment(
        raw_start=start,
        raw_end=end,
        derived_start=derived,
        derived_end=derived + length,
        mapping=kind,
    )


def replay_with_map(
    raw: str, edits: tuple[ExactEdit, ...]
) -> tuple[str, tuple[SupportSegment, ...]]:
    pieces, segments = [], []
    cursor, derived = 0, 0
    for edit in edits:
        _check_edit(raw, edit, cursor)
        copied = raw[cursor : edit.start]
        if copied:
            pieces.append(copied)
            segments.append(_segment(cursor, edit.start, derived, len(copied), "exact_copy"))
            derived += len(copied)
        pieces.append(edit.replacement)
        segments.append(
            _segment(edit.start, edit.end, derived, len(edit.replacement), "replacement")
        )
        derived += len(edit.replacement)
        cursor = edit.end
    if cursor < len(raw):
        pieces.append(raw[cursor:])
        segments.append(_segment(cursor, len(raw), derived, len(raw) - cursor, "exact_copy"))
    return "".join(pieces), tuple(segments)


def derived_support(segments: tuple[SupportSegment, ...], start: int, end: int) -> tuple[int, int]:
    selected = _overlapping_segments(segments, start, end)
    if start < 0 or end <= start or not selected:
        raise ValueError("derived span has no support")
    if end > segments[-1].derived_end:
        raise ValueError("derived span outside text")
    return _support_start(selected[0], start), _support_end(selected[-1], end)


def _overlapping_segments(segments, start, end) -> list[SupportSegment]:
    return [s for s in segments if s.derived_start < end and start < s.derived_end]


def _support_start(segment: SupportSegment, start: int) -> int:
    if segment.mapping == "replacement":
        return segment.raw_start
    return segment.raw_start + max(start, segment.derived_start) - segment.derived_start


def _support_end(segment: SupportSegment, end: int) -> int:
    if segment.mapping == "replacement":
        return segment.raw_end
    return segment.raw_start + min(end, segment.derived_end) - segment.derived_start
