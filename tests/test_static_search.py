"""Derived text must point to support in the unchanged raw OCR, never borrowed offsets."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from congressional_globe.literal_search import load_collection
from congressional_globe.static_search import (
    PAIRS_SHA256,
    StaticPair,
    _static_hit,
    load_static_collection,
)

FIXTURE = Path("artifacts/raw-clean-readiness-20261027-01")
OUTCOMES = json.loads((FIXTURE / "mechanical-outcomes.json").read_text())


@pytest.fixture
def collection():
    return load_static_collection(FIXTURE / "pairs.json")


@pytest.mark.parametrize("case", OUTCOMES, ids=lambda c: c["query"])
def test_frozen_static_queries_and_raw_support(collection, case):
    result = collection.search(case["query"])
    actual = []
    for hit in result.hits:
        actual.append(
            dict(alias=hit.raw_support.paragraph.alias, start=hit.static_start, end=hit.static_end)
        )
        assert hit.static_paragraph[hit.static_start : hit.static_end] == hit.matched_text
        c = hit.raw_support.citation
        assert hit.raw_support.paragraph.raw_text[c.start : c.end] == hit.raw_support_text
        assert c.raw_sha256 == hit.raw_support.paragraph.raw_sha256
        assert c.page_url_status == "unverified"
    assert actual == case["static_occurrences"]
    assert result.total_occurrences == result.returned_count == len(actual)
    assert result.source_layer == "saved_static"
    assert result.pairs_sha256 == PAIRS_SHA256


def test_edited_word_and_later_shift_are_explicit(collection):
    joined = collection.search("Constitution").hits[0]
    assert joined.raw_support_text == "Consti- tution"
    assert joined.mapping == "includes_saved_edit"
    assert (joined.static_start, joined.static_end) == (89, 101)
    assert (joined.raw_support.citation.start, joined.raw_support.citation.end) == (89, 103)
    later = collection.search("McPherson").hits[0]
    assert later.mapping == "exact_copy"
    assert later.raw_support_text == "McPherson"
    assert later.raw_support.citation.start == later.static_start + 4


def test_partial_and_cross_edit_matches_map_whole_support_interval(collection):
    part = collection.search("stitution").hits[0]
    assert part.raw_support_text == "Consti- tution"
    assert part.mapping == "includes_saved_edit"
    across = collection.search("the Constitution for").hits[0]
    assert across.raw_support_text == "the Consti- tution for"
    assert across.mapping == "includes_saved_edit"


def test_same_context_boundaries_and_truncation_as_raw(collection):
    house = collection.search("House", limit=1)
    assert house.total_occurrences == 3
    assert house.returned_count == 1
    assert house.truncated
    assert house.hits[0].preceding is None
    assert house.hits[0].following.paragraph.alias == "P4"
    assert house.hits[0].following.kind == "context"
    senate = collection.search("Senate adjourned").hits[0]
    assert senate.following is None
    assert senate.preceding.paragraph.alias == "P1"
    assert collection.search("Mr. FOOT").hits[0].preceding is None
    assert collection.search("John Lynch").hits[0].following is None


def test_raw_and_static_identities_cannot_be_swapped(collection):
    with pytest.raises(ValidationError, match="fingerprint"):
        load_collection(FIXTURE / "pairs.json")
    with pytest.raises(ValidationError, match="fingerprint"):
        load_static_collection(Path("artifacts/search-slice-design-20261027-01/paragraphs.json"))
    assert (
        collection.search("Freedmen").message
        == "No exact static-text match in these six paragraphs"
    )


def _change_pair_field(pair, change):
    if change == "region":
        pair["source"]["region_id"] = "house-opening"
    else:
        pair[{"hash": "static_sha256", "text": "static_text"}[change]] = "changed"


@pytest.mark.parametrize("change", ["order", "region", "duplicate", "hash", "text"])
def test_pair_file_tampering_rejected(tmp_path, change):
    pairs = json.loads((FIXTURE / "pairs.json").read_text())
    if change == "order":
        pairs.reverse()
    elif change == "duplicate":
        pairs[1] = pairs[0]
    else:
        _change_pair_field(pairs[0], change)
    path = tmp_path / "pairs.json"
    path.write_text(json.dumps(pairs))
    with pytest.raises(ValidationError, match="fingerprint"):
        load_static_collection(path)


def _change_edit_output(pair, change):
    if change == "output":
        pair["static_edits"][0]["replacement"] = "wrong"
    else:
        pair["static_sha256"] = "wrong"


@pytest.mark.parametrize("change", ["expected", "overlap", "reverse", "end", "output", "hash"])
def test_independent_edit_validation(change):
    pair = json.loads((FIXTURE / "pairs.json").read_text())[2]
    edits = pair["static_edits"]
    if change == "expected":
        edits[0]["expected"] = "wrong"
    elif change == "overlap":
        edits[1]["start_char"] = edits[0]["start_char"]
    elif change == "reverse":
        edits.reverse()
    elif change == "end":
        edits[0]["end_char"] = 10000
    else:
        _change_edit_output(pair, change)
    with pytest.raises(ValidationError):
        StaticPair.model_validate_json(json.dumps(pair))


def test_invalid_request_and_unsupported_filters(collection):
    for query in ["", " ", "x" * 257]:
        with pytest.raises(ValidationError):
            collection.search(query)
    with pytest.raises(ValidationError):
        collection.search("House", limit=0)
    with pytest.raises(TypeError):
        collection.search("House", date="1865-12-04")


def test_fixture_only_loading_and_size_bound(tmp_path):
    path = tmp_path / "pairs.json"
    path.write_bytes((FIXTURE / "pairs.json").read_bytes())
    assert load_static_collection(path).search("Constitution").returned_count == 1
    path.write_bytes(b" " * 16001)
    with pytest.raises(ValueError, match="bounded file size"):
        load_static_collection(path)


def test_synthetic_unicode_overlap_and_deletion_mapping():
    raw = "é😀banana!"
    static = "é😀banana"
    source = dict(
        alias="P1",
        source_paragraph_id="synthetic",
        item_identifier="synthetic",
        scan_leaf=0,
        raw_text=raw,
        raw_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        region_id="synthetic",
    )
    edit = dict(
        start_char=8, end_char=9, expected="!", replacement="", reason="test", confidence=1.0
    )
    pair = StaticPair.model_validate_json(
        json.dumps(
            dict(
                source=source,
                static_text=static,
                static_sha256=hashlib.sha256(static.encode()).hexdigest(),
                static_edits=[edit],
                static_cleanup_provenance={},
                ai_status="not_queued",
                ai_provenance=None,
            )
        )
    )
    hit = _static_hit((pair,), 0, 3, "ana")
    assert hit.raw_support_text == "ana"
    assert hit.raw_support.citation.start == 3
    assert hit.mapping == "exact_copy"
