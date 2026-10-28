"""Frozen lexical/pattern signals and guarded line-wrap proposals."""

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import Field

from congressional_globe.bracket_cues import Contract, annotate_brackets
from congressional_globe.deterministic_geometry import GeometryRegistry
from congressional_globe.deterministic_lexicon import Lexicon, LexiconIdentity, lookup
from congressional_globe.deterministic_models import (
    ExactEdit,
    ParagraphInput,
    SupportSegment,
    derived_support,
)

TOKEN = re.compile(r"\d+(?:[.,/\-]\d+)*(?:%|\b)|[^\W_]+(?:['\u2019\-][^\W_]+)*|[{}^|~\uFFFD]")
SPLIT = re.compile(r"([A-Za-z]+)-\s+([a-z][A-Za-z]*)")
NUMBER = re.compile(r"\d+(?:[.,/\-]\d+)*%?")
ROMAN = re.compile(r"[IVXLCDM]+")
TITLE = re.compile(r"(?:Mr\.|Mrs\.|Miss|Senator|General|Dr\.)\s+$", re.IGNORECASE)
ROMAN_CONTEXT = re.compile(
    r"(?:chapter|chap\.|article|art\.|section|sec\.|no\.)\s+$", re.IGNORECASE
)
RULE_VERSION = "bounded-lexical-linewrap-v1"


@dataclass(frozen=True)
class Resources:
    words: Lexicon | None = None
    names: Lexicon | None = None
    places: Lexicon | None = None
    geometry: GeometryRegistry | None = None

    def __post_init__(self) -> None:
        for purpose in ("words", "names", "places"):
            resource = getattr(self, purpose)
            if resource is not None and resource.spec.purpose != purpose:
                raise ValueError("lexicon purpose mismatch")

    def identities(self) -> tuple[LexiconIdentity, ...]:
        return tuple(
            resource.identity()
            for resource in (self.words, self.names, self.places)
            if resource is not None
        )


SplitReason = Literal[
    "guarded_adjacent_line_join",
    "line_geometry_unavailable",
    "not_at_adjacent_line_boundary",
    "vocabulary_unavailable",
    "joined_form_not_known",
    "known_hyphenated_form",
    "standalone_parts_ambiguous",
    "protected_bracket_span",
    "uppercase_or_nonlowercase",
    "malformed_bracket_structure",
]


class SplitFinding(Contract):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    raw_quote: str
    joined_candidate: str
    decision: Literal["proposed_join", "retained_for_review"]
    reason: SplitReason


