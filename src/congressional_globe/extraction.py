"""Streaming extraction from Internet Archive hOCR and page maps."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

from lxml import etree  # ty: ignore[unresolved-import]

from congressional_globe.inventory import PARTS
from congressional_globe.models import (
    BoundingBox,
    LineRecord,
    PageRecord,
    ParagraphRecord,
    PrintedPage,
    SourceKind,
    WordRecord,
)

_BBOX = re.compile(r"bbox (\d+) (\d+) (\d+) (\d+)")
_PAGE = re.compile(r"ppageno (\d+)")
_DIMENSIONS = re.compile(r"bbox 0 0 (\d+) (\d+)")
_DPI = re.compile(r"scan_res (\d+)")
_CONFIDENCE = re.compile(r"x_wconf (\d+)")
_FONT_SIZE = re.compile(r"x_fsize ([\d.]+)")


def load_page_map(path: Path) -> dict[int, PrintedPage]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {entry["leafNum"]: _printed_page(entry) for entry in payload["pages"]}


def iter_pages(hocr_path: Path, page_map: dict[int, PrintedPage]) -> Iterator[PageRecord]:
    context = etree.iterparse(str(hocr_path), events=("end",), recover=True, huge_tree=True)
    for _, element in context:
        if _is_hocr_page(element):
            yield _page_record(element, hocr_path.stem.removesuffix("_hocr"), page_map)
            element.clear()


def _is_hocr_page(element: etree._Element) -> bool:
    return element.get("class") == "ocr_page"


def _page_record(
    element: etree._Element, identifier: str, page_map: dict[int, PrintedPage]
) -> PageRecord:
    title = element.get("title", "")
    scan_leaf = _int_match(_PAGE, title)
    width, height = _dimensions(title)
    paragraphs = _paragraphs(element)
    return PageRecord(
        id=f"ia:{identifier}:leaf:{scan_leaf}",
        item_identifier=identifier,
        part_number=PARTS.get(identifier),
        scan_leaf=scan_leaf,
        hocr_page_id=element.get("id", f"page_{scan_leaf:06d}"),
        image_width_px=width,
        image_height_px=height,
        dpi=_int_match(_DPI, title),
        printed_page=page_map.get(scan_leaf, PrintedPage()),
        text_ocr="\n\n".join(paragraph.text_ocr for paragraph in paragraphs),
        paragraphs=paragraphs,
    )


def _paragraphs(page: etree._Element) -> list[ParagraphRecord]:
    records = [
        _paragraph_record(element) for element in page.iter() if _has_class(element, "ocr_par")
    ]
    return _ordered(records)


def _paragraph_record(element: etree._Element) -> ParagraphRecord:
    lines = [_line_record(child) for child in element.iter() if _has_class(child, "ocr_line")]
    return ParagraphRecord(
        id=element.get("id", ""),
        reading_order=0,
        bbox=_bbox(element.get("title", "")),
        line_ids=[line.id for line in lines if line.id],
        lines=lines,
        text_ocr=_text(element),
    )


def _line_record(element: etree._Element) -> LineRecord:
    words = [_word_record(child) for child in element.iter() if _has_class(child, "ocrx_word")]
    return LineRecord(
        id=element.get("id", ""),
        bbox=_bbox(element.get("title", "")),
        text=_text(element),
        words=words,
    )


def _word_record(element: etree._Element) -> WordRecord:
    title = element.get("title", "")
    return WordRecord(
        id=element.get("id", ""),
        text=_text(element),
        bbox=_bbox(title),
        confidence=_int_match(_CONFIDENCE, title) if _CONFIDENCE.search(title) else None,
        font_size=_float_match(_FONT_SIZE, title),
    )


def _ordered(paragraphs: list[ParagraphRecord]) -> list[ParagraphRecord]:
    sortable = sorted(paragraphs, key=_sort_key)
    return [
        paragraph.model_copy(update={"reading_order": index})
        for index, paragraph in enumerate(sortable)
    ]


def _sort_key(paragraph: ParagraphRecord) -> tuple[int, int, int]:
    if paragraph.bbox is None:
        return (2, 0, paragraph.reading_order)
    column = 0 if paragraph.bbox.left < 1600 else 1
    return (column, paragraph.bbox.top, paragraph.bbox.left)


def _printed_page(entry: dict[str, object]) -> PrintedPage:
    number = str(entry.get("pageNumber") or "") or None
    return PrintedPage(
        detected=number,
        source=SourceKind.ARCHIVE_MAP if number else SourceKind.UNKNOWN,
        confidence=_as_int(entry.get("confidence")),
    )


def _dimensions(title: str) -> tuple[int | None, int | None]:
    match = _DIMENSIONS.search(title)
    return (int(match.group(1)), int(match.group(2))) if match else (None, None)


def _int_match(pattern: re.Pattern[str], value: str) -> int:
    match = pattern.search(value)
    return int(match.group(1)) if match else 0


def _float_match(pattern: re.Pattern[str], value: str) -> float | None:
    match = pattern.search(value)
    return float(match.group(1)) if match else None


def _bbox(title: str) -> BoundingBox | None:
    match = _BBOX.search(title)
    if match is None:
        return None
    return BoundingBox(
        left=int(match.group(1)),
        top=int(match.group(2)),
        right=int(match.group(3)),
        bottom=int(match.group(4)),
    )


def _has_class(element: etree._Element, name: str) -> bool:
    return name in element.get("class", "").split()


def _text(element: etree._Element) -> str:
    return " ".join("".join(element.itertext()).split())


def _as_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
