"""Page-bounded RAG chunk construction with stable citations."""

from __future__ import annotations

from congressional_globe.models import PageRecord, ParagraphRecord, RAGChunk


def chunk_page(page: PageRecord, max_characters: int = 4_000) -> list[RAGChunk]:
    groups = _paragraph_groups(page.paragraphs, max_characters)
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
    )


def _citation(page: PageRecord, page_value: str, group: list[ParagraphRecord]) -> str:
    part = f", pt. {page.part_number}" if page.part_number else ""
    return (
        f"The Congressional Globe, 39th Cong., 1st Sess.{part}, p. {page_value}, "
        f"leaf {page.scan_leaf}, hOCR {page.hocr_page_id}, "
        f"paragraphs {', '.join(paragraph.id for paragraph in group)}"
    )
