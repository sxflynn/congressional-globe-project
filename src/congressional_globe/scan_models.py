"""Typed contracts for precise on-demand source-image crop requests."""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from congressional_globe.models import BoundingBox

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _positive_crop(region: CropRegion) -> bool:
    box = region.bbox
    return box.left < box.right and box.top < box.bottom


def _inside_frame(region: CropRegion, width: int, height: int) -> bool:
    box = region.bbox
    return box.left >= 0 and box.top >= 0 and box.right <= width and box.bottom <= height


def _valid_crop(region: CropRegion, width: int, height: int) -> bool:
    return _positive_crop(region) and _inside_frame(region, width, height)


class CropRegion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bbox: BoundingBox
    line_ids: list[NonBlank] = Field(default_factory=list)
    word_ids: list[NonBlank] = Field(default_factory=list)


class ScanTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_identifier: NonBlank
    part_number: int = Field(ge=1, le=5)
    scan_leaf: int = Field(ge=0)
    hocr_page_id: NonBlank
    paragraph_id: NonBlank
    printed_page: str | None = None
    raw_text: str = Field(min_length=1)
    raw_sha256: Sha256
    hocr_sha256: Sha256
    page_map_sha256: Sha256
    ocr_width: int = Field(gt=0)
    ocr_height: int = Field(gt=0)
    selection_start: int = Field(ge=0)
    selection_end: int = Field(gt=0)
    selection_text: str = Field(min_length=1)
    precision: Literal["paragraph", "word-span"]
    max_width: int = Field(ge=100, le=2000)
    regions: list[CropRegion] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_source_integrity(self) -> ScanTarget:
        if hashlib.sha256(self.raw_text.encode("utf-8")).hexdigest() != self.raw_sha256:
            raise ValueError("raw_sha256 does not match raw_text")
        if not 0 <= self.selection_start < self.selection_end <= len(self.raw_text):
            raise ValueError("selection offsets must be a nonempty in-bounds half-open span")
        if self.selection_text != self.raw_text[self.selection_start : self.selection_end]:
            raise ValueError("selection_text does not match raw_text offsets")
        if any(not _valid_crop(region, self.ocr_width, self.ocr_height) for region in self.regions):
            raise ValueError("crop regions must have positive area within the OCR frame")
        return self
