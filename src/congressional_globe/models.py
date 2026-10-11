"""Validated data contracts for raw, canonical, and AI-derived records."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceKind(StrEnum):
    ARCHIVE_MAP = "archive_map"
    DIRECT_HEADER = "direct_header"
    PROPAGATED = "propagated"
    MANUAL_REVIEW = "manual_review"
    UNKNOWN = "unknown"


class BoundingBox(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    left: int = Field(ge=0)
    top: int = Field(ge=0)
    right: int = Field(ge=0)
    bottom: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> BoundingBox:
        if self.right < self.left or self.bottom < self.top:
            raise ValueError("bounding box coordinates must be ordered")
        return self


class ArchivePageMapEntry(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    leaf_num: int = Field(alias="leafNum", ge=0)
    page_number: str | int | None = Field(default=None, alias="pageNumber")
    confidence: int | None = Field(default=None, ge=0, le=100)


class ArchivePageMap(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    pages: list[ArchivePageMapEntry]


class PrintedPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    detected: str | None = None
    inferred: str | None = None
    source: SourceKind = SourceKind.UNKNOWN
    confidence: int | None = Field(default=None, ge=0, le=100)


class WordRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    text: str
    bbox: BoundingBox | None = None
    confidence: int | None = Field(default=None, ge=0, le=100)
    font_size: float | None = Field(default=None, gt=0)


class LineRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    bbox: BoundingBox | None = None
    text: str
    words: list[WordRecord]


class ParagraphRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    reading_order: int = Field(ge=0)
    bbox: BoundingBox | None = None
    line_ids: list[str]
    lines: list[LineRecord] = Field(default_factory=list)
    text_ocr: str
    text_normalized: str | None = None
    static_edits: list[TextEdit] = Field(default_factory=list)
    static_cleanup_provenance: dict[str, str] | None = None
    unresolved_wrap_hints: list[dict[str, str]] = Field(default_factory=list)
    role: str = "body"
    role_source: str | None = None
    context: dict[str, str] = Field(default_factory=dict)
    ai_edits: list[TextEdit] = Field(default_factory=list)
    ai_input_text: str | None = None
    ai_input_sha256: str | None = None
    cleanup_status: str | None = None
    ai_provenance: dict[str, Any] | None = None


class PageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    item_identifier: str
    part_number: int | None = Field(default=None, ge=1)
    scan_leaf: int = Field(ge=0)
    hocr_page_id: str
    image_width_px: int | None = Field(default=None, ge=1)
    image_height_px: int | None = Field(default=None, ge=1)
    dpi: int | None = Field(default=None, ge=1)
    printed_page: PrintedPage
    text_ocr: str
    text_normalized: str | None = None
    paragraphs: list[ParagraphRecord]


class TextEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)
    expected: str
    replacement: str
    reason: str
    confidence: float = Field(ge=0, le=1)


class CleanupResult(BaseModel):
    """Strict model output used to reconstruct normalized text from raw text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    edits: list[TextEdit]
    needs_image_review: bool
    review_reason: str | None = None


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return a schema that satisfies OpenAI strict structured outputs.

    Strict mode requires every object property to appear in ``required``; Pydantic
    omits properties that carry defaults, so promote them here for transport only.
    """
    schema = model.model_json_schema()
    _require_all_properties(schema)
    return schema


def _require_all_properties(node: Any) -> None:
    if isinstance(node, dict):
        _require_object_properties(node)
        children = node.values()
    elif isinstance(node, list):
        children = node
    else:
        return
    for child in children:
        _require_all_properties(child)


def _require_object_properties(node: dict[str, Any]) -> None:
    properties = node.get("properties")
    if node.get("type") == "object" and isinstance(properties, dict):
        node["required"] = list(properties)


class RAGChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    text: str
    item_identifier: str
    part_number: int | None
    scan_leaves: list[int]
    printed_pages: list[str]
    paragraph_ids: list[str]
    citation: str
    hocr_page_id: str | None = None
