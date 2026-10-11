from __future__ import annotations

import json
from pathlib import Path

import pytest

from congressional_globe.ai import SYSTEM_PROMPT, prepare_batch, reconcile_batch
from congressional_globe.chunking import chunk_page
from congressional_globe.extraction import iter_pages, load_page_map
from congressional_globe.models import (
    CleanupResult,
    PageRecord,
    PrintedPage,
    TextEdit,
    strict_json_schema,
)
from congressional_globe.normalization import apply_edits, resolve_edits, validate_edit_shapes
from congressional_globe.static_cleanup import normalize_jsonl, normalize_line_wraps
from congressional_globe.storage import (
    claim_next,
    complete_job,
    create_run,
    progress,
    retry_job,
    retry_review_jobs,
    run_summary,
)


def test_extraction_preserves_hocr_ids_geometry_and_page_map(tmp_path: Path) -> None:
    hocr_path = tmp_path / "example_hocr.html"
    map_path = tmp_path / "example_page_numbers.json"
    hocr_path.write_text(_hocr(), encoding="utf-8")
    map_path.write_text(
        json.dumps({"pages": [{"leafNum": 1, "pageNumber": "42", "confidence": 99}]})
    )

    page = next(iter_pages(hocr_path, load_page_map(map_path)))

    assert page.hocr_page_id == "page_000001"
    assert page.printed_page.detected == "42"
    assert page.paragraphs[0].id == "par_right"
    assert page.paragraphs[0].bbox is not None
    assert page.paragraphs[0].bbox.left == 1800
    assert page.paragraphs[1].id == "par_left"
    assert [paragraph.reading_order for paragraph in page.paragraphs] == [0, 1]


def test_extraction_retains_word_geometry_and_confidence(tmp_path: Path) -> None:
    hocr_path = tmp_path / "example_hocr.html"
    hocr_path.write_text(_hocr_with_words(), encoding="utf-8")

    page = next(iter_pages(hocr_path, {}))
    word = page.paragraphs[0].lines[0].words[0]

    assert word.id == "word_1"
    assert word.text == "exam-"
    assert word.confidence == 87
    assert word.bbox is not None and word.bbox.left == 10


def test_static_cleanup_joins_only_lexicon_supported_line_wraps() -> None:
    page = PageRecord.model_validate(
        {
            "id": "i:leaf:1",
            "item_identifier": "i",
            "scan_leaf": 1,
            "hocr_page_id": "page_1",
            "printed_page": {},
            "text_ocr": "exam- ple text",
            "paragraphs": [
                {
                    "id": "p1",
                    "reading_order": 0,
                    "line_ids": ["l1", "l2"],
                    "text_ocr": "exam- ple text",
                    "lines": [
                        {"id": "l1", "text": "exam-", "words": []},
                        {"id": "l2", "text": "ple text", "words": []},
                    ],
                }
            ],
        }
    )

    paragraph = page.paragraphs[0]
    normalized, edits = normalize_line_wraps(paragraph, {"example"})
    untouched, no_edits = normalize_line_wraps(paragraph, {"exam", "ple"})

    assert normalized == "example text"
    assert edits[0].expected == "exam- ple"
    assert untouched == paragraph.text_ocr
    assert no_edits == []


