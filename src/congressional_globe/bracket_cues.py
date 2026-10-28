"""Literal, source-bound bracket candidates; no historical event inference."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from congressional_globe.scan_models import Sha256

SourceId = Annotated[str, StringConstraints(pattern=r"^[^:\s]+:[0-9]+:[^:\s]+$", max_length=256)]
Cue = Literal["laughter", "applause", "hammer_fell", "unknown"]
Kind = Literal["event_cue", "numeric_marker", "editorial_marker", "unknown"]
Basis = Literal[
    "exact_literal_allowlist", "literal_numeric_form", "literal_editorial_allowlist", "unclassified"
]
IssueCode = Literal["nested_brackets", "unmatched_open", "unmatched_close"]
RULE_VERSION = "literal-bracket-cues-v1"
LITERAL_CUES: Mapping[str, Cue] = MappingProxyType(
    {
        "laughter": "laughter",
        "much laughter": "laughter",
        "great laughter": "laughter",
        "loud laughter": "laughter",
        "lots of laughter": "laughter",
        "applause": "applause",
        "great applause": "applause",
        "loud applause": "applause",
        "here the hammer fell": "hammer_fell",
    }
)
EDITORIAL_MARKERS = ("sic", "illegible", "unclear", "inaudible", "?", "...")
RULE_SHA256 = hashlib.sha256(
    json.dumps(
        {
            "version": RULE_VERSION,
            "literal_cues": dict(LITERAL_CUES),
            "editorial_markers": EDITORIAL_MARKERS,
            "normalization": (
                "classification only: casefold, collapse whitespace, "
                "remove at most one final period except literal ellipsis"
            ),
            "numeric_pattern": r"[0-9]+(?:[-\u2013,]\s*[0-9]+)*",
            "parser": (
                "balanced nonnested ASCII square brackets only; malformed/nested regions are issues"
            ),
        },
        sort_keys=True,
        ensure_ascii=False,
    ).encode()
).hexdigest()


class Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, revalidate_instances="always"
    )


def _check_text_bounds(text: str) -> None:
    if not isinstance(text, str):
        raise ValueError("bracket text must be a string")
    if len(text) > 6000:
        raise ValueError("bracket source exceeds 6000 codepoints")
    if text.count("[") + text.count("]") > 512:
        raise ValueError("bracket symbol budget exceeds 512")


class BracketSource(Contract):
    source_id: SourceId
    raw_text: str = Field(max_length=6000)
    raw_sha256: Sha256

    @model_validator(mode="after")
    def verify_source(self) -> BracketSource:
        if hashlib.sha256(self.raw_text.encode()).hexdigest() != self.raw_sha256:
            raise ValueError("bracket source raw hash mismatch")
        _check_text_bounds(self.raw_text)
        return self


class BracketAnnotation(Contract):
    annotation_id: Sha256
    source_id: SourceId
    raw_sha256: Sha256
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str
    kind: Kind
    literal_cue: Cue
    basis: Basis
    status: Literal["literal_candidate"] = "literal_candidate"


class BracketIssue(Contract):
    code: IssueCode
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str


class BracketReport(Contract):
    contract: Literal["source-bound-bracket-candidates-v1"] = "source-bound-bracket-candidates-v1"
    rule_version: Literal["literal-bracket-cues-v1"] = RULE_VERSION
    rules_sha256: Sha256 = RULE_SHA256
    source: BracketSource
    annotations: tuple[BracketAnnotation, ...] = Field(max_length=256)
    issues: tuple[BracketIssue, ...] = Field(max_length=512)
    inspection_state: Literal["complete", "needs_review"]

    @model_validator(mode="after")
    def verify_report(self) -> BracketReport:
        if self.rules_sha256 != RULE_SHA256:
            raise ValueError("bracket rules hash mismatch")
        if (self.annotations, self.issues, self.inspection_state) != _material(self.source):
            raise ValueError("bracket report does not reproduce its exact source")
        return self


@dataclass
class _Scanner:
    opens: list[int] = field(default_factory=list)
    nested: bool = False
    spans: list[tuple[int, int]] = field(default_factory=list)
    issues: list[tuple[IssueCode, int, int]] = field(default_factory=list)

    def opening(self, position: int) -> None:
        self.nested = self.nested or bool(self.opens)
        self.opens.append(position)

    def closing(self, position: int) -> None:
        if not self.opens:
            self.issues.append(("unmatched_close", position, position + 1))
            return
        start = self.opens.pop()
        if self.opens:
            return
        if self.nested:
            self.issues.append(("nested_brackets", start, position + 1))
        else:
            self.spans.append((start, position + 1))
        self.nested = False


def _scan(text: str) -> _Scanner:
    scanner = _Scanner()
    actions = {"[": scanner.opening, "]": scanner.closing}
    for position, char in enumerate(text):
        if char in actions:
            actions[char](position)
    _finish_scan(scanner, text)
    return scanner


def _finish_scan(scanner: _Scanner, text: str) -> None:
    if scanner.nested and scanner.opens:
        scanner.issues.append(("nested_brackets", scanner.opens[0], len(text)))
    scanner.issues.extend(("unmatched_open", start, start + 1) for start in scanner.opens)
    scanner.issues.sort(key=lambda issue: (issue[1], issue[2], issue[0]))


def _classify(text: str) -> tuple[Kind, Cue, Basis]:
    normalized = _normalized_literal(text)
    if normalized in LITERAL_CUES:
        return "event_cue", LITERAL_CUES[normalized], "exact_literal_allowlist"
    if re.fullmatch(r"[0-9]+(?:[-\u2013,]\s*[0-9]+)*", normalized):
        return "numeric_marker", "unknown", "literal_numeric_form"
    if normalized in EDITORIAL_MARKERS:
        return "editorial_marker", "unknown", "literal_editorial_allowlist"
    return "unknown", "unknown", "unclassified"


def _normalized_literal(text: str) -> str:
    normalized = " ".join(text[1:-1].strip().casefold().split())
    return normalized if normalized == "..." else normalized.removesuffix(".")


def _annotation(source: BracketSource, start: int, end: int) -> BracketAnnotation:
    text = source.raw_text[start:end]
    kind, cue, basis = _classify(text)
    identity = [source.source_id, source.raw_sha256, RULE_SHA256, start, end]
    return BracketAnnotation(
        annotation_id=hashlib.sha256(json.dumps(identity).encode()).hexdigest(),
        source_id=source.source_id,
        raw_sha256=source.raw_sha256,
        start=start,
        end=end,
        text=text,
        kind=kind,
        literal_cue=cue,
        basis=basis,
    )


def _issues(text: str, scanner: _Scanner) -> tuple[BracketIssue, ...]:
    return tuple(
        BracketIssue(code=code, start=start, end=end, text=text[start:end])
        for code, start, end in scanner.issues
    )


def _material(source: BracketSource) -> tuple:
    scanner = _scan(source.raw_text)
    annotations = tuple(_annotation(source, start, end) for start, end in scanner.spans)
    issues = _issues(source.raw_text, scanner)
    return annotations, issues, "needs_review" if issues else "complete"


def annotate_brackets(source: BracketSource) -> BracketReport:
    """Preserve every balanced literal span; malformed structures require review."""
    source = BracketSource.model_validate(source)
    annotations, issues, state = _material(source)
    return BracketReport(
        source=source, annotations=annotations, issues=issues, inspection_state=state
    )


class BracketComparison(Contract):
    contract: Literal["bracket-literal-preservation-v1"] = "bracket-literal-preservation-v1"
    source_report: BracketReport
    proposed_text: str = Field(max_length=6000)
    proposed_sha256: Sha256
    proposed_quotes: tuple[str, ...] = Field(max_length=256)
    proposed_issues: tuple[BracketIssue, ...] = Field(max_length=512)
    status: Literal["same_literal_sequence", "changed_literal_sequence", "needs_review"]

    @model_validator(mode="after")
    def verify_comparison(self) -> BracketComparison:
        _check_text_bounds(self.proposed_text)
        if self.proposed_sha256 != hashlib.sha256(self.proposed_text.encode()).hexdigest():
            raise ValueError("proposed bracket text hash mismatch")
        expected = _comparison_parts(self.source_report, self.proposed_text)
        if (self.proposed_quotes, self.proposed_issues, self.status) != expected:
            raise ValueError("bracket comparison does not reproduce proposed text")
        return self


def _comparison_parts(report: BracketReport, proposed: str) -> tuple:
    scanner = _scan(proposed)
    quotes = tuple(proposed[start:end] for start, end in scanner.spans)
    issues = _issues(proposed, scanner)
    if report.issues or issues:
        return quotes, issues, "needs_review"
    raw_quotes = tuple(annotation.text for annotation in report.annotations)
    status = "same_literal_sequence" if quotes == raw_quotes else "changed_literal_sequence"
    return quotes, issues, status


def compare_brackets(source: BracketSource, proposed_text: str) -> BracketComparison:
    """Flag literal sequence changes; same text is not verified event fidelity."""
    _check_text_bounds(proposed_text)
    report = annotate_brackets(source)
    quotes, issues, status = _comparison_parts(report, proposed_text)
    return BracketComparison(
        source_report=report,
        proposed_text=proposed_text,
        proposed_sha256=hashlib.sha256(proposed_text.encode()).hexdigest(),
        proposed_quotes=quotes,
        proposed_issues=issues,
        status=status,
    )
