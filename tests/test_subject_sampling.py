"""Focused checks for offline subject-review sample preparation."""

import json
from pathlib import Path

import pytest

from congressional_globe.subject_sampling import build_subject_review_sample


def _page(part: int | None, leaf: int) -> dict[str, object]:
    return {
        "id": f"page-{leaf}",
        "item_identifier": f"item-{part}",
        "part_number": part,
        "scan_leaf": leaf,
        "hocr_page_id": f"hocr-{leaf}",
        "printed_page": {"detected": "12", "inferred": None, "source": "unknown"},
        "unused_large_words": [{"text": "ignored"}] * 100,
        "paragraphs": [
            {
                "id": f"p-{leaf}",
                "text_ocr": "a" * 250,
                "line_ids": [f"l-{leaf}"],
                "bbox": None,
                "role": "body",
            }
        ],
    }


def _inputs(tmp_path: Path, pages: list[dict[str, object]]) -> tuple[Path, Path]:
    source = tmp_path / "canonical_pages.jsonl"
    source.write_text("".join(json.dumps(page) + "\n" for page in pages), encoding="utf-8")
    exclusions = tmp_path / "exclusions.json"
    exclusions.write_text(json.dumps({"complete": False, "paragraphs": []}), encoding="utf-8")
    return source, exclusions


def test_sampling_is_reproducible_and_blinded(tmp_path: Path) -> None:
    source, exclusions = _inputs(
        tmp_path, [_page(part, leaf) for part in range(1, 6) for leaf in range(1, 4)]
    )
    first = build_subject_review_sample(source, exclusions, tmp_path / "first", 42, 2)
    build_subject_review_sample(source, exclusions, tmp_path / "second", 42, 2)
    first_packets = (tmp_path / "first" / "review_packets.jsonl").read_text()
    assert first_packets == (tmp_path / "second" / "review_packets.jsonl").read_text()
    assert first["provider_calls"] == 0
    assert first["selected_by_part"] == {str(part): 2 for part in range(1, 6)}
    assert "candidate" not in first_packets
    assert "heldout claims pending" in first["status"]


def test_exclusion_drops_entire_window_and_output_is_no_overwrite(tmp_path: Path) -> None:
    pages = [_page(part, leaf) for part in range(1, 6) for leaf in (1, 2)]
    source, exclusions = _inputs(tmp_path, pages)
    exclusions.write_text(
        json.dumps(
            {
                "complete": False,
                "paragraphs": [
                    {
                        "item_identifier": "item-1",
                        "part_number": 1,
                        "scan_leaf": 1,
                        "paragraph_id": "p-1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = build_subject_review_sample(source, exclusions, tmp_path / "out", 9, 1)
    packets = [
        json.loads(line)
        for line in (tmp_path / "out" / "review_packets.jsonl").read_text().splitlines()
    ]
    assert len(packets) == 5
    assert not any(packet["scan_leaf"] == 1 and packet["part_number"] == 1 for packet in packets)
    assert result["excluded_windows_by_part"]["1"] == 1
    with pytest.raises(FileExistsError):
        build_subject_review_sample(source, exclusions, tmp_path / "out", 9, 2)


def test_null_part_fails_without_completed_manifest(tmp_path: Path) -> None:
    source, exclusions = _inputs(tmp_path, [_page(None, 1)])
    with pytest.raises(ValueError, match="null part_number"):
        build_subject_review_sample(source, exclusions, tmp_path / "failed", 1)
    assert not (tmp_path / "failed" / "manifest.json").exists()


def test_sample_count_cap_is_enforced(tmp_path: Path) -> None:
    source, exclusions = _inputs(tmp_path, [_page(1, 1)])
    with pytest.raises(ValueError, match="between 1 and 5"):
        build_subject_review_sample(source, exclusions, tmp_path / "out", 1, 6)
