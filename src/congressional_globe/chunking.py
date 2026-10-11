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
        if current and _group_length(current) + len(paragraph.text_ocr) + 2 > limit:
            groups.append(current)
            current = []
        current.append(paragraph)
    if current:
        groups.append(current)
    return groups


def _group_length(group: list[ParagraphRecord]) -> int:
    return sum(len(paragraph.text_ocr) + 2 for paragraph in group)


def _chunk(page: PageRecord, group: list[ParagraphRecord], index: int) -> RAGChunk:
    page_value = page.printed_page.inferred or page.printed_page.detected or "unpaginated"
    citation = _citation(page, page_value)
    return RAGChunk(
        id=f"{page.id}:chunk:{index:04d}",
        text="\n\n".join(paragraph.text_normalized or paragraph.text_ocr for paragraph in group),
        item_identifier=page.item_identifier,
        part_number=page.part_number,
        scan_leaves=[page.scan_leaf],
        printed_pages=[page_value],
        paragraph_ids=[paragraph.id for paragraph in group],
        citation=citation,
    )


def _citation(page: PageRecord, page_value: str) -> str:
    part = f", pt. {page.part_number}" if page.part_number else ""
    return (
        f"The Congressional Globe, 39th Cong., 1st Sess.{part}, p. {page_value}, "
        f"leaf {page.scan_leaf}"
    )
