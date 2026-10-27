"""Source-preserving behavior against the frozen T42 raw OCR fixture."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from congressional_globe.literal_search import (
    COLLECTION_SHA256,
    LiteralCollection,
    Paragraph,
    SearchRequest,
    _positions,
    load_collection,
)

FIXTURE = Path("artifacts/search-slice-design-20261027-01")
CASES = json.loads((FIXTURE / "query-expectations.json").read_text())


@pytest.fixture
def collection():
    return load_collection(FIXTURE / "paragraphs.json")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_frozen_queries_and_citation_roundtrip(collection, case):
    result = collection.search(case["query"])
    actual = []
    for hit in result.hits:
        citation = hit.match.citation
        paragraph = hit.match.paragraph
        assert paragraph.raw_text[citation.start : citation.end] == hit.quote
        assert citation.source_paragraph_id == paragraph.source_paragraph_id
        assert citation.raw_sha256 == paragraph.raw_sha256
        assert citation.item_identifier == "congressionalg7391unit"
        assert citation.scan_leaf == 117
        assert citation.page_url.endswith("/page/n117")
        assert citation.page_url_status == "unverified"
        actual.append(
            dict(alias=paragraph.alias, start=citation.start, end=citation.end, quote=hit.quote)
        )
    assert actual == case["expected_occurrences"]
    assert result.total_occurrences == result.returned_count == len(actual)
    assert not result.truncated
    assert result.collection_sha256 == COLLECTION_SHA256
    if not actual:
        assert result.message == "No exact match in these six paragraphs"


def test_context_respects_declared_region_and_packet_edges(collection):
    house = collection.search("McPherson").hits[0]
    assert house.preceding is None
    assert house.following.paragraph.alias == "P4"
    assert house.following.kind == "context"
    assert house.following.citation.start == 0
    assert house.following.citation.end == len(house.following.paragraph.raw_text)
    senate = collection.search("Senate adjourned").hits[0]
    assert senate.preceding.paragraph.alias == "P1"
    assert senate.following is None
    assert collection.search("Mr. FOOT").hits[0].preceding is None
    assert collection.search("John Lynch").hits[0].following is None


def test_first_n_reports_total_and_stable_occurrence_order(collection):
    all_hits = collection.search("House")
    limited = collection.search("House", limit=1)
    assert limited.total_occurrences == 3
    assert limited.returned_count == 1
    assert limited.truncated
    assert limited.hits == all_hits.hits[:1]


@pytest.mark.parametrize("query", ["", " ", "\t\n", "a" * 257, 123, None])
def test_invalid_query_rejected(collection, query):
    with pytest.raises(ValidationError):
        collection.search(query)


@pytest.mark.parametrize("limit", [0, 21, -1, True, 1.5, "1"])
def test_invalid_limit_rejected(collection, limit):
    with pytest.raises(ValidationError):
        collection.search("House", limit=limit)


def test_unsupported_filters_fail_explicitly(collection):
    with pytest.raises(TypeError):
        collection.search("House", date="1865-12-04")
    with pytest.raises(ValidationError):
        SearchRequest.model_validate(dict(query="House", speaker="McPherson"))


@pytest.mark.parametrize("change", ["raw", "hash", "order", "region", "duplicate"])
def test_changed_collection_rejected_even_with_new_local_manifest(tmp_path, change):
    records = json.loads((FIXTURE / "paragraphs.json").read_text())
    if change == "order":
        records.reverse()
    elif change == "duplicate":
        records[1] = records[0]
    else:
        key = dict(raw="raw_text", hash="raw_sha256", region="region_id")[change]
        records[0][key] = "changed"
    path = tmp_path / "paragraphs.json"
    path.write_text(json.dumps(records))
    with pytest.raises(ValidationError, match="fingerprint mismatch"):
        load_collection(path)


def test_raw_hash_validated_independently():
    record = json.loads((FIXTURE / "paragraphs.json").read_text())[0]
    record["raw_text"] += "changed"
    with pytest.raises(ValidationError, match="Raw paragraph fingerprint"):
        Paragraph.model_validate(record)


def test_portable_fixture_only_and_frozen_state(tmp_path):
    path = tmp_path / "standalone.json"
    path.write_bytes((FIXTURE / "paragraphs.json").read_bytes())
    collection = load_collection(path)
    assert collection.search("McPherson").returned_count == 1
    with pytest.raises(ValidationError):
        collection.payload = b"changed"  # ty: ignore[invalid-assignment]
    with pytest.raises(ValidationError):
        LiteralCollection(payload=b"[]")


def test_oversized_input_rejected_before_parsing(tmp_path):
    path = tmp_path / "large.json"
    path.write_bytes(b" " * 16001)
    with pytest.raises(ValueError, match="bounded file size"):
        load_collection(path)


def test_overlapping_and_unicode_codepoint_positions():
    assert list(_positions("banana", "ana")) == [1, 3]
    assert list(_positions("é😀é😀", "😀")) == [1, 3]
