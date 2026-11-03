"""Conservative cross-column reading hypotheses; canonical paragraphs remain separate.

Geometry and text come from the same supplied page bytes. Passing these guards is
not proof of source fidelity: inspect the registered image before endorsing a join.
"""

import hashlib
from itertools import pairwise
from typing import Literal

from pydantic import BaseModel, ConfigDict

from congressional_globe.models import PageRecord, ParagraphRecord


class ContinuationPart(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_id: str
    raw_sha256: str
    raw_start: int
    raw_end: int
    reading_start: int
    reading_end: int


class ColumnReading(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["source_inspection_required"] = "source_inspection_required"
    page_sha256: str
    text: str
    parts: tuple[ContinuationPart, ContinuationPart]
    inserted_separator: Literal[" "] = " "
    separator_start: int


def _adjacent(page: PageRecord, first: str, second: str):
    paragraphs = sorted(page.paragraphs, key=lambda p: p.reading_order)
    if not _unique_order(paragraphs):
        return None
    for left, right in pairwise(paragraphs):
        if (left.id, right.id) == (first, second):
            return left, right
    return None


def _unique_order(paragraphs):
    ids = [p.id for p in paragraphs]
    orders = [p.reading_order for p in paragraphs]
    return len(set(ids)) == len(ids) and len(set(orders)) == len(orders)


def _column_boundary(page, left, right):
    if not page.image_width_px or not page.image_height_px or not left.bbox or not right.bbox:
        return False
    a, b = left.bbox, right.bbox
    return (
        a.right <= b.left < b.right <= page.image_width_px
        and a.top < a.bottom <= page.image_height_px
        and a.bottom >= page.image_height_px * 0.75
        and b.top <= page.image_height_px * 0.25
        and b.top < b.bottom < a.top
    )


def _text_boundary(left, right):
    a, b = left.text_ocr, right.text_ocr
    return (
        left.role == right.role == "body"
        and right.reading_order == left.reading_order + 1
        and bool(a.strip())
        and bool(b.strip())
        and a[-1:].isalpha()
        and b[:1].islower()
    )


def _part(page, paragraph: ParagraphRecord, offset: int):
    raw = paragraph.text_ocr
    return ContinuationPart(
        source_id=f"{page.item_identifier}:{page.scan_leaf}:{paragraph.id}",
        raw_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        raw_start=0,
        raw_end=len(raw),
        reading_start=offset,
        reading_end=offset + len(raw),
    )


def column_reading(page_bytes: bytes, first: str, second: str) -> ColumnReading | None:
    """Join only adjacent body fragments spanning bottom→top of successive columns.

    Keep every original character. The sole added space has no raw-source support.
    Headings, terminal punctuation, missing geometry and cross-page joins decline.
    """
    page = PageRecord.model_validate_json(page_bytes)
    pair = _adjacent(page, first, second)
    if pair is None:
        return None
    left, right = pair
    if not _column_boundary(page, left, right) or not _text_boundary(left, right):
        return None
    boundary = len(left.text_ocr)
    return ColumnReading(
        page_sha256=hashlib.sha256(page_bytes).hexdigest(),
        text=left.text_ocr + " " + right.text_ocr,
        parts=(_part(page, left, 0), _part(page, right, boundary + 1)),
        separator_start=boundary,
    )
