"""Tests for canonical page merging and RAG JSONL export."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from congressional_globe.models import PageRecord
from congressional_globe.pipeline import build_rag_from_pages, merge_normalized_paragraphs


def test_build_rag_uses_normalized_text_and_cites_source_anchors(tmp_path: Path) -> None:
    pages = tmp_path / "pages.jsonl"
    chunks = tmp_path / "chunks.jsonl"
    _write_jsonl(pages, [_page_payload([_paragraph("p1", "raw", "")])])

    assert build_rag_from_pages(pages, chunks, max_characters=1) == 1

    chunk = _read_jsonl(chunks)[0]
    assert chunk["text"] == ""
    assert chunk["hocr_page_id"] == "page_000001"
    assert "hOCR page_000001" in chunk["citation"]
    assert "paragraphs p1" in chunk["citation"]


def test_chunk_limit_counts_emitted_normalized_text(tmp_path: Path) -> None:
    pages = tmp_path / "pages.jsonl"
    chunks = tmp_path / "chunks.jsonl"
    paragraphs = [
        _paragraph("p1", "raw text longer", "a"),
        _paragraph("p2", "raw text longer", "b"),
    ]
    _write_jsonl(pages, [_page_payload(paragraphs)])

    assert build_rag_from_pages(pages, chunks, max_characters=4) == 1
    assert _read_jsonl(chunks)[0]["text"] == "a\n\nb"


def test_merge_normalized_paragraphs_preserves_raw_and_static_ledger(tmp_path: Path) -> None:
    pages = tmp_path / "pages.jsonl"
    normalized = tmp_path / "normalized.jsonl"
    output = tmp_path / "merged.jsonl"
    page = _page_payload([_paragraph("p1", "raw", "joined")])
    derived = _paragraph("p1", "raw", "joined")
    derived["item_identifier"] = "item-1"
    derived["scan_leaf"] = 1
    derived["static_edits"] = [
        {
            "start_char": 0,
            "end_char": 3,
            "expected": "raw",
            "replacement": "joined",
            "reason": "test",
            "confidence": 0.98,
        }
    ]
    derived["static_cleanup_provenance"] = {"pipeline_version": "test-v1"}
    derived["unresolved_wrap_hints"] = [{"left": "unknown-", "right": "word"}]
    _write_jsonl(pages, [page])
    _write_jsonl(normalized, [derived])

    assert merge_normalized_paragraphs(pages, normalized, output) == 1

    merged = PageRecord.model_validate(_read_jsonl(output)[0])
    paragraph = merged.paragraphs[0]
    assert paragraph.text_ocr == "raw"
    assert paragraph.text_normalized == "joined"
    assert merged.text_normalized == "joined"
    assert paragraph.model_dump(mode="json")["static_edits"] == derived["static_edits"]
    assert paragraph.static_cleanup_provenance == derived["static_cleanup_provenance"]
    assert paragraph.unresolved_wrap_hints == derived["unresolved_wrap_hints"]


@pytest.mark.parametrize("failure", ["duplicate", "missing", "mismatch", "extra"])
def test_merge_rejects_incomplete_or_inconsistent_inputs(tmp_path: Path, failure: str) -> None:
    pages = tmp_path / "pages.jsonl"
    normalized = tmp_path / "normalized.jsonl"
    output = tmp_path / "merged.jsonl"
    page_paragraphs = [_paragraph("p1", "raw", "one"), _paragraph("p2", "raw2", "two")]
    records = [_normalized_payload("p1", "raw", "one", leaf=1)]
    if failure == "duplicate":
        records.append(_normalized_payload("p1", "raw", "one", leaf=1))
    elif failure == "missing":
        pass
    elif failure == "mismatch":
        records[0]["text_ocr"] = "different"
        records.append(_normalized_payload("p2", "raw2", "two", leaf=1))
    else:
        records.append(_normalized_payload("p2", "raw2", "two", leaf=2))
    _write_jsonl(pages, [_page_payload(page_paragraphs)])
    _write_jsonl(normalized, records)

    with pytest.raises(ValueError):
        merge_normalized_paragraphs(pages, normalized, output)


def test_invalid_static_ledger_keeps_existing_output_unchanged(tmp_path: Path) -> None:
    pages = tmp_path / "pages.jsonl"
    normalized = tmp_path / "normalized.jsonl"
    output = tmp_path / "merged.jsonl"
    derived = _normalized_payload("p1", "raw", "incorrect", leaf=1)
    derived["static_edits"] = []
    _write_jsonl(pages, [_page_payload([_paragraph("p1", "raw", None)])])
    _write_jsonl(normalized, [derived])
    output.write_text("previous output\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Static edit ledger"):
        merge_normalized_paragraphs(pages, normalized, output)

    assert output.read_text(encoding="utf-8") == "previous output\n"


def test_merge_rejects_hard_link_output_alias(tmp_path: Path) -> None:
    pages = tmp_path / "pages.jsonl"
    normalized = tmp_path / "normalized.jsonl"
    output = tmp_path / "pages-alias.jsonl"
    _write_jsonl(pages, [_page_payload([])])
    _write_jsonl(normalized, [])
    os.link(pages, output)

    with pytest.raises(ValueError, match="aliases an input"):
        merge_normalized_paragraphs(pages, normalized, output)


def _page_payload(paragraphs: list[dict[str, Any]]) -> dict[str, Any]:
    return PageRecord(
        id="ia:item-1:leaf:1",
        item_identifier="item-1",
        part_number=1,
        scan_leaf=1,
        hocr_page_id="page_000001",
        printed_page={"detected": "1"},
        text_ocr="\n\n".join(paragraph["text_ocr"] for paragraph in paragraphs),
        paragraphs=paragraphs,
    ).model_dump(mode="json")


def _paragraph(identifier: str, raw: str, normalized: str | None) -> dict[str, Any]:
    return {
        "id": identifier,
        "reading_order": 0,
        "line_ids": [],
        "lines": [],
        "text_ocr": raw,
        "text_normalized": normalized,
    }


def _normalized_payload(identifier: str, raw: str, normalized: str, leaf: int) -> dict[str, Any]:
    return {
        **_paragraph(identifier, raw, normalized),
        "item_identifier": "item-1",
        "scan_leaf": leaf,
    }


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
