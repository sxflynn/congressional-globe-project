from __future__ import annotations

from congressional_globe.chunking import chunk_page
from congressional_globe.models import PageRecord


def _page(paragraphs: list[dict[str, object]]) -> PageRecord:
    return PageRecord.model_validate(
        {
            "id": "ia:item:leaf:12",
            "item_identifier": "item",
            "part_number": 2,
            "scan_leaf": 12,
            "hocr_page_id": "page_000012",
            "printed_page": {"detected": "44", "source": "archive_map"},
            "text_ocr": "\n\n".join(str(item["text_ocr"]) for item in paragraphs),
            "paragraphs": paragraphs,
        }
    )


def _paragraph(identifier: str, text: str, context: dict[str, str]) -> dict[str, object]:
    return {
        "id": identifier,
        "reading_order": 0,
        "bbox": {"left": 10, "top": 20, "right": 100, "bottom": 40},
        "line_ids": [f"line-{identifier}"],
        "lines": [],
        "text_ocr": text,
        "text_normalized": text,
        "context": context,
        "cleanup_status": "unchanged",
    }


def _facts() -> dict[str, str]:
    return {
        "edition_date": "1865-12-04",
        "edition_date_source_paragraph_id": "date-header",
        "edition_date_source_text": "MONDAY, December 4, 1865.",
        "chamber": "senate",
        "chamber_source_paragraph_id": "chamber-header",
        "chamber_source_text": "SENATE",
    }


def test_chunk_preserves_paragraph_source_cleanup_and_consistent_context_facts() -> None:
    page = _page(
        [_paragraph("p1", "First paragraph.", _facts()), _paragraph("p2", "Second.", _facts())]
    )

    chunk = chunk_page(page)[0]

    assert chunk.edition_date == "1865-12-04"
    assert chunk.edition_date_source_paragraph_id == "date-header"
    assert chunk.edition_date_source_text == "MONDAY, December 4, 1865."
    assert chunk.chamber == "senate"
    assert chunk.chamber_source_paragraph_id == "chamber-header"
    assert len(chunk.paragraph_sources) == 2
    source = chunk.paragraph_sources[0]
    assert source.hocr_line_ids == ["line-p1"]
    assert source.bbox is not None and source.bbox.left == 10
    assert source.printed_page.detected == "44"
    assert source.context["edition_date_source_text"] == "MONDAY, December 4, 1865."
    assert source.cleanup_status == "unchanged"


def test_chunk_suppresses_conflicting_or_reviewed_context_facts() -> None:
    first = _facts()
    second = {
        **_facts(),
        "edition_date": "1865-12-05",
        "review_hint": "edition_date: conflicting headers",
    }
    page = _page([_paragraph("p1", "First.", first), _paragraph("p2", "Second.", second)])

    chunk = chunk_page(page)[0]

    assert chunk.edition_date is None
    assert chunk.edition_date_source_paragraph_id is None
    assert chunk.chamber == "senate"


def test_legacy_rag_chunk_defaults_allow_missing_provenance() -> None:
    from congressional_globe.models import RAGChunk

    chunk = RAGChunk(
        id="legacy",
        text="Text",
        item_identifier="item",
        part_number=None,
        scan_leaves=[1],
        printed_pages=["unpaginated"],
        paragraph_ids=["p"],
        citation="citation",
    )

    assert chunk.paragraph_sources == []
    assert chunk.edition_date is None
    assert chunk.chamber is None
