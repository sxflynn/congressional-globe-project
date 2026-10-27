"""Literal search over the single frozen six-paragraph T42 collection."""

import hashlib
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

COLLECTION_SHA256 = "9509aaefdff21fbfcaf113b57b6b06b9cc72ac011fbf5fd5502156ab20a54815"
COVERAGE = "Six frozen paragraphs P1-P6; congressionalg7391unit, scan leaf 117 only"
UNAVAILABLE = "Context unavailable within this slice"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Paragraph(FrozenModel):
    alias: str
    source_paragraph_id: str
    item_identifier: str
    scan_leaf: Annotated[int, Field(ge=0)]
    raw_text: str
    raw_sha256: str
    region_id: str

    @model_validator(mode="after")
    def check_hash(self) -> "Paragraph":
        if hashlib.sha256(self.raw_text.encode()).hexdigest() != self.raw_sha256:
            raise ValueError("Raw paragraph fingerprint mismatch")
        return self


class Citation(FrozenModel):
    item_identifier: str
    scan_leaf: int
    source_paragraph_id: str
    raw_sha256: str
    start: int
    end: int
    page_url: str
    page_url_status: Literal["unverified"] = "unverified"
    offsets: Literal["unicode_codepoints_half_open"] = "unicode_codepoints_half_open"


class Passage(FrozenModel):
    paragraph: Paragraph
    citation: Citation
    kind: Literal["match", "context"]


class Hit(FrozenModel):
    match: Passage
    quote: str
    preceding: Passage | None
    following: Passage | None
    preceding_status: str
    following_status: str


class SearchResult(FrozenModel):
    collection_sha256: str = COLLECTION_SHA256
    coverage: str = COVERAGE
    match_mode: Literal["case_sensitive_raw_substring"] = "case_sensitive_raw_substring"
    query: str
    total_occurrences: int
    returned_count: int
    truncated: bool
    hits: tuple[Hit, ...]
    message: str


class SearchRequest(FrozenModel):
    query: Annotated[str, Field(min_length=1, max_length=256)]
    limit: Annotated[int, Field(ge=1, le=20)] = 20

    @model_validator(mode="after")
    def check_query(self) -> "SearchRequest":
        if not self.query.strip():
            raise ValueError("Query must contain non-whitespace characters")
        return self


def _passage(p: Paragraph, start: int, end: int, kind: Literal["match", "context"]) -> Passage:
    citation = Citation(
        item_identifier=p.item_identifier,
        scan_leaf=p.scan_leaf,
        source_paragraph_id=p.source_paragraph_id,
        raw_sha256=p.raw_sha256,
        start=start,
        end=end,
        page_url=f"https://archive.org/details/{p.item_identifier}/page/n{p.scan_leaf}",
    )
    return Passage(paragraph=p, citation=citation, kind=kind)


def _neighbor(paragraphs: tuple[Paragraph, ...], index: int, step: int) -> Passage | None:
    other = index + step
    if not 0 <= other < len(paragraphs):
        return None
    p = paragraphs[other]
    if p.region_id != paragraphs[index].region_id:
        return None
    return _passage(p, 0, len(p.raw_text), "context")


def _hit(paragraphs: tuple[Paragraph, ...], index: int, start: int, query: str) -> Hit:
    preceding = _neighbor(paragraphs, index, -1)
    following = _neighbor(paragraphs, index, 1)
    return Hit(
        match=_passage(paragraphs[index], start, start + len(query), "match"),
        quote=query,
        preceding=preceding,
        following=following,
        preceding_status="Available context, not a match" if preceding else UNAVAILABLE,
        following_status="Available context, not a match" if following else UNAVAILABLE,
    )


def _positions(text: str, query: str):
    start = text.find(query)
    while start >= 0:
        yield start
        start = text.find(query, start + 1)


class LiteralCollection(FrozenModel):
    """Construction requires the pinned file bytes, including order and region assignments."""

    payload: bytes = Field(repr=False)

    @model_validator(mode="after")
    def check_payload(self) -> "LiteralCollection":
        if hashlib.sha256(self.payload).hexdigest() != COLLECTION_SHA256:
            raise ValueError("Frozen collection fingerprint mismatch")
        self._paragraphs()
        return self

    def _paragraphs(self) -> tuple[Paragraph, ...]:
        records = TypeAdapter(list[Paragraph]).validate_json(self.payload)
        return tuple(records)

    def search(self, query: str, *, limit: int = 20) -> SearchResult:
        request = SearchRequest(query=query, limit=limit)
        paragraphs = self._paragraphs()
        occurrences = (
            (index, pos)
            for index, p in enumerate(paragraphs)
            for pos in _positions(p.raw_text, request.query)
        )
        hits: list[Hit] = []
        total = 0
        for index, pos in occurrences:
            total += 1
            if len(hits) < request.limit:
                hits.append(_hit(paragraphs, index, pos, request.query))
        return _result(request.query, total, hits)


def _result(query: str, total: int, hits: list[Hit]) -> SearchResult:
    return SearchResult(
        query=query,
        total_occurrences=total,
        returned_count=len(hits),
        truncated=total > len(hits),
        hits=tuple(hits),
        message="Exact matches in these six paragraphs"
        if total
        else "No exact match in these six paragraphs",
    )


def load_collection(path: Path) -> LiteralCollection:
    """Load only pinned T42 bytes; no manifest supplied by the caller can change the trust root."""
    with path.open("rb") as stream:
        payload = stream.read(16_001)
    if len(payload) > 16_000:
        raise ValueError("Collection exceeds the bounded file size")
    return LiteralCollection(payload=payload)
