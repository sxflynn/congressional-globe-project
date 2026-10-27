"""Search the T43 saved static layer with explicit support in the original raw text."""

import hashlib
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_validator

from congressional_globe.literal_search import (
    COVERAGE,
    UNAVAILABLE,
    FrozenModel,
    Paragraph,
    Passage,
    SearchRequest,
    _neighbor,
    _passage,
    _positions,
)

PAIRS_SHA256 = "414b7a4e5ede7e2a8c9efca2f4b66a942b6dcefa91730f08824207009cc36e64"


class StaticEdit(FrozenModel):
    start_char: Annotated[int, Field(ge=0)]
    end_char: Annotated[int, Field(gt=0)]
    expected: str
    replacement: str
    reason: str
    confidence: Annotated[float, Field(ge=0, le=1)]

    @model_validator(mode="after")
    def check_extent(self) -> "StaticEdit":
        if self.end_char <= self.start_char:
            raise ValueError("Edit must replace a nonempty raw interval")
        return self


class StaticPair(FrozenModel):
    source: Paragraph
    static_text: str
    static_sha256: str
    static_edits: tuple[StaticEdit, ...]
    static_cleanup_provenance: dict[str, str]
    ai_status: str
    ai_provenance: None

    @model_validator(mode="after")
    def check_static(self) -> "StaticPair":
        if hashlib.sha256(self.static_text.encode()).hexdigest() != self.static_sha256:
            raise ValueError("Static paragraph fingerprint mismatch")
        _character_map(self)
        return self


def _edit_check(raw: str, edit: StaticEdit, cursor: int) -> None:
    if edit.start_char < cursor:
        raise ValueError("Edits must be ordered and nonoverlapping")
    if raw[edit.start_char : edit.end_char] != edit.expected:
        raise ValueError("Edit does not match its declared raw interval")
    if edit.end_char > len(raw):
        raise ValueError("Edit extends beyond raw paragraph")


def _copied_positions(start: int, end: int) -> tuple[tuple[int, int, bool], ...]:
    return tuple((i, i + 1, False) for i in range(start, end))


def _replacement_positions(edit: StaticEdit) -> tuple[tuple[int, int, bool], ...]:
    return tuple((edit.start_char, edit.end_char, True) for _ in edit.replacement)


def _character_map(pair: StaticPair) -> tuple[tuple[int, int, bool], ...]:
    raw = pair.source.raw_text
    cursor = 0
    pieces: list[str] = []
    positions: list[tuple[int, int, bool]] = []
    for edit in pair.static_edits:
        _edit_check(raw, edit, cursor)
        pieces.extend((raw[cursor : edit.start_char], edit.replacement))
        positions.extend(_copied_positions(cursor, edit.start_char))
        positions.extend(_replacement_positions(edit))
        cursor = edit.end_char
    pieces.append(raw[cursor:])
    positions.extend(_copied_positions(cursor, len(raw)))
    if "".join(pieces) != pair.static_text:
        raise ValueError("Saved edits do not reproduce static text")
    return tuple(positions)


class StaticHit(FrozenModel):
    static_paragraph: str
    static_sha256: str
    static_start: int
    static_end: int
    offsets: Literal["unicode_codepoints_half_open"] = "unicode_codepoints_half_open"
    matched_text: str
    raw_support: Passage
    raw_support_text: str
    mapping: Literal["exact_copy", "includes_saved_edit"]
    preceding: Passage | None
    following: Passage | None
    preceding_status: str
    following_status: str


class StaticSearchResult(FrozenModel):
    source_layer: Literal["saved_static"] = "saved_static"
    pairs_sha256: str = PAIRS_SHA256
    coverage: str = COVERAGE
    match_mode: Literal["case_sensitive_static_substring"] = "case_sensitive_static_substring"
    query: str
    total_occurrences: int
    returned_count: int
    truncated: bool
    hits: tuple[StaticHit, ...]
    message: str


def _support(pair: StaticPair, start: int, end: int) -> tuple[int, int, str]:
    selected = _character_map(pair)[start:end]
    low, high = selected[0][0], selected[-1][1]
    return low, high, pair.source.raw_text[low:high]


def _mapping_kind(
    pair: StaticPair, start: int, end: int, raw_text: str
) -> Literal["exact_copy", "includes_saved_edit"]:
    changed = any(p[2] for p in _character_map(pair)[start:end])
    if changed or raw_text != pair.static_text[start:end]:
        return "includes_saved_edit"
    return "exact_copy"


def _static_hit(pairs: tuple[StaticPair, ...], index: int, start: int, query: str) -> StaticHit:
    pair = pairs[index]
    end = start + len(query)
    low, high, raw_text = _support(pair, start, end)
    paragraphs = tuple(p.source for p in pairs)
    preceding = _neighbor(paragraphs, index, -1)
    following = _neighbor(paragraphs, index, 1)
    return StaticHit(
        static_paragraph=pair.static_text,
        static_sha256=pair.static_sha256,
        static_start=start,
        static_end=end,
        matched_text=query,
        raw_support=_passage(pair.source, low, high, "match"),
        raw_support_text=raw_text,
        mapping=_mapping_kind(pair, start, end, raw_text),
        preceding=preceding,
        following=following,
        preceding_status="Available raw context, not a match" if preceding else UNAVAILABLE,
        following_status="Available raw context, not a match" if following else UNAVAILABLE,
    )


class StaticCollection(FrozenModel):
    payload: bytes = Field(repr=False)

    @model_validator(mode="after")
    def check_payload(self) -> "StaticCollection":
        if hashlib.sha256(self.payload).hexdigest() != PAIRS_SHA256:
            raise ValueError("Frozen paired-input fingerprint mismatch")
        self._pairs()
        return self

    def _pairs(self) -> tuple[StaticPair, ...]:
        return tuple(TypeAdapter(list[StaticPair]).validate_json(self.payload))

    def search(self, query: str, *, limit: int = 20) -> StaticSearchResult:
        request = SearchRequest(query=query, limit=limit)
        pairs = self._pairs()
        occurrences = (
            (index, pos)
            for index, p in enumerate(pairs)
            for pos in _positions(p.static_text, request.query)
        )
        hits: list[StaticHit] = []
        total = 0
        for index, pos in occurrences:
            total += 1
            if len(hits) < request.limit:
                hits.append(_static_hit(pairs, index, pos, request.query))
        return _static_result(request.query, total, hits)


def _static_result(query: str, total: int, hits: list[StaticHit]) -> StaticSearchResult:
    return StaticSearchResult(
        query=query,
        total_occurrences=total,
        returned_count=len(hits),
        truncated=total > len(hits),
        hits=tuple(hits),
        message="Static-text matches in these six paragraphs"
        if total
        else "No exact static-text match in these six paragraphs",
    )


def load_static_collection(path: Path) -> StaticCollection:
    with path.open("rb") as stream:
        payload = stream.read(16_001)
    if len(payload) > 16_000:
        raise ValueError("Paired collection exceeds the bounded file size")
    return StaticCollection(payload=payload)
