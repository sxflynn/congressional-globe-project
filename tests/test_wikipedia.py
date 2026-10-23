"""Core failure guarantees for the deterministic authority-candidate workflow."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from congressional_globe.wiki_records import WikiRecord, member_record
from congressional_globe.wiki_sources import read_snapshot
from congressional_globe.wikipedia import query


def test_snapshot_rejects_modified_source(tmp_path: Path) -> None:
    payload = b"saved source"
    (tmp_path / "house.html").write_bytes(payload)
    metadata = {
        "source_id": "house",
        "requested_url": "https://en.wikipedia.org/wiki/example",
        "resolved_url": "https://en.wikipedia.org/wiki/example",
        "retrieved_at_utc": "2026-10-23T00:00:00Z",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "revision_id": "123",
        "headers": {},
    }
    (tmp_path / "house.metadata.json").write_text(json.dumps(metadata))
    assert read_snapshot(tmp_path, "house")[1] == "saved source"
    (tmp_path / "house.html").write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash/size mismatch"):
        read_snapshot(tmp_path, "house")


def test_member_query_preserves_unknowns_and_filters(tmp_path: Path) -> None:
    record = member_record(
        "house",
        {
            "name": "Thaddeus Stevens",
            "kind": "representative",
            "party": "R",
            "district": "PA-09",
            "person_page": "/wiki/Thaddeus_Stevens",
        },
    )
    assert record.linked_page == "https://en.wikipedia.org/wiki/Thaddeus_Stevens"
    assert record.service_start is None
    path = tmp_path / "records.jsonl"
    path.write_text(record.model_dump_json() + "\n")
    assert len(query(path, ["name=STEVENS", "district=PA"])) == 1
    assert len(query(path, ["name=Stevens", "state=PA"])) == 1
    assert query(path, ["name=Stevens", "service_start=1865"]) == []
    with pytest.raises(ValueError, match="FIELD=TEXT"):
        query(path, ["not_a_field=Stevens"])
    with pytest.raises(ValidationError):
        WikiRecord.model_validate({**record.model_dump(), "service_start": "1865-03-04"})
