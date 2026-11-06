from __future__ import annotations

import json

import pytest

from congressional_globe.extraction import iter_pages, load_page_map
from congressional_globe.inventory import sha256_file
from congressional_globe.reading_contracts import ReadingCandidate, text_hash
from congressional_globe.reading_preparation import source_paragraph
from congressional_globe.reading_source_check import verify_candidate_sources


@pytest.mark.parametrize("migrated", [False, True])
def test_original_hocr_checks_text_and_geometry_not_just_file_hashes(tmp_path, migrated):
    hocr = tmp_path / "congressionalg7391unit_hocr.html"
    hocr.write_text("""<html xmlns="http://www.w3.org/1999/xhtml"><body>
    <div class="ocr_page" id="page_000010" title="bbox 0 0 1000 1500; ppageno 10">
    <p class="ocr_par" id="par_000010_000001" title="bbox 10 10 500 80">
    <span class="ocr_line" id="line_000010_000001" title="bbox 10 10 500 80">
    <span class="ocrx_word" id="word_000010_000001" title="bbox 10 10 40 80">café</span>
    <span class="ocrx_word" id="word_000010_000002" title="bbox 50 10 80 80">GCO</span>
    </span></p></div></body></html>""")
    mapping = tmp_path / "congressionalg7391unit_page_numbers.json"
    mapping.write_text(json.dumps({"pages": [{"leafNum": 10, "pageNumber": "100"}]}))
    manifest = tmp_path / "manifest.json"
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
    page = next(iter_pages(hocr, load_page_map(mapping)))
    raw = page.paragraphs[0]
    paragraph = source_paragraph(page, raw.model_copy(update={"text_normalized": raw.text_ocr}))
    candidate = ReadingCandidate(
        id="synthetic",
        part_number=1,
        stratum="ordinary",
        split="primary",
        target=[paragraph],
        selection_reason="Synthetic source check",
    )
    if migrated:
        (tmp_path / "downloads").mkdir()
        hocr.rename(tmp_path / "downloads" / hocr.name)
        mapping.rename(tmp_path / "downloads" / mapping.name)
    proof = verify_candidate_sources([candidate], manifest)
    assert proof["paragraph_count"] == 1
    assert proof["candidate_to_source_binding"] == "verified"
    changed = paragraph.model_copy(
        update=dict(
            raw="café 999",
            raw_sha256=text_hash("café 999"),
            static="café 999",
            static_sha256=text_hash("café 999"),
        )
    )
    with pytest.raises(ValueError, match="differs from original"):
        verify_candidate_sources([candidate.model_copy(update={"target": [changed]})], manifest)
