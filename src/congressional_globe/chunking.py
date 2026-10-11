"""Page-bounded RAG chunk construction with stable citations."""

from __future__ import annotations

from congressional_globe.models import PageRecord, ParagraphRecord, RAGChunk, RAGParagraphSource


def chunk_page(page: PageRecord, max_characters: int = 4_000) -> list[RAGChunk]:
    substantive = [
        paragraph
        for paragraph in page.paragraphs
        if paragraph.role not in {"running_header", "page_number"}
    ]
    groups = _paragraph_groups(substantive, max_characters)
    return [_chunk(page, group, index) for index, group in enumerate(groups)]


def _paragraph_groups(paragraphs: list[ParagraphRecord], limit: int) -> list[list[ParagraphRecord]]:
    groups: list[list[ParagraphRecord]] = []
    current: list[ParagraphRecord] = []
    for paragraph in paragraphs:
        paragraph_length = len(_paragraph_text(paragraph))
        if current and _group_length(current) + paragraph_length + 2 > limit:
            groups.append(current)
            current = []
        current.append(paragraph)
    if current:
        groups.append(current)
    return groups


def _group_length(group: list[ParagraphRecord]) -> int:
    text_length = sum(len(_paragraph_text(paragraph)) for paragraph in group)
    return text_length + max(0, len(group) - 1) * 2


def _paragraph_text(paragraph: ParagraphRecord) -> str:
    if paragraph.text_normalized is not None:
        return paragraph.text_normalized
    return paragraph.text_ocr


def _chunk(page: PageRecord, group: list[ParagraphRecord], index: int) -> RAGChunk:
    page_value = page.printed_page.inferred or page.printed_page.detected or "unpaginated"
    citation = _citation(page, page_value, group)
    edition_date = _consistent_fact(group, "edition_date")
    chamber = _consistent_fact(group, "chamber")
    return RAGChunk(
        id=f"{page.id}:chunk:{index:04d}",
        text="\n\n".join(_paragraph_text(paragraph) for paragraph in group),
        item_identifier=page.item_identifier,
        part_number=page.part_number,
        scan_leaves=[page.scan_leaf],
        printed_pages=[page_value],
        paragraph_ids=[paragraph.id for paragraph in group],
        citation=citation,
        hocr_page_id=page.hocr_page_id,
        paragraph_sources=[_paragraph_source(page, paragraph) for paragraph in group],
        edition_date=edition_date[0] if edition_date else None,
        edition_date_source_paragraph_id=edition_date[1] if edition_date else None,
        edition_date_source_text=edition_date[2] if edition_date else None,
        chamber=chamber[0] if chamber else None,
        chamber_source_paragraph_id=chamber[1] if chamber else None,
        chamber_source_text=chamber[2] if chamber else None,
    )


def _paragraph_source(page: PageRecord, paragraph: ParagraphRecord) -> RAGParagraphSource:
    return RAGParagraphSource(
        paragraph_id=paragraph.id,
        item_identifier=page.item_identifier,
        part_number=page.part_number,
        scan_leaf=page.scan_leaf,
        printed_page=page.printed_page,
        hocr_page_id=page.hocr_page_id,
        hocr_line_ids=paragraph.line_ids,
        bbox=paragraph.bbox,
        role=paragraph.role,
        role_source=paragraph.role_source,
        context=paragraph.context,
        cleanup_status=paragraph.cleanup_status,
        static_edits=paragraph.static_edits,
        static_cleanup_provenance=paragraph.static_cleanup_provenance,
        ai_edits=paragraph.ai_edits,
        ai_provenance=paragraph.ai_provenance,
    )


def _consistent_fact(group: list[ParagraphRecord], key: str) -> tuple[str, str, str] | None:
    values = [_fact_value(paragraph, key) for paragraph in group]
    if not values or any(value is None for value in values):
        return None
    first = values[0]
    return first if all(value == first for value in values) else None


def _fact_value(paragraph: ParagraphRecord, key: str) -> tuple[str, str, str] | None:
    if _has_relevant_review_hint(paragraph, key):
        return None
    value = paragraph.context.get(key)
    source_id = paragraph.context.get(f"{key}_source_paragraph_id")
    source_text = paragraph.context.get(f"{key}_source_text")
    if not value or not source_id or not source_text:
        return None
    return value, source_id, source_text


def _has_relevant_review_hint(paragraph: ParagraphRecord, key: str) -> bool:
    hint = paragraph.context.get("review_hint", "").casefold()
    markers = ("date", "weekday") if key == "edition_date" else ("chamber",)
    return any(marker in hint for marker in markers)


def _citation(page: PageRecord, page_value: str, group: list[ParagraphRecord]) -> str:
    part = f", pt. {page.part_number}" if page.part_number else ""
    return (
        f"The Congressional Globe, 39th Cong., 1st Sess.{part}, p. {page_value}, "
        f"leaf {page.scan_leaf}, hOCR {page.hocr_page_id}, "
        f"paragraphs {', '.join(paragraph.id for paragraph in group)}"
    )
