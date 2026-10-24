from __future__ import annotations

import hashlib

import pytest

from congressional_globe.models import (
    BoundingBox,
    LineRecord,
    PageRecord,
    ParagraphRecord,
    PrintedPage,
    SourceKind,
    WordRecord,
)
from congressional_globe.scan_geometry import prepare_target, target_from_page
from congressional_globe.scan_models import ScanTarget


def _box(left: int, top: int, right: int, bottom: int) -> BoundingBox:
    return BoundingBox(left=left, top=top, right=right, bottom=bottom)


def _word(word_id: str, text: str, left: int, top: int, right: int, bottom: int):
    return WordRecord(id=word_id, text=text, bbox=_box(left, top, right, bottom))


def _page(
    text: str = "alpha beta gamma",
    bbox: BoundingBox | None = None,
    width: int | None = 100,
    height: int | None = 100,
    lines: list[LineRecord] | None = None,
) -> PageRecord:
    paragraph = ParagraphRecord(
        id="par-1",
        reading_order=0,
        bbox=bbox if bbox is not None else _box(5, 8, 90, 25),
        line_ids=[line.id for line in lines or []],
        lines=lines
        or [
            LineRecord(
                id="line-1",
                bbox=_box(5, 8, 90, 25),
                text=text,
                words=[
                    _word("w1", "alpha", 5, 8, 30, 20),
                    _word("w2", "beta", 35, 8, 55, 20),
                    _word("w3", "gamma", 60, 8, 90, 20),
                ],
            )
        ],
        text_ocr=text,
    )
    return PageRecord(
        id="ia:congressionalglo7392unit:leaf:1009",
        item_identifier="congressionalglo7392unit",
        part_number=2,
        scan_leaf=1009,
        hocr_page_id="page_001009",
        image_width_px=width,
        image_height_px=height,
        printed_page=PrintedPage(detected="1857", source=SourceKind.ARCHIVE_MAP),
        text_ocr=text,
        paragraphs=[paragraph],
    )


def _target(page: PageRecord, start=None, end=None, padding=64):
    return target_from_page(page, "par-1", "a" * 64, "b" * 64, start, end, padding)


def test_full_paragraph_uses_one_clamped_paragraph_region():
    target = _target(_page())
    assert target.precision == "paragraph"
    assert target.selection_text == "alpha beta gamma"
    assert len(target.regions) == 1
    assert target.regions[0].bbox == _box(0, 0, 100, 89)
    assert target.regions[0].line_ids == ["line-1"]
    assert target.regions[0].word_ids == ["w1", "w2", "w3"]


def test_word_span_groups_selected_words_by_line_and_pads_each_region():
    lines = [
        LineRecord(
            id="line-1",
            bbox=_box(10, 10, 70, 20),
            text="alpha beta",
            words=[_word("w1", "alpha", 10, 10, 30, 20), _word("w2", "beta", 40, 10, 70, 20)],
        ),
        LineRecord(
            id="line-2",
            bbox=_box(20, 30, 60, 40),
            text="gamma",
            words=[_word("w3", "gamma", 20, 30, 60, 40)],
        ),
    ]
    target = _target(_page("alpha beta gamma", lines=lines), 6, 16, 5)
    assert target.precision == "word-span"
    assert target.selection_text == "beta gamma"
    assert [region.line_ids for region in target.regions] == [["line-1"], ["line-2"]]
    assert [region.word_ids for region in target.regions] == [["w2"], ["w3"]]
    assert [region.bbox for region in target.regions] == [_box(35, 5, 75, 25), _box(15, 25, 65, 45)]


def test_span_ignores_whitespace_only_word_spans():
    line = LineRecord(
        id="line-1",
        bbox=_box(10, 10, 60, 20),
        text="alpha beta",
        words=[
            _word("w1", "alpha", 10, 10, 30, 20),
            _word("empty", " ", 30, 10, 35, 20),
            _word("w2", "beta", 40, 10, 60, 20),
        ],
    )
    target = _target(_page("alpha beta", lines=[line]), 6, 10, 0)
    assert target.regions[0].word_ids == ["w2"]
    assert target.regions[0].bbox == _box(40, 10, 60, 20)


@pytest.mark.parametrize(
    ("start", "end"),
    [(-1, 2), (0, 100), (4, 4), (5, 6)],
)
def test_invalid_or_whitespace_only_spans_are_rejected(start: int, end: int):
    with pytest.raises(ValueError):
        _target(_page(), start, end)


def test_word_spans_require_exact_paragraph_reconstruction():
    line = LineRecord(
        id="line-1",
        bbox=_box(5, 8, 90, 25),
        text="different OCR text",
        words=[_word("w1", "different", 5, 8, 30, 20)],
    )
    with pytest.raises(ValueError, match="reconstruct source line"):
        _target(_page("expected text", lines=[line]), 0, 9)