def test_static_cleanup_cli_payload_preserves_source_and_page_metadata(tmp_path: Path) -> None:
    paragraphs = tmp_path / "paragraphs.jsonl"
    lexicon = tmp_path / "words.txt"
    output = tmp_path / "normalized.jsonl"
    paragraphs.write_text(
        json.dumps(
            {
                "id": "p1",
                "reading_order": 0,
                "line_ids": ["l1", "l2"],
                "text_ocr": "exam- ple",
                "lines": [
                    {"id": "l1", "text": "exam-", "words": []},
                    {"id": "l2", "text": "ple", "words": []},
                ],
                "item_identifier": "part-one",
                "part_number": 1,
                "scan_leaf": 12,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    lexicon.write_text("example\n", encoding="utf-8")

    assert normalize_jsonl(paragraphs, lexicon, output) == 1
    result = json.loads(output.read_text(encoding="utf-8"))

    assert result["text_ocr"] == "exam- ple"
    assert result["text_normalized"] == "example"
    assert result["scan_leaf"] == 12
    assert result["static_edits"][0]["expected"] == "exam- ple"


def test_patch_application_is_reversible_and_rejects_bad_source() -> None:
    edit = TextEdit(
        start_char=3,
        end_char=6,
        expected="bad",
        replacement="good",
        reason="test",
        confidence=1,
    )

    assert apply_edits("A: bad", [edit]) == "A: good"
    with pytest.raises(ValueError, match="does not match"):
        apply_edits("A: typo", [edit])


def test_edit_shape_validator_rejects_punctuation_and_numeric_only_changes() -> None:
    punctuation = TextEdit(
        start_char=0,
        end_char=3,
        expected="an,",
        replacement="an",
        reason="fixture",
        confidence=0.9,
    )
    numeric = TextEdit(
        start_char=0,
        end_char=4,
        expected="1865",
        replacement="1866",
        reason="fixture",
        confidence=0.9,
    )

    with pytest.raises(ValueError, match="punctuation-only"):
        validate_edit_shapes("an,", [punctuation])
    with pytest.raises(ValueError, match="numeric-only"):
        validate_edit_shapes("1865", [numeric])


def test_edit_shape_validator_allows_word_repairs_and_hyphen_joins() -> None:
    lexical = TextEdit(
        start_char=0,
        end_char=3,
        expected="ihc",
        replacement="the",
        reason="fixture",
        confidence=0.9,
    )
    wrapped = TextEdit(
        start_char=4,
        end_char=10,
        expected="exam- ple",
        replacement="example",
        reason="fixture",
        confidence=0.9,
    )

    validate_edit_shapes("ihc exam- ple", [lexical, wrapped])


def test_chunk_keeps_page_bounded_citation() -> None:
    page = PageRecord.model_validate(
        {
            "id": "ia:item:leaf:1",
            "item_identifier": "item",
            "part_number": 1,
            "scan_leaf": 1,
            "hocr_page_id": "page_000001",
            "printed_page": PrintedPage(detected="1").model_dump(),
            "text_ocr": "Alpha",
            "paragraphs": [{"id": "p1", "reading_order": 0, "line_ids": [], "text_ocr": "Alpha"}],
        }
    )

    chunk = chunk_page(page)[0]

    assert chunk.scan_leaves == [1]
    assert "pt. 1" in chunk.citation
    assert chunk.paragraph_ids == ["p1"]


def test_prepare_ai_writes_stable_batch_request(tmp_path: Path) -> None:
    paragraphs = tmp_path / "paragraphs.jsonl"
    requests = tmp_path / "requests.jsonl"
    paragraphs.write_text(json.dumps({"id": "p1", "text_ocr": "raw text"}) + "\n")

    count = prepare_batch(paragraphs, requests, "test-model")
    request = json.loads(requests.read_text())

    assert count == 1
    assert request["custom_id"] == "p1"
    assert request["url"] == "/v1/responses"
    assert request["body"]["text"]["format"]["strict"] is True


def test_strict_schema_requires_every_property_for_openai() -> None:
    schema = strict_json_schema(CleanupResult)

    assert schema["required"] == ["edits", "needs_image_review", "review_reason"]
    assert schema["additionalProperties"] is False
    assert set(schema["$defs"]["TextEdit"]["required"]) == set(
        schema["$defs"]["TextEdit"]["properties"]
    )


def test_cleanup_prompt_authorizes_clear_line_wrap_repairs() -> None:
    assert "him- self' becomes 'himself'" in SYSTEM_PROMPT
    assert "expected must exactly reproduce the source substring" in SYSTEM_PROMPT


def test_unique_source_anchor_recovers_an_inaccurate_model_offset() -> None:
    text = "Availing him- self of that occasion."
    edit = TextEdit(
        start_char=0,
        end_char=9,
        expected="him- self",
        replacement="himself",
        reason="line wrap",
        confidence=1,
    )

    resolved = resolve_edits(text, [edit])

    assert resolved[0].start_char == 9
    assert apply_edits(text, resolved) == "Availing himself of that occasion."


def test_reconcile_ai_applies_validated_patch_and_queues_invalid_result(tmp_path: Path) -> None:
    paragraphs = tmp_path / "paragraphs.jsonl"
    output = tmp_path / "output.jsonl"
    review = tmp_path / "review.jsonl"
    batch_output = tmp_path / "batch.jsonl"
    paragraphs.write_text('{"id":"p1","text_ocr":"Congrefs"}\n')
    cleanup = {
        "edits": [
            {
                "start_char": 6,
                "end_char": 7,
                "expected": "f",
                "replacement": "s",
                "reason": "clear OCR long-s",
                "confidence": 0.99,
            }
        ],
        "needs_image_review": False,
        "review_reason": None,
    }
    successful = {
        "custom_id": "p1",
        "response": {
            "body": {
                "output": [{"content": [{"type": "output_text", "text": json.dumps(cleanup)}]}]
            }
        },
    }
    failed = {"custom_id": "missing", "response": {"body": {"output": []}}}
    batch_output.write_text("\n".join([json.dumps(successful), json.dumps(failed)]) + "\n")

    counts = reconcile_batch(batch_output, paragraphs, output, review)

    assert counts == {"accepted": 1, "review": 1}
    assert json.loads(output.read_text())["text_normalized"] == "Congress"
    assert json.loads(review.read_text())["custom_id"] == "missing"


def test_cleanup_queue_is_resumable(tmp_path: Path) -> None:
    paragraphs = tmp_path / "paragraphs.jsonl"
    database = tmp_path / "jobs.sqlite"
    paragraphs.write_text('{"id":"p1","scan_leaf":1,"text_ocr":"Congress"}\n')

    assert create_run(database, "run-1", paragraphs) == 1
    job = claim_next(database, "run-1", "ollama", "test-model")

    assert job is not None
    assert job.paragraph_id == "p1"
    assert progress(database, "run-1") == {"claimed": 1, "total": 1}


def test_connection_failure_is_retryable_but_review_requires_explicit_retry(tmp_path: Path) -> None:
    paragraphs = tmp_path / "paragraphs.jsonl"
    database = tmp_path / "jobs.sqlite"
    paragraphs.write_text('{"id":"p1","scan_leaf":1,"text_ocr":"Congress"}\n')
    create_run(database, "run-1", paragraphs)
    job = claim_next(database, "run-1", "ollama", "test-model")

    assert job is not None
    retry_job(database, job.id, "Connection error.", 3)
    assert progress(database, "run-1") == {"pending": 1, "total": 1}
    assert retry_review_jobs(database, "run-1") == 0


def test_run_summary_reports_progress_and_eta(tmp_path: Path) -> None:
    paragraphs = tmp_path / "paragraphs.jsonl"
    database = tmp_path / "jobs.sqlite"
    paragraphs.write_text('{"id":"p1","scan_leaf":1,"text_ocr":"Congress"}\n')
    create_run(database, "run-1", paragraphs)
    job = claim_next(database, "run-1", "ollama", "test-model")

    assert job is not None
    complete_job(database, job.id, {"text_normalized": "Congress"}, 1_000)

    assert run_summary(database, "run-1") == {
        "completed": 1,
        "pending": 0,
        "claimed": 0,
        "review": 0,
        "total": 1,
        "remaining": 0,
        "percent_complete": 100.0,
        "average_completed_seconds": 1.0,
        "estimated_remaining_hours": 0.0,
    }


def _hocr() -> str:
    return "\n".join(
        [
            '<?xml version="1.0"?>',
            '<html xmlns="http://www.w3.org/1999/xhtml"><body>',
            '<div class="ocr_page" id="page_000001"',
            ' title="bbox 0 0 3200 4300; ppageno 1; scan_res 400 400">',
            '  <p class="ocr_par" id="par_right" title="bbox 1800 200 3000 300">',
            '    <span class="ocr_line" id="line_right">Right column.</span></p>',
            '  <p class="ocr_par" id="par_left" title="bbox 100 200 1400 300">',
            '    <span class="ocr_line" id="line_left">Left column.</span></p>',
            "</div></body></html>",
        ]
    )


def _hocr_with_words() -> str:
    return (
        '<html><body><div class="ocr_page" id="page_1" '
        'title="bbox 0 0 100 100; ppageno 1; scan_res 300 300">'
        '<p class="ocr_par" id="p1"><span class="ocr_line" id="l1" '
        'title="bbox 5 5 60 20"><span class="ocrx_word" id="word_1" '
        'title="bbox 10 5 40 20; x_wconf 87; x_fsize 12">exam-</span></span></p>'
        "</div></body></html>"
    )
