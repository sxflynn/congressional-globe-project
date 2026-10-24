"""Resolve exact OCR text selections to source hOCR crop geometry."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from congressional_globe.extraction import iter_pages, load_page_map
from congressional_globe.inventory import PARTS, expected_paths
from congressional_globe.models import BoundingBox, PageRecord, ParagraphRecord, WordRecord
from congressional_globe.scan_models import CropRegion, ScanTarget


@dataclass(frozen=True)
class _WordPosition:
    line_id: str
    word: WordRecord
    start: int
    end: int


def _file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _validate_limits(padding: int, max_width: int, leaf: int) -> None:
    if not 0 <= padding <= 256:
        raise ValueError("padding must be between 0 and 256 pixels")
    if not 100 <= max_width <= 2000:
        raise ValueError("max_width must be between 100 and 2000 pixels")
    if leaf < 0:
        raise ValueError("scan leaf must be nonnegative")


def prepare_target(
    root: Path,
    item: str,
    leaf: int,
    paragraph_id: str,
    start: int | None = None,
    end: int | None = None,
    padding: int = 64,
    max_width: int = 1600,
) -> ScanTarget:
    """Prepare a source-anchored crop target without retrieving any image data."""
    if item not in PARTS:
        raise ValueError(f"unsupported Internet Archive item {item!r}")
    _validate_limits(padding, max_width, leaf)
    paths = expected_paths(root, item)
    hocr_hash = _file_sha256(paths["hocr.html"])
    page_map_hash = _file_sha256(paths["page_numbers.json"])
    page_map = load_page_map(paths["page_numbers.json"])
    pages = iter_pages(paths["hocr.html"], page_map)
    page = next((candidate for candidate in pages if candidate.scan_leaf == leaf), None)
    if page is None:
        raise KeyError(f"scan leaf {leaf} is absent from {item}")
    return target_from_page(
        page,
        paragraph_id,
        hocr_hash,
        page_map_hash,
        start,
        end,
        padding,
        max_width,
    )


def target_from_page(
    page: PageRecord,
    paragraph_id: str,
    hocr_sha256: str,
    page_map_sha256: str,
    start: int | None = None,
    end: int | None = None,
    padding: int = 64,
    max_width: int = 1600,
) -> ScanTarget:
    """Build and validate a crop target from one already parsed page."""
    _validate_limits(padding, max_width, page.scan_leaf)
    paragraph = _find_paragraph(page, paragraph_id)
    width, height = _frame(page)
    selection_start, selection_end = _selection_bounds(paragraph, start, end)
    raw_text = paragraph.text_ocr
    selection_text = raw_text[selection_start:selection_end]
    if not selection_text.strip():
        raise ValueError("selection must include non-whitespace source text")
    if start is None and end is None:
        regions = [_paragraph_region(paragraph, width, height, padding)]
        precision = "paragraph"
    else:
        regions = _word_regions(paragraph, selection_start, selection_end, width, height, padding)
        precision = "word-span"
    printed = page.printed_page.detected or page.printed_page.inferred
    return ScanTarget(
        item_identifier=page.item_identifier,
        part_number=PARTS[page.item_identifier],
        scan_leaf=page.scan_leaf,
        hocr_page_id=page.hocr_page_id,
        paragraph_id=paragraph.id,
        printed_page=printed,
        raw_text=raw_text,
        raw_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        hocr_sha256=hocr_sha256,
        page_map_sha256=page_map_sha256,
        ocr_width=width,
        ocr_height=height,
        selection_start=selection_start,
        selection_end=selection_end,
        selection_text=selection_text,
        precision=precision,
        max_width=max_width,
        regions=regions,
    )


def _find_paragraph(page: PageRecord, paragraph_id: str) -> ParagraphRecord:
    _validate_page_identity(page)
    matches = [paragraph for paragraph in page.paragraphs if paragraph.id == paragraph_id]
    if len(matches) != 1:
        raise KeyError(f"paragraph {paragraph_id!r} is not unique on this source page")
    return matches[0]


def _validate_page_identity(page: PageRecord) -> None:
    expected_part = PARTS.get(page.item_identifier)
    if expected_part is None:
        raise ValueError("source page has no supported part identity")
    if page.part_number != expected_part:
        raise ValueError("source page item and part identity disagree")


def _frame(page: PageRecord) -> tuple[int, int]:
    if page.image_width_px is None or page.image_height_px is None:
        raise ValueError("source page has no usable OCR coordinate frame")
    return page.image_width_px, page.image_height_px


def _selection_bounds(
    paragraph: ParagraphRecord, start: int | None, end: int | None
) -> tuple[int, int]:
    if start is None and end is None:
        return 0, len(paragraph.text_ocr)
    if start is None or end is None:
        raise ValueError("selection start and end must be supplied together")
    return _validate_selection(paragraph.text_ocr, start, end)


def _validate_selection(text: str, start: int, end: int) -> tuple[int, int]:
    if start < 0 or end > len(text) or start >= end:
        raise ValueError("selection must be a nonempty in-bounds half-open span")
    return start, end


def _validate_box(box: BoundingBox | None, width: int, height: int) -> BoundingBox:
    if box is None:
        raise ValueError("required source OCR bounding box is missing")
    if box.right <= box.left or box.bottom <= box.top:
        raise ValueError("source OCR bounding box has zero or inverted area")
    if box.right > width or box.bottom > height:
        raise ValueError("source OCR bounding box exceeds the OCR coordinate frame")
    return box


def _padded_box(box: BoundingBox, width: int, height: int, padding: int) -> BoundingBox:
    return BoundingBox(
        left=max(0, box.left - padding),
        top=max(0, box.top - padding),
        right=min(width, box.right + padding),
        bottom=min(height, box.bottom + padding),
    )


def _paragraph_region(
    paragraph: ParagraphRecord, width: int, height: int, padding: int
) -> CropRegion:
    box = _validate_box(paragraph.bbox, width, height)
    return CropRegion(
        bbox=_padded_box(box, width, height, padding),
        line_ids=[line.id for line in paragraph.lines if line.id],
        word_ids=[word.id for line in paragraph.lines for word in line.words if word.id.strip()],
    )


def _line_words(line) -> list[tuple[WordRecord, str]]:
    if not line.id:
        raise ValueError("source OCR line has no ID")
    words = [(word, word.text.strip()) for word in line.words if word.text.strip()]
    if " ".join(text for _, text in words) != line.text:
        raise ValueError(f"hOCR words do not reconstruct source line {line.id!r}")
    return words


def _position_line_words(
    line_id: str,
    words: list[tuple[WordRecord, str]],
    cursor: int,
    first_line: bool,
) -> tuple[list[_WordPosition], int]:
    if not first_line:
        cursor += 1
    positions = []
    for index, (word, text) in enumerate(words):
        if index:
            cursor += 1
        positions.append(_WordPosition(line_id, word, cursor, cursor + len(text)))
        cursor += len(text)
    return positions, cursor


def _word_positions(paragraph: ParagraphRecord) -> list[_WordPosition]:
    positions = []
    line_texts = []
    cursor = 0
    for line in paragraph.lines:
        words = _line_words(line)
        located, cursor = _position_line_words(line.id, words, cursor, not line_texts)
        positions.extend(located)
        line_texts.append(" ".join(text for _, text in words))
    if " ".join(line_texts) != paragraph.text_ocr:
        raise ValueError("hOCR lines do not exactly reconstruct the source paragraph")
    return positions


def _union(boxes: list[BoundingBox]) -> BoundingBox:
    return BoundingBox(
        left=min(box.left for box in boxes),
        top=min(box.top for box in boxes),
        right=max(box.right for box in boxes),
        bottom=max(box.bottom for box in boxes),
    )


def _word_regions(
    paragraph: ParagraphRecord,
    start: int,
    end: int,
    width: int,
    height: int,
    padding: int,
) -> list[CropRegion]:
    positions = _word_positions(paragraph)
    selected = [position for position in positions if position.start < end and position.end > start]
    if not selected:
        raise ValueError("selection does not overlap any source OCR word")
    return _regions_by_line(selected, width, height, padding)


def _regions_by_line(
    selected: list[_WordPosition], width: int, height: int, padding: int
) -> list[CropRegion]:
    by_line: dict[str, list[WordRecord]] = defaultdict(list)
    for position in selected:
        by_line[position.line_id].append(position.word)
    return [
        _line_region(line_id, words, width, height, padding) for line_id, words in by_line.items()
    ]


def _line_region(
    line_id: str, words: list[WordRecord], width: int, height: int, padding: int
) -> CropRegion:
    boxes = [_validate_box(word.bbox, width, height) for word in words]
    return CropRegion(
        bbox=_padded_box(_union(boxes), width, height, padding),
        line_ids=[line_id],
        word_ids=[word.id for word in words if word.id.strip()],
    )