def test_missing_frame_or_invalid_bounding_boxes_are_rejected():
    with pytest.raises(ValueError, match="coordinate frame"):
        _target(_page(width=None))
    page = _page()
    paragraph = page.paragraphs[0].model_copy(update={"bbox": None})
    with pytest.raises(ValueError, match="missing"):
        _target(page.model_copy(update={"paragraphs": [paragraph]}))
    zero = _page(bbox=_box(10, 10, 10, 20))
    with pytest.raises(ValueError, match="zero or inverted"):
        _target(zero, padding=0)
    outside = _page(bbox=_box(5, 8, 101, 25))
    with pytest.raises(ValueError, match="exceeds"):
        _target(outside)


def test_selected_word_requires_valid_geometry():
    line = LineRecord(
        id="line-1",
        bbox=_box(5, 8, 90, 25),
        text="alpha",
        words=[WordRecord(id="w1", text="alpha", bbox=None)],
    )
    with pytest.raises(ValueError, match="missing"):
        _target(_page("alpha", lines=[line]), 0, 5)


@pytest.mark.parametrize(
    ("bbox", "message"),
    [(_box(10, 10, 10, 20), "zero or inverted"), (_box(10, 10, 101, 20), "exceeds")],
)
def test_selected_word_rejects_zero_or_out_of_frame_geometry(bbox, message):
    line = LineRecord(
        id="line-1",
        bbox=_box(5, 8, 90, 25),
        text="alpha",
        words=[WordRecord(id="w1", text="alpha", bbox=bbox)],
    )
    with pytest.raises(ValueError, match=message):
        _target(_page("alpha", lines=[line]), 0, 5)


def test_padding_limits_and_unpaired_span_endpoints_are_rejected():
    with pytest.raises(ValueError, match="padding"):
        _target(_page(), padding=257)
    with pytest.raises(ValueError, match="max_width"):
        target_from_page(_page(), "par-1", "a" * 64, "b" * 64, max_width=99)
    with pytest.raises(ValueError, match="start and end"):
        _target(_page(), start=1)


def test_prepare_target_hashes_local_sources_and_resolves_requested_page(tmp_path):
    item = "congressionalglo7392unit"
    hocr = tmp_path / f"{item}_hocr.html"
    page_map = tmp_path / f"{item}_page_numbers.json"
    hocr.write_text(
        '<html><body><div class="ocr_page" id="page_000007" '
        'title="bbox 0 0 100 100; ppageno 7; scan_res 300 300">'
        '<p class="ocr_par" id="par-1" title="bbox 10 10 60 30">'
        '<span class="ocr_line" id="line-1" title="bbox 10 10 60 20">'
        '<span class="ocrx_word" id="word-1" title="bbox 10 10 30 20">hello </span>'
        '<span class="ocrx_word" id="word-2" title="bbox 35 10 60 20">world</span>'
        "</span></p></div></body></html>",
        encoding="utf-8",
    )
    page_map.write_text('{"pages":[{"leafNum":7,"pageNumber":"12"}]}', encoding="utf-8")

    target = prepare_target(tmp_path, item, 7, "par-1", 0, 5, padding=1)

    assert target.hocr_sha256 == hashlib.sha256(hocr.read_bytes()).hexdigest()
    assert target.page_map_sha256 == hashlib.sha256(page_map.read_bytes()).hexdigest()
    assert target.printed_page == "12"
    assert target.selection_text == "hello"
    assert target.regions[0].bbox == _box(9, 9, 31, 21)


def test_prepare_target_rejects_unsupported_item(tmp_path):
    with pytest.raises(ValueError, match="unsupported"):
        prepare_target(tmp_path, "unknown-item", 1, "par-1")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("raw_sha256", "0" * 64, "raw_sha256"),
        ("selection_end", 100, "selection offsets"),
        ("selection_text", "wrong", "selection_text"),
    ],
)
def test_scan_target_validates_text_integrity(field, value, message):
    payload = _target(_page(), 0, 5).model_dump(mode="json")
    payload[field] = value
    with pytest.raises(ValueError, match=message):
        ScanTarget.model_validate(payload)


@pytest.mark.parametrize(
    ("box", "message"),
    [
        ({"left": 5, "top": 5, "right": 5, "bottom": 10}, "positive area"),
        ({"left": 5, "top": 5, "right": 101, "bottom": 10}, "within the OCR frame"),
    ],
)
def test_scan_target_rejects_invalid_crop_frame(box, message):
    payload = _target(_page(), 0, 5).model_dump(mode="json")
    payload["regions"][0]["bbox"] = box
    with pytest.raises(ValueError, match=message):
        ScanTarget.model_validate(payload)