class TokenFinding(Contract):
    layer: Literal["raw", "proposed"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str
    raw_start: int = Field(ge=0)
    raw_end: int = Field(gt=0)
    raw_quote: str
    context: str
    categories: tuple[
        Literal["word", "name_place_candidate", "number", "mixed_alphanumeric", "symbol_pattern"],
        ...,
    ]
    signals: tuple[
        Literal[
            "word_not_in_vocabulary",
            "vocabulary_not_assessed",
            "numeric_value_unverified",
            "roman_like_ambiguous",
            "mixed_identifier_unverified",
            "symbol_pattern_unverified",
            "title_name_cue",
            "capitalized_candidate",
            "lexical_name_hint",
            "lexical_place_hint",
        ],
        ...,
    ]
    routes: tuple[
        Literal[
            "whole_unit_audit_only",
            "word_image_check_candidate",
            "number_image_check_candidate",
            "name_place_image_check_candidate",
            "pattern_image_check_candidate",
        ],
        ...,
    ]
    membership: Literal["known", "unfamiliar", "not_assessed", "not_word"]


def split_findings(source: ParagraphInput, resources: Resources) -> tuple[SplitFinding, ...]:
    protected = annotate_brackets(source.source)
    return tuple(
        _split_finding(source, resources, match, protected)
        for match in SPLIT.finditer(source.source.raw_text)
    )


def _split_finding(source: ParagraphInput, resources: Resources, match, protected) -> SplitFinding:
    left, right = match.groups()
    reason = _split_reason(source, resources, match, protected)
    return SplitFinding(
        start=match.start(),
        end=match.end(),
        raw_quote=match.group(),
        joined_candidate=left + right,
        decision="proposed_join"
        if reason == "guarded_adjacent_line_join"
        else "retained_for_review",
        reason=reason,
    )


def _split_reason(source: ParagraphInput, resources: Resources, match, protected) -> SplitReason:
    if protected.issues:
        return "malformed_bracket_structure"
    if _intersects_bracket(match.start(), match.end(), protected):
        return "protected_bracket_span"
    if source.line_status == "unavailable" or resources.geometry is None:
        return "line_geometry_unavailable"
    resources.geometry.matches(source)
    if not _line_wrap(source, match):
        return "not_at_adjacent_line_boundary"
    return _word_join_reason(match.group(1), match.group(2), resources.words)


def _intersects_bracket(start: int, end: int, report) -> bool:
    spans = [(x.start, x.end) for x in (*report.annotations, *report.issues)]
    return any(start < high and low < end for low, high in spans)


def _line_wrap(source: ParagraphInput, match) -> bool:
    for left, right in zip(source.lines, source.lines[1:], strict=False):
        if _line_pair_matches(source.source.raw_text, match, left, right):
            return True
    return False


def _line_pair_matches(raw: str, match, left, right) -> bool:
    if not (
        left.start
        <= match.start()
        < left.end
        <= right.start
        <= match.start(2)
        < match.end()
        <= right.end
    ):
        return False
    return (
        not raw[match.end(1) + 1 : left.end].strip()
        and not raw[right.start : match.start(2)].strip()
    )


def _word_join_reason(left: str, right: str, words: Lexicon | None) -> SplitReason:
    if not left.islower() or not right.islower():
        return "uppercase_or_nonlowercase"
    if words is None:
        return "vocabulary_unavailable"
    if lookup(words, left + right) != "known":
        return "joined_form_not_known"
    return _ambiguous_join_reason(left, right, words)


def _ambiguous_join_reason(left: str, right: str, words: Lexicon) -> SplitReason:
    if lookup(words, left + "-" + right) == "known":
        return "known_hyphenated_form"
    if lookup(words, left) == "known" and lookup(words, right) == "known":
        return "standalone_parts_ambiguous"
    return "guarded_adjacent_line_join"


def proposed_edits(splits: tuple[SplitFinding, ...]) -> tuple[ExactEdit, ...]:
    return tuple(
        ExactEdit(
            start=s.start,
            end=s.end,
            raw_quote=s.raw_quote,
            replacement=s.joined_candidate,
            rule_id=RULE_VERSION + ":guarded_adjacent_line_join",
        )
        for s in splits
        if s.decision == "proposed_join"
    )


def _base_token(token: str, prefix: str, resources: Resources) -> tuple:
    if NUMBER.fullmatch(token):
        return ["number"], ["numeric_value_unverified"], "not_word"
    if _mixed(token):
        return ["mixed_alphanumeric"], ["mixed_identifier_unverified"], "not_word"
    if len(token) == 1 and not token.isalnum():
        return ["symbol_pattern"], ["symbol_pattern_unverified"], "not_word"
    return _word_token(token, prefix, resources)


def _mixed(token: str) -> bool:
    return any(c.isalpha() for c in token) and any(c.isdecimal() for c in token)


def _word_token(token: str, prefix: str, resources: Resources) -> tuple:
    membership = lookup(resources.words, token)
    signals = (
        []
        if membership == "known"
        else [
            {"unfamiliar": "word_not_in_vocabulary", "not_assessed": "vocabulary_not_assessed"}[
                membership
            ]
        ]
    )
    categories = ["word"]
    if _roman(token, prefix):
        categories.append("number")
        signals.append("roman_like_ambiguous")
    return categories, signals, membership


def _roman(token: str, prefix: str) -> bool:
    if not ROMAN.fullmatch(token):
        return False
    return len(token) > 1 or bool(ROMAN_CONTEXT.search(prefix))


def _name_signals(token: str, prefix: str, resources: Resources) -> list[str]:
    signals = []
    if TITLE.search(prefix):
        signals.append("title_name_cue")
    if _capitalized(token, prefix):
        signals.append("capitalized_candidate")
    signals.extend(_lexical_names(token, resources))
    return signals


def _capitalized(token: str, prefix: str) -> bool:
    if not prefix.strip() or re.search(r"[.!?\[]\s*$", prefix):
        return False
    return token.istitle()


def _lexical_names(token: str, resources: Resources) -> list[str]:
    if not token[0].isupper():
        return []
    return [
        signal
        for resource, signal in [
            (resources.names, "lexical_name_hint"),
            (resources.places, "lexical_place_hint"),
        ]
        if lookup(resource, token) == "known"
    ]


def _routes(signals: list[str]) -> tuple:
    groups = [
        ({"word_not_in_vocabulary"}, "word_image_check_candidate"),
        ({"numeric_value_unverified", "roman_like_ambiguous"}, "number_image_check_candidate"),
        (
            {"title_name_cue", "capitalized_candidate", "lexical_name_hint", "lexical_place_hint"},
            "name_place_image_check_candidate",
        ),
        (
            {"mixed_identifier_unverified", "symbol_pattern_unverified"},
            "pattern_image_check_candidate",
        ),
    ]
    routes = tuple(route for keys, route in groups if keys.intersection(signals))
    return routes or ("whole_unit_audit_only",)


def token_findings(
    raw: str,
    text: str,
    layer: Literal["raw", "proposed"],
    segments: tuple[SupportSegment, ...],
    resources: Resources,
) -> tuple[TokenFinding, ...]:
    return tuple(
        _token(raw, text, layer, segments, resources, match) for match in TOKEN.finditer(text)
    )


def _token(
    raw: str,
    text: str,
    layer: Literal["raw", "proposed"],
    segments: tuple[SupportSegment, ...],
    resources: Resources,
    match,
) -> TokenFinding:
    prefix = text[max(0, match.start() - 40) : match.start()]
    categories, signals, membership = _base_token(match.group(), prefix, resources)
    names = _name_signals(match.group(), prefix, resources)
    if names:
        categories.append("name_place_candidate")
        signals.extend(names)
    low, high = derived_support(segments, match.start(), match.end())
    return TokenFinding(
        layer=layer,
        start=match.start(),
        end=match.end(),
        text=match.group(),
        raw_start=low,
        raw_end=high,
        raw_quote=raw[low:high],
        context=raw[max(0, low - 32) : min(len(raw), high + 32)],
        categories=tuple(categories),
        signals=tuple(signals),
        routes=_routes(signals),
        membership=membership,
    )
