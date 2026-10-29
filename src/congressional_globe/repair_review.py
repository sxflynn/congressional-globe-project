"""Bounded review-only signals for OCR damage missed by line-join rules.

No replacement here is applied or established from dictionary membership.
The older deterministic proposal/report contract stays unchanged.
"""

import hashlib
import re
import string
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from congressional_globe.bracket_cues import BracketSource, Contract
from congressional_globe.deterministic_lexicon import Lexicon, LexiconIdentity, lookup
from congressional_globe.productive_ocr_host import Paragraph, Signal, canonical_json
from congressional_globe.scan_models import Sha256

RULE_VERSION = "punctuation-internal-hyphen-review-v1"
ISOLATED_QUOTE = re.compile(r"(?<!\S)['\u2018\u2019](?!\S)")
HYPHENATED = re.compile(r"(?<![\w\-])[A-Za-z]+(?:-[A-Za-z]+)+(?![\w\-])")
IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


ReviewReason = Literal[
    "isolated_mark_needs_image",
    "unknown_internal_hyphen",
    "word_resource_unavailable",
    "token_exceeds_candidate_limit",
]


class ReviewFinding(Contract):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    raw_quote: str = Field(min_length=1)
    kind: Literal["isolated_quote", "internal_hyphen_damage"]
    reason: ReviewReason
    candidate_readings: tuple[str, ...] = Field(max_length=16)
    route: Literal["image_review_required"] = "image_review_required"
    state: Literal["unverified_review_candidate"] = "unverified_review_candidate"


class ReviewReport(Contract):
    contract: Literal["bounded-missed-error-review-v1"] = "bounded-missed-error-review-v1"
    rule_version: Literal["punctuation-internal-hyphen-review-v1"] = RULE_VERSION
    implementation_sha256: Sha256 = IMPLEMENTATION_SHA256
    source: BracketSource
    words: LexiconIdentity | None
    findings: tuple[ReviewFinding, ...] = Field(max_length=128)
    proposed_text: str = Field(max_length=6000)
    interpretation: Literal["review_signals_only_not_corrections"] = (
        "review_signals_only_not_corrections"
    )
    source_quality: Literal["not_verified"] = "not_verified"

    @model_validator(mode="after")
    def verify_spans(self) -> "ReviewReport":
        if self.proposed_text != self.source.raw_text:
            raise ValueError("review-only diagnostics must preserve original text")
        _verify_findings(self.source.raw_text, self.findings)
        return self


def _verify_findings(raw: str, findings: tuple[ReviewFinding, ...]) -> None:
    cursor = 0
    for finding in findings:
        _verify_finding(raw, finding, cursor)
        cursor = finding.end


def _verify_finding(raw: str, finding: ReviewFinding, cursor: int) -> None:
    if finding.start < cursor or finding.end <= finding.start or finding.end > len(raw):
        raise ValueError("review findings must be ordered and disjoint")
    if raw[finding.start : finding.end] != finding.raw_quote:
        raise ValueError("review finding does not match exact raw text")


def _punctuation(raw: str) -> list[ReviewFinding]:
    return [
        ReviewFinding(
            start=match.start(),
            end=match.end(),
            raw_quote=match.group(),
            kind="isolated_quote",
            reason="isolated_mark_needs_image",
            candidate_readings=(),
        )
        for match in ISOLATED_QUOTE.finditer(raw)
    ]


def _word_candidates(token: str, words: Lexicon) -> tuple[str, ...]:
    collapsed = token.replace("-", "").casefold()
    candidates = {collapsed} if lookup(words, collapsed) == "known" else set()
    for index in range(len(collapsed)):
        candidates.update(_substitutions(collapsed, index, words))
    if len(candidates) > 16:
        raise ValueError("damaged-token candidate limit exceeded; no truncation")
    return tuple(sorted(candidates))


def _substitutions(token: str, index: int, words: Lexicon) -> set[str]:
    return {
        changed
        for letter in string.ascii_lowercase
        if letter != token[index]
        and lookup(words, changed := token[:index] + letter + token[index + 1 :]) == "known"
    }


def _hyphen_reason(token: str, words: Lexicon | None) -> ReviewReason:
    if words is None:
        return "word_resource_unavailable"
    if len(token) > 64:
        return "token_exceeds_candidate_limit"
    return "unknown_internal_hyphen"


def _hyphens(raw: str, words: Lexicon | None) -> list[ReviewFinding]:
    findings = []
    for match in HYPHENATED.finditer(raw):
        token = match.group()
        if lookup(words, token) == "known":
            continue
        findings.append(_hyphen_finding(match, words))
    return findings


def _hyphen_finding(match, words: Lexicon | None) -> ReviewFinding:
    token = match.group()
    candidates = _word_candidates(token, words) if words and len(token) <= 64 else ()
    return ReviewFinding(
        start=match.start(),
        end=match.end(),
        raw_quote=token,
        kind="internal_hyphen_damage",
        reason=_hyphen_reason(token, words),
        candidate_readings=candidates,
    )


def review_missed_errors(source: BracketSource, words: Lexicon | None = None) -> ReviewReport:
    """Return explicit image-review needs; do not silently repair punctuation or spelling."""
    source = BracketSource.model_validate(source)
    if words is not None and words.spec.purpose != "words":
        raise ValueError("missed-error review requires a word lexicon")
    findings = sorted(
        [*_punctuation(source.raw_text), *_hyphens(source.raw_text, words)], key=lambda f: f.start
    )
    return ReviewReport(
        source=source,
        words=words.identity() if words else None,
        findings=tuple(findings),
        proposed_text=source.raw_text,
    )


def verify_review_report(report: ReviewReport, words: Lexicon | None = None) -> None:
    checked = ReviewReport.model_validate(report)
    if checked != review_missed_errors(checked.source, words):
        raise ValueError("review report does not reproduce with pinned rules/resources")


def provider_signals(
    report: ReviewReport, paragraph: dict, words: Lexicon | None = None
) -> list[Signal]:
    """Bind checked flags to the actual host paragraph, not an arbitrary alias.

    The caller passes the exact paragraph row used in its host packet. The
    normal host validator must still verify the final packet and diagnostics.
    """
    verify_review_report(report, words)
    bound = Paragraph.model_validate_json(canonical_json(paragraph))
    _verify_paragraph(report.source, bound)
    return [_signal(finding, bound.alias, report.source) for finding in report.findings]


def _verify_paragraph(source: BracketSource, paragraph: Paragraph) -> None:
    expected = (source.source_id, source.raw_sha256, source.raw_text, "target")
    actual = (paragraph.source_id, paragraph.raw.sha256, paragraph.raw.text, paragraph.role)
    if actual != expected:
        raise ValueError("host paragraph does not bind this report's exact target source")


def _signal(finding: ReviewFinding, alias: str, source: BracketSource) -> Signal:
    identity = (
        f"{RULE_VERSION}:{source.source_id}:{source.raw_sha256}:{alias}:"
        f"{finding.start}:{finding.end}:{finding.raw_quote}"
    )
    return Signal(
        signal_id=hashlib.sha256(identity.encode()).hexdigest(),
        paragraph_alias=alias,
        raw_start=finding.start,
        raw_end=finding.end,
        raw_quote=finding.raw_quote,
        category="other" if finding.kind == "isolated_quote" else "word",
        flags=[finding.kind, finding.reason, finding.state],
        route_reason=(
            "Inspect the original image; this signal is not a repair or a verified reading."
        ),
    )
