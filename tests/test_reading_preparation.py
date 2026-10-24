from __future__ import annotations

import json

import pytest

from congressional_globe.inventory import PARTS
from congressional_globe.reading_contracts import ReadingCandidate
from congressional_globe.reading_preparation import exposure_pages, prepare_candidates


def _page(leaf, part, item, text):
    return dict(
        id=f"ia:{item}:leaf:{leaf}",
        item_identifier=item,
        part_number=part,
        scan_leaf=leaf,
        hocr_page_id=f"page_{leaf:06}",
        printed_page={},
        text_ocr=text,
        text_normalized=text,
        paragraphs=[
            dict(
                id=f"par_{leaf:06}_000001",
                reading_order=0,
                line_ids=[],
                text_ocr=text,
                text_normalized=text,
            )
        ],
    )


def test_deterministic_offline_candidates_and_explicit_missing_coverage(tmp_path):
    item = "congressionalg7391unit"
    pages = tmp_path / "pages.jsonl"
    rows = [_page(leaf, 1, item, "Mr. TEST. " + "word " * 210) for leaf in range(10, 20)]
    pages.write_text("".join(json.dumps(row) + "\n" for row in rows))
    exclusion = tmp_path / "exclusions.json"
    exclusion.write_text(json.dumps([dict(item_identifier=item, scan_leaf=10)]))
    first, second = tmp_path / "first", tmp_path / "second"
    one = prepare_candidates(pages, [exclusion], first)
    two = prepare_candidates(pages, [exclusion], second)
    left, right = one.copy(), two.copy()
    left.pop("run_id")
    right.pop("run_id")
    assert left == right
    assert one["run_id"] == "first"
    assert two["run_id"] == "second"
    assert (first / "candidates.jsonl").read_bytes() == (second / "candidates.jsonl").read_bytes()
    selected = [
        ReadingCandidate.model_validate_json(line)
        for line in (first / "candidates.jsonl").read_text().splitlines()
    ]
    assert len(selected) == 2
    assert {x.split for x in selected} == {"primary", "confirmation"}
    assert all(x.target[0].scan_leaf != 10 for x in selected)
    assert one["launch_ready"] is False
    assert one["provider_calls"] == 0
    assert "primary:1:structured" in one["missing_strata"]
    with pytest.raises(FileExistsError):
        prepare_candidates(pages, [exclusion], first)


def test_exposure_context_pages_are_excluded_and_ranges_resolve(tmp_path):
    path = tmp_path / "exclusions.json"
    path.write_text(
        json.dumps(
            {"source_anchor": dict(item_identifier=next(iter(PARTS)), scan_leaf_range=[10, 12])}
        )
    )
    pages, _ = exposure_pages([path])
    assert ("congressionalg7391unit", 10) in pages
    assert ("congressionalg7391unit", 11) in pages
    assert ("congressionalg7391unit", 12) in pages


def test_tampered_static_text_stops_preparation(tmp_path):
    page = _page(10, 1, "congressionalg7391unit", "Mr. TEST. " + "word " * 210)
    page["paragraphs"][0]["text_normalized"] = "An unrecorded replacement"
    pages = tmp_path / "pages.jsonl"
    pages.write_text(json.dumps(page) + "\n")
    excluded = tmp_path / "exclude.json"
    excluded.write_text("[]")
    with pytest.raises(ValueError, match="baseline"):
        prepare_candidates(pages, [excluded], tmp_path / "candidate")


def test_original_source_fingerprints_are_checked(tmp_path):
    from congressional_globe.inventory import sha256_file
    from congressional_globe.reading_preparation import _source_bindings

    hocr, mapping = tmp_path / "source.html", tmp_path / "map.json"
    hocr.write_text("Synthetic immutable hOCR")
    mapping.write_text("{}")
    manifest = tmp_path / "sources.json"
    manifest.write_text(
        json.dumps(
            {
                "parts": [
                    dict(
                        identifier="congressionalg7391unit",
                        hocr_path=str(hocr),
                        hocr_sha256=sha256_file(hocr),
                        page_map_path=str(mapping),
                        page_map_sha256=sha256_file(mapping),
                    )
                ]
            }
        )
    )
    pages = tmp_path / "pages.jsonl"
    pages.write_text(
        json.dumps(_page(10, 1, "congressionalg7391unit", "Mr. TEST. " + "word " * 210)) + "\n"
    )
    excluded = tmp_path / "excluded.json"
    excluded.write_text("[]")
    out = tmp_path / "prepared"
    prepare_candidates(pages, [excluded], out, manifest)
    candidates = [
        ReadingCandidate.model_validate_json(line)
        for line in (out / "candidates.jsonl").read_text().splitlines()
    ]
    assert json.loads((out / "source-files.json").read_text())["source_files_hash_verified"]
    hocr.write_text("Changed after preparation")
    with pytest.raises(ValueError, match="source hash"):
        _source_bindings(manifest, candidates)
