import hashlib
import json
from pathlib import Path

import pytest

from congressional_globe.paragraph_continuation import column_reading

SOURCE = Path("artifacts/column-continuation-20261102-01/source-page.jsonl")
LEFT = "par_001060_000026"
RIGHT = "par_001060_000027"


def test_actual_column_reading_keeps_all_raw_characters_and_exact_source_support():
    raw = SOURCE.read_bytes()
    reading = column_reading(raw, LEFT, RIGHT)
    assert reading is not None
    assert reading.status == "source_inspection_required"
    assert reading.page_sha256 == hashlib.sha256(raw).hexdigest()
    page = json.loads(raw)
    originals = {p["id"]: p["text_ocr"] for p in page["paragraphs"]}
    assert reading.text == originals[LEFT] + " " + originals[RIGHT]
    assert "eastern district of Louisiana" in reading.text
    assert reading.text[reading.separator_start] == reading.inserted_separator == " "
    for part, identity in zip(reading.parts, [LEFT, RIGHT], strict=True):
        assert reading.text[part.reading_start : part.reading_end] == originals[identity]
        assert part.raw_sha256 == hashlib.sha256(originals[identity].encode()).hexdigest()
        assert part.raw_end - part.raw_start == len(originals[identity])
    assert SOURCE.read_bytes() == raw


@pytest.mark.parametrize(
    "change",
    [
        "heading",
        "terminal",
        "new_act",
        "same_column",
        "not_bottom",
        "not_top",
        "no_geometry",
        "gap",
        "duplicate_order",
    ],
)
def test_declines_unsafe_or_ambiguous_boundaries(change):
    page = json.loads(SOURCE.read_bytes())
    left = next(p for p in page["paragraphs"] if p["id"] == LEFT)
    right = next(p for p in page["paragraphs"] if p["id"] == RIGHT)
    _change(page, left, right, change)
    assert column_reading(json.dumps(page).encode(), LEFT, RIGHT) is None


def _change(page, left, right, change):
    mutations = {
        "heading": (right, "role", "heading"),
        "terminal": (left, "text_ocr", left["text_ocr"] + "."),
        "new_act": (right, "text_ocr", "CHAP. NEW. A separate act."),
        "same_column": (right["bbox"], "left", left["bbox"]["left"]),
        "not_bottom": (page, "image_height_px", 100000),
        "not_top": (right, "bbox", {**right["bbox"], "top": 1500, "bottom": 2200}),
        "no_geometry": (right, "bbox", None),
        "gap": (right, "reading_order", 2000),
        "duplicate_order": (right, "reading_order", left["reading_order"]),
    }
    target, key, value = mutations[change]
    target[key] = value


def test_declines_reversed_nonadjacent_and_missing_other_page_paragraphs():
    raw = SOURCE.read_bytes()
    assert column_reading(raw, RIGHT, LEFT) is None
    assert column_reading(raw, LEFT, "par_001060_000028") is None
    assert column_reading(raw, LEFT, "par_001061_000000") is None
