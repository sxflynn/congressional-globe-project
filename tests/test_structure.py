from __future__ import annotations

from congressional_globe.models import PageRecord, PrintedPage
from congressional_globe.structure import classify_page, needs_model


def _paragraph(identifier: str, text: str, top: int, bottom: int) -> dict[str, object]:
    return {
        "id": identifier,
        "reading_order": 0,
        "bbox": {"left": 100, "top": top, "right": 900, "bottom": bottom},
        "line_ids": [f"{identifier}-line"],
        "lines": [{"id": f"{identifier}-line", "text": text, "words": []}],
        "text_ocr": text,
    }


def _page(paragraphs: list[dict[str, object]], printed_page: str = "42") -> PageRecord:
    return PageRecord.model_validate(
        {
            "id": "ia:item:leaf:42",
            "item_identifier": "item",
            "scan_leaf": 42,
            "hocr_page_id": "page_000042",
            "image_width_px": 1000,
            "image_height_px": 5000,
            "printed_page": PrintedPage(detected=printed_page).model_dump(),
            "text_ocr": "\n\n".join(str(paragraph["text_ocr"]) for paragraph in paragraphs),
            "paragraphs": paragraphs,
        }
    )


def test_known_running_headers_and_matching_edge_page_number_are_classified() -> None:
    page = _page(
        [
            _paragraph("title", "THE CONGRESSIONAL GLOBE.", 100, 150),
            _paragraph("page", "42", 4850, 4890),
            _paragraph("body", "The Senate proceeded to business.", 800, 900),
            _paragraph("wrong", "43", 4800, 4840),
        ]
    )

    classified = classify_page(page)

    assert [paragraph.role for paragraph in classified.paragraphs] == [
        "running_header",
        "page_number",
        "body",
        "body",
    ]
    assert classified.paragraphs[0].role_source == "exact_header_pattern_and_edge_geometry"
    assert classified.paragraphs[1].role_source == "printed_page_match_and_edge_geometry"


def test_index_header_at_bottom_is_excluded_only_with_valid_geometry() -> None:
    page = _page(
        [
            _paragraph("index", "INDEX TO THE CONGRESSIONAL GLOBE.", 4850, 4890),
            {**_paragraph("unlocated", "THE CONGRESSIONAL GLOBE.", 100, 150), "bbox": None},
        ]
    )

    classified = classify_page(page)

    assert classified.paragraphs[0].role == "running_header"
    assert classified.paragraphs[1].role == "body"


def test_explicit_calendar_date_and_chamber_keep_source_on_page_context() -> None:
    page = _page(
        [
            _paragraph("date", "MONDAY, December 4, 1865.", 120, 170),
            _paragraph("chamber", "HOUSE OF REPRESENTATIVES", 180, 230),
            _paragraph("speech", "The House then proceeded to business.", 800, 900),
        ]
    )

    classified = classify_page(page)
    speech = classified.paragraphs[2]

    assert speech.context["edition_date"] == "1865-12-04"
    assert speech.context["edition_date_source_paragraph_id"] == "date"
    assert speech.context["edition_date_source_text"] == "MONDAY, December 4, 1865."
    assert speech.context["chamber"] == "house_of_representatives"
    assert speech.context["chamber_source_paragraph_id"] == "chamber"
    assert speech.role == "body"


def test_invalid_or_weekday_conflicting_date_becomes_review_hint() -> None:
    page = _page([_paragraph("date", "WEDNESDAY, February 31, 1865.", 120, 170)])

    paragraph = classify_page(page).paragraphs[0]

    assert "edition_date" not in paragraph.context
    assert "Unvalidated date-like header" in paragraph.context["review_hint"]


def test_conflicting_explicit_header_dates_are_not_propagated() -> None:
    page = _page(
        [
            _paragraph("date-a", "MONDAY, December 4, 1865.", 120, 170),
            _paragraph("date-b", "TUESDAY, December 5, 1865.", 180, 230),
            _paragraph("speech", "Proceedings began.", 800, 900),
        ]
    )

    speech = classify_page(page).paragraphs[2]

    assert "edition_date" not in speech.context
    assert "Conflicting explicit edition_date headers" in speech.context["review_hint"]


def test_model_routing_only_flags_unresolved_wraps_and_suspicious_glyphs() -> None:
    clean = _paragraph("clean", "The bill—$5 under § 2 and £1.", 100, 150)
    suspicious = _paragraph("suspicious", "The bill cost €5.", 100, 150)
    clean_record = PageRecord.model_validate(
        {**_page([clean]).model_dump(mode="json"), "paragraphs": [clean]}
    ).paragraphs[0]
    suspicious_record = PageRecord.model_validate(
        {**_page([suspicious]).model_dump(mode="json"), "paragraphs": [suspicious]}
    ).paragraphs[0]
    unresolved_record = clean_record.model_copy(
        update={"unresolved_wrap_hints": [{"candidate": "gentlemen"}]}
    )
    header_record = unresolved_record.model_copy(update={"role": "running_header"})

    assert not needs_model(clean_record)
    assert needs_model(suspicious_record)
    assert needs_model(unresolved_record)
    assert not needs_model(header_record)


def test_empty_normalized_text_is_used_instead_of_falling_back_to_ocr() -> None:
    suspicious = _paragraph("suspicious", "The bill cost €5.", 100, 150)
    record = PageRecord.model_validate(
        {**_page([suspicious]).model_dump(mode="json"), "paragraphs": [suspicious]}
    ).paragraphs[0]

    assert needs_model(record.model_copy(update={"text_normalized": ""})) is False
    assert needs_model(record.model_copy(update={"text_normalized": None})) is True


def test_low_confidence_is_a_review_hint_without_automatic_model_routing() -> None:
    paragraph = _paragraph("uncertain", "A proposition.", 800, 900)
    paragraph["lines"] = [
        {
            "id": "uncertain-line",
            "text": "A proposition.",
            "words": [{"id": f"w{i}", "text": "word", "confidence": 10} for i in range(3)],
        }
    ]

    classified = classify_page(_page([paragraph])).paragraphs[0]

    assert "low OCR word confidence" in classified.context["review_hint"]
    assert not needs_model(classified)
