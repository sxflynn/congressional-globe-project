"""Source-bound, reversible proposed reading text; never canonical acceptance."""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from congressional_globe.inventory import PARTS
from congressional_globe.models import BoundingBox, PrintedPage, TextEdit
from congressional_globe.normalization import apply_edits
from congressional_globe.scan_models import NonBlank, Sha256

ReadingStratum = Literal[
    "ordinary", "damage_cue", "structured", "long", "continuation", "quotation"
]


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class ReadingParagraph(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_identifier: NonBlank
    part_number: int = Field(ge=1, le=5)
    scan_leaf: int = Field(ge=0)
    printed_page: PrintedPage
    reading_order: int = Field(ge=0)
    paragraph_id: NonBlank
    hocr_page_id: NonBlank
    line_ids: list[NonBlank]
    bbox: BoundingBox | None
    raw: str
    raw_sha256: Sha256
    static: str
    static_patches: list[TextEdit]
    static_sha256: Sha256

    @model_validator(mode="after")
    def verify_texts(self) -> ReadingParagraph:
        if PARTS.get(self.item_identifier) != self.part_number:
            raise ValueError("source item and part disagree")
        if text_hash(self.raw) != self.raw_sha256 or text_hash(self.static) != self.static_sha256:
            raise ValueError("reading paragraph text hash mismatch")
        if apply_edits(self.raw, self.static_patches) != self.static:
            raise ValueError("static baseline does not replay from raw")
        return self

    @property
    def source_id(self) -> str:
        return f"{self.item_identifier}:{self.scan_leaf}:{self.paragraph_id}"


class ReadingCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: NonBlank
    part_number: int = Field(ge=1, le=5)
    stratum: ReadingStratum
    split: Literal["primary", "confirmation"]
    target: list[ReadingParagraph] = Field(min_length=1)
    context_before: list[ReadingParagraph] = Field(default_factory=list)
    context_after: list[ReadingParagraph] = Field(default_factory=list)
    selection_reason: NonBlank
    source_review: Literal["pending"] = "pending"

    @model_validator(mode="after")
    def verify_sources(self) -> ReadingCandidate:
        records = [*self.context_before, *self.target, *self.context_after]
        ids = [record.source_id for record in records]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate paragraph in target/context")
        if any(record.part_number != self.part_number for record in records):
            raise ValueError("candidate crosses corpus parts")
        return self


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_id: NonBlank
    raw_sha256: Sha256
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class ReadingPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: NonBlank
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    old: str
    new: str
    image_ids: list[NonBlank] = Field(min_length=1)
    reason: NonBlank


class UncertainReading(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_id: NonBlank
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    reason: NonBlank


class ReadingReply(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    unit_id: NonBlank
    status: Literal["unchanged", "proposed", "needs_review"]
    patches: list[ReadingPatch]
    uncertain: list[UncertainReading]

    @model_validator(mode="after")
    def consistent_status(self) -> ReadingReply:
        valid = {
            "unchanged": self._unchanged(),
            "proposed": self._proposed(),
            "needs_review": bool(self.uncertain),
        }
        if not valid[self.status]:
            raise ValueError("reply status inconsistent with patches/uncertainty")
        return self

    def _unchanged(self) -> bool:
        return not (self.patches or self.uncertain)

    def _proposed(self) -> bool:
        return bool(self.patches) and not self.uncertain


class SpanMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    raw_start: int
    raw_end: int
    clean_start: int
    clean_end: int
    kind: Literal["unchanged", "replacement"]


def replay_paragraph(raw: str, patches: list[ReadingPatch]) -> tuple[str, list[SpanMapping]]:
    """No offset repair, sorting, guessing, or acceptance of unsupported metadata."""
    chunks: list[str] = []
    mappings: list[SpanMapping] = []
    raw_cursor = clean_cursor = 0
    for patch in patches:
        _check_patch(raw, patch, raw_cursor)
        unchanged = raw[raw_cursor : patch.start]
        mappings.append(
            _mapping(raw_cursor, patch.start, clean_cursor, len(unchanged), "unchanged")
        )
        clean_cursor += len(unchanged)
        mappings.append(
            _mapping(patch.start, patch.end, clean_cursor, len(patch.new), "replacement")
        )
        chunks.extend([unchanged, patch.new])
        clean_cursor += len(patch.new)
        raw_cursor = patch.end
    tail = raw[raw_cursor:]
    chunks.append(tail)
    mappings.append(_mapping(raw_cursor, len(raw), clean_cursor, len(tail), "unchanged"))
    return "".join(chunks), mappings


def _mapping(start: int, end: int, clean: int, length: int, kind: str) -> SpanMapping:
    return SpanMapping.model_validate(
        dict(raw_start=start, raw_end=end, clean_start=clean, clean_end=clean + length, kind=kind)
    )


def _check_patch(raw: str, patch: ReadingPatch, cursor: int) -> None:
    if not cursor <= patch.start <= patch.end <= len(raw):
        raise ValueError("patch order, overlap or bounds invalid")
    if raw[patch.start : patch.end] != patch.old:
        raise ValueError("patch old text mismatch")
    if patch.old == patch.new:
        raise ValueError("no-op patch")


def validate_reply(
    unit: ReadingCandidate, reply: ReadingReply, image_coverage: dict[str, list[EvidenceSpan]]
) -> dict[str, dict]:
    """Coverage must come from verified image bindings, never provider declarations."""
    if unit.id != reply.unit_id:
        raise ValueError("reply unit ID mismatch")
    targets = {paragraph.source_id: paragraph for paragraph in unit.target}
    _verify_reply_anchors(reply, targets, image_coverage)
    return {source_id: _derived(paragraph, reply) for source_id, paragraph in targets.items()}


def _verify_reply_anchors(
    reply: ReadingReply, targets: dict, coverage: dict[str, list[EvidenceSpan]]
) -> None:
    for patch in reply.patches:
        _verify_patch_anchor(patch, targets, coverage)
    for span in reply.uncertain:
        _check_uncertainty(span, targets)


def _verify_patch_anchor(patch: ReadingPatch, targets: dict, coverage: dict) -> None:
    if patch.source_id not in targets:
        raise ValueError("patch references non-target paragraph")
    for image in patch.image_ids:
        if not any(
            _covered(patch, span, targets[patch.source_id]) for span in coverage.get(image, [])
        ):
            raise ValueError("patch image does not cover exact raw span/hash")


def _check_uncertainty(span: UncertainReading, targets: dict) -> None:
    if span.source_id not in targets:
        raise ValueError("uncertainty references non-target paragraph")
    if not 0 <= span.start < span.end <= len(targets[span.source_id].raw):
        raise ValueError("uncertainty span invalid")


def _derived(paragraph: ReadingParagraph, reply: ReadingReply) -> dict:
    patches = [patch for patch in reply.patches if patch.source_id == paragraph.source_id]
    uncertain = [span for span in reply.uncertain if span.source_id == paragraph.source_id]
    _check_disputed(patches, uncertain)
    clean, mapping = replay_paragraph(paragraph.raw, patches)
    return dict(
        text=clean,
        sha256=text_hash(clean),
        raw_sha256=paragraph.raw_sha256,
        mapping=[span.model_dump() for span in mapping],
        uncertain=[span.model_dump() for span in uncertain],
        status="model_proposal",
    )


def _overlaps(patch: ReadingPatch, span: UncertainReading) -> bool:
    if patch.start == patch.end:
        return span.start <= patch.start < span.end
    return patch.start < span.end and span.start < patch.end


def _covered(patch: ReadingPatch, span: EvidenceSpan, paragraph: ReadingParagraph) -> bool:
    return (
        span.source_id == patch.source_id
        and span.raw_sha256 == paragraph.raw_sha256
        and 0 <= span.start < span.end <= len(paragraph.raw)
        and span.start <= patch.start <= patch.end <= span.end
    )


def _check_disputed(patches: list[ReadingPatch], uncertain: list[UncertainReading]) -> None:
    for patch in patches:
        if any(_overlaps(patch, span) for span in uncertain):
            raise ValueError("patch overlaps an uncertain span")
