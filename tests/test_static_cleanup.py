from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from congressional_globe.models import ParagraphRecord
from congressional_globe.static_cleanup import normalize_jsonl, normalize_line_wraps


def _paragraph(lines: list[tuple[str, str]], text: str) -> ParagraphRecord:
    return ParagraphRecord.model_validate(
        {
            "id": "p1",
            "reading_order": 0,
            "line_ids": [line_id for line_id, _ in lines],
            "lines": [
                {"id": line_id, "text": line_text, "words": []} for line_id, line_text in lines
            ],
            "text_ocr": text,
        }
    )


def test_cleanup_requires_hyphen_at_end_of_left_line() -> None:
    paragraph = _paragraph(
        [("l1", "An exam- remains inline."), ("l2", "ple starts here.")],
        "An exam- remains inline. ple starts here.",
    )

    normalized, edits = normalize_line_wraps(paragraph, {"example"})

    assert normalized == paragraph.text_ocr
    assert edits == []


def test_cleanup_handles_multiword_line_before_wrapped_word() -> None:
    paragraph = _paragraph(
        [("l1", "The example argu-"), ("l2", "ment continues.")],
        "The example argu- ment continues.",
    )

    normalized, edits = normalize_line_wraps(paragraph, {"argument"})

    assert normalized == "The example argument continues."
    assert len(edits) == 1
    assert edits[0].expected == "argu- ment"


def test_cleanup_resolves_repeated_line_pairs_in_order() -> None:
    paragraph = _paragraph(
        [("l1", "exam-"), ("l2", "ple"), ("l3", "exam-"), ("l4", "ple")],
        "exam- ple exam- ple",
    )

    normalized, edits = normalize_line_wraps(paragraph, {"example"})

    assert normalized == "example example"
    assert [edit.start_char for edit in edits] == [0, 10]


def test_cleanup_keeps_unknown_boundary_wrap_as_residual_hint(tmp_path: Path) -> None:
    paragraphs = tmp_path / "paragraphs.jsonl"
    lexicon = tmp_path / "lexicon.txt"
    output = tmp_path / "derived.jsonl"
    paragraphs.write_text(
        json.dumps(
            {
                "id": "p1",
                "reading_order": 0,
                "line_ids": ["l1", "l2"],
                "lines": [
                    {"id": "l1", "text": "unusual-", "words": []},
                    {"id": "l2", "text": "term", "words": []},
                ],
                "text_ocr": "unusual- term",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    lexicon.write_text("known\n", encoding="utf-8")

    assert normalize_jsonl(paragraphs, lexicon, output) == 1
    record = json.loads(output.read_text(encoding="utf-8"))

    assert record["text_ocr"] == "unusual- term"
    assert record["text_normalized"] == "unusual- term"
    assert record["static_edits"] == []
    assert record["unresolved_wrap_hints"] == [
        {
            "left_line_id": "l1",
            "right_line_id": "l2",
            "candidate": "unusualterm",
            "reason": "line-end hyphen unresolved by static lexicon",
        }
    ]
    assert (
        record["static_cleanup_provenance"]["lexicon_sha256"]
        == hashlib.sha256(b"known\n").hexdigest()
    )
    assert (
        record["static_cleanup_provenance"]["input_sha256"]
        == hashlib.sha256(paragraphs.read_bytes()).hexdigest()
    )
    assert len(record["static_cleanup_provenance"]["pipeline_sha256"]) == 64


def test_cleanup_rejects_input_output_alias_before_truncation(tmp_path: Path) -> None:
    source = tmp_path / "paragraphs.jsonl"
    lexicon = tmp_path / "lexicon.txt"
    source.write_text("preserve me\n", encoding="utf-8")
    lexicon.write_text("word\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must not alias"):
        normalize_jsonl(source, lexicon, source)

    assert source.read_text(encoding="utf-8") == "preserve me\n"


def test_cleanup_rejects_hard_link_output_alias(tmp_path: Path) -> None:
    source = tmp_path / "paragraphs.jsonl"
    hard_link = tmp_path / "output.jsonl"
    lexicon = tmp_path / "lexicon.txt"
    source.write_text("preserve me\n", encoding="utf-8")
    lexicon.write_text("word\n", encoding="utf-8")
    hard_link.hardlink_to(source)

    with pytest.raises(ValueError, match="must not alias"):
        normalize_jsonl(source, lexicon, hard_link)

    assert source.read_text(encoding="utf-8") == "preserve me\n"


def test_cleanup_rejects_lexicon_output_alias(tmp_path: Path) -> None:
    source = tmp_path / "paragraphs.jsonl"
    lexicon = tmp_path / "lexicon.txt"
    source.write_text("{}\n", encoding="utf-8")
    lexicon.write_text("word\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must not alias"):
        normalize_jsonl(source, lexicon, lexicon)

    assert lexicon.read_text(encoding="utf-8") == "word\n"
