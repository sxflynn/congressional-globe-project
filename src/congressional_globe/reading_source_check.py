"""Recheck selected export paragraphs against immutable hOCR, without image requests."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from lxml import etree  # ty: ignore[unresolved-import]

from congressional_globe.extraction import _is_hocr_page, _page_record, _release_page, load_page_map
from congressional_globe.inventory import resolve_source_path, sha256_file
from congressional_globe.models import PageRecord
from congressional_globe.reading_contracts import ReadingCandidate, ReadingParagraph
from congressional_globe.reading_preparation import _Sources, source_paragraph


def _selected_pages(path: Path, page_map: dict, leaves: set[int]):
    tags = ("div", "{http://www.w3.org/1999/xhtml}div")
    parser = etree.iterparse(str(path), events=("end",), tag=tags, recover=True, huge_tree=True)
    for _, element in parser:
        if _is_hocr_page(element):
            yield from _selected_page(element, path, page_map, leaves)
            _release_page(element)


def _selected_page(element, path: Path, page_map: dict, leaves: set[int]):
    page_id = element.get("id", "")
    if page_id in {f"page_{leaf:06d}" for leaf in leaves}:
        yield _page_record(element, path.stem.removesuffix("_hocr"), page_map)


def verify_candidate_sources(candidates: list[ReadingCandidate], source_manifest: Path) -> dict:
    sources = _Sources.model_validate_json(source_manifest.read_text())
    wanted: dict[str, dict[str, ReadingParagraph]] = defaultdict(dict)
    for unit in candidates:
        for paragraph in [*unit.context_before, *unit.target, *unit.context_after]:
            wanted[paragraph.item_identifier][paragraph.source_id] = paragraph
    checked = []
    for source in sources.parts:
        checked.extend(_verify_item(source, wanted.pop(source.identifier, {})))
    if wanted:
        raise ValueError("missing source item")
    return dict(
        candidate_to_source_binding="verified",
        paragraph_count=len(checked),
        checked_source_ids=checked,
        source_manifest_sha256=sha256_file(source_manifest),
        visual_inspection="pending",
        provider_calls=0,
    )


def _verify_item(source, wanted: dict[str, ReadingParagraph]) -> list[str]:
    if not wanted:
        return []
    _verify_files(source)
    page_map = load_page_map(resolve_source_path(Path(source.page_map_path), relocated=True))
    leaves = {p.scan_leaf for p in wanted.values()}
    checked = []
    for page in _selected_pages(
        resolve_source_path(Path(source.hocr_path), relocated=True), page_map, leaves
    ):
        checked.extend(_verify_page(page, wanted))
    if wanted:
        raise ValueError("source paragraphs missing from original hOCR")
    return checked


def _verify_page(page: PageRecord, wanted: dict[str, ReadingParagraph]) -> list[str]:
    checked = []
    for paragraph in page.paragraphs:
        identity = f"{page.item_identifier}:{page.scan_leaf}:{paragraph.id}"
        expected = wanted.get(identity)
        if expected is not None:
            _verify_paragraph(page, paragraph, expected)
            wanted.pop(identity)
            checked.append(identity)
    return checked


def _verify_paragraph(page: PageRecord, paragraph, expected: ReadingParagraph) -> None:
    actual = source_paragraph(
        page,
        paragraph.model_copy(update={"text_normalized": paragraph.text_ocr, "static_edits": []}),
    )
    fields = (
        "raw",
        "raw_sha256",
        "bbox",
        "line_ids",
        "printed_page",
        "hocr_page_id",
        "reading_order",
    )
    if any(getattr(actual, field) != getattr(expected, field) for field in fields):
        raise ValueError(f"candidate differs from original hOCR/page map: {expected.source_id}")


def _verify_files(source) -> None:
    for path, expected in [
        (source.hocr_path, source.hocr_sha256),
        (source.page_map_path, source.page_map_sha256),
    ]:
        if sha256_file(resolve_source_path(Path(path), relocated=True)) != expected:
            raise ValueError("source file changed")
