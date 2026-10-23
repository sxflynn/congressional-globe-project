"""Small boundary and preservation checks for offline role preparation."""

from pathlib import Path

import pytest

from congressional_globe.role_aliases import prepare_aliases
from congressional_globe.role_preparation import _context_row, prepare
from congressional_globe.subject_sampling import SamplePage


def _page(leaf: int, texts: list[str]) -> SamplePage:
    return SamplePage.model_validate(
        {
            "id": f"ia:test:leaf:{leaf}",
            "item_identifier": "congressionalglo7395unit",
            "part_number": 5,
            "scan_leaf": leaf,
            "hocr_page_id": f"page_{leaf}",
            "printed_page": {},
            "paragraphs": [
                {"id": f"par_{leaf}_{index}", "text_ocr": text} for index, text in enumerate(texts)
            ],
        }
    )


def test_context_preserves_page_breaks_without_false_name_prefixes() -> None:
    pages = [
        _page(403, ["Mr. WADE. I offer. The"]),
        _page(404, ["House acted.", "Mr. SUMNER. Who?", "Mr. President, no."]),
    ]
    row = _context_row(pages, ["floor_speaker"], ["proposed", "unknown"])
    prepared = prepare_aliases(row)
    assert prepared["input"]["raw_text"] == (
        "Mr. WADE. I offer. The\n\nHouse acted.\n\nMr. SUMNER. Who?\n\nMr. President, no."
    )
    cues = [span["text"] for span in prepared["input"]["spans"] if span["kind"] == "speaker_cue"]
    assert cues == ["Mr. WADE.", "Mr. SUMNER."]
    sources = row["source_anchor"]["paragraph_sources"]
    assert [source["scan_leaf"] for source in sources] == [403, 404, 404, 404]
    assert prepared["alias_map"]["P2"]["span"]["source_paragraph_id"].endswith("par_404_0")


def test_existing_output_is_rejected_before_reading_inputs(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(FileExistsError):
        prepare(tmp_path / "missing", tmp_path / "missing-pages", output)
