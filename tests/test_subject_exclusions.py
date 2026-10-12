"""Focused tests for explicit subject-evaluation exclusions."""

import json
import sqlite3

import pytest
from pydantic import ValidationError

from congressional_globe.subject_exclusions import (
    ExclusionManifest,
    build_subject_exclusions,
)


def _sample(path, paragraph_id="par_000114_000235"):
    path.write_text(
        json.dumps(
            {
                "sample": [
                    {
                        "source_anchor": {
                            "item_identifier": "globe39part1",
                            "part_number": 1,
                            "scan_leaf_range": [114, 114],
                            "paragraph_ids": [paragraph_id],
                        }
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_sample_exclusions_are_composite_and_always_incomplete(tmp_path) -> None:
    sample = tmp_path / "sample.json"
    output = tmp_path / "exclusions.json"
    _sample(sample)

    report = build_subject_exclusions([sample], output)
    manifest = ExclusionManifest.model_validate_json(output.read_text(encoding="utf-8"))

    assert manifest.complete is False
    assert manifest.paragraphs[0].model_dump() == {
        "item_identifier": "globe39part1",
        "part_number": 1,
        "scan_leaf": 114,
        "paragraph_id": "par_000114_000235",
    }
    assert report.unique_exclusion_count == 1
    assert report.sample_paragraph_count == 1
    with pytest.raises(FileExistsError):
        build_subject_exclusions([sample], output)


def test_unknown_or_range_inconsistent_paragraph_ids_fail(tmp_path) -> None:
    sample = tmp_path / "sample.json"
    _sample(sample, "par_000115_000235")

    with pytest.raises(ValueError, match="outside its declared range"):
        build_subject_exclusions([sample], tmp_path / "exclusions.json")

    _sample(sample, "paragraph-235")
    with pytest.raises(ValueError, match="unrecognized generated paragraph ID"):
        build_subject_exclusions([sample], tmp_path / "other.json")


def test_attempted_database_jobs_are_read_only_and_pending_jobs_are_skipped(tmp_path) -> None:
    sample = tmp_path / "sample.json"
    database = tmp_path / "jobs.sqlite"
    output = tmp_path / "exclusions.json"
    _sample(sample)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE cleanup_jobs "
            "(id TEXT, attempts INTEGER, paragraph_id TEXT, source_json TEXT, status TEXT)"
        )
        source = {
            "item_identifier": "globe39part1",
            "part_number": 1,
            "scan_leaf": 200,
        }
        connection.execute(
            "INSERT INTO cleanup_jobs VALUES (?, ?, ?, ?, ?)",
            ("pending", 0, "par_000201_000001", json.dumps(source), "pending"),
        )
        connection.execute(
            "INSERT INTO cleanup_jobs VALUES (?, ?, ?, ?, ?)",
            ("attempted", 1, "par_000200_000002", json.dumps(source), "review"),
        )
    before = database.read_bytes()

    report = build_subject_exclusions([sample], output, database)
    manifest = ExclusionManifest.model_validate_json(output.read_text(encoding="utf-8"))

    assert report.attempted_job_count == 1
    assert report.jobs_database_sha256 is not None
    assert len(manifest.paragraphs) == 2
    assert database.read_bytes() == before


def test_invalid_manifest_boundaries_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ExclusionManifest.model_validate(
            {
                "schema_version": "1",
                "complete": True,
                "paragraphs": [],
            }
        )
