"""Build explicit, incomplete exclusion inventories from known review samples."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_PARAGRAPH_ID = re.compile(r"^par_(\d{6})_\d{6}$")


class ExcludedParagraph(BaseModel):
    """Composite source anchor understood by the subject-sampling interface."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_identifier: NonBlank
    part_number: int = Field(ge=1, le=5)
    scan_leaf: int = Field(ge=0)
    paragraph_id: NonBlank


class ExclusionManifest(BaseModel):
    """Machine-readable exclusions; deliberately never claims full coverage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    complete: Literal[False] = False
    paragraphs: list[ExcludedParagraph]


class ExclusionBuildReport(BaseModel):
    """Provenance for the manifest, separate from its sampling-compatible schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_sha256: str
    sample_file_sha256: dict[str, str]
    jobs_database_sha256: str | None = None
    sample_paragraph_count: int = Field(ge=0)
    attempted_job_count: int = Field(ge=0)
    unique_exclusion_count: int = Field(ge=0)
    complete: bool = False


class _SampleAnchor(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    item_identifier: NonBlank
    part_number: int = Field(ge=1, le=5)
    scan_leaf_range: tuple[int, int]
    paragraph_ids: list[NonBlank] = Field(min_length=1)


class _SampleRecord(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    source_anchor: _SampleAnchor


class _DatabaseSource(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    item_identifier: NonBlank
    part_number: int = Field(ge=1, le=5)
    scan_leaf: int = Field(ge=0)
    paragraph_id: NonBlank


def build_subject_exclusions(
    sample_paths: list[Path],
    output_path: Path,
    jobs_database: Path | None = None,
) -> ExclusionBuildReport:
    """Build a strict, explicit exclusion list; never infer unlisted samples."""
    if not sample_paths:
        raise ValueError("at least one explicit sample path is required")
    if output_path.exists():
        raise FileExistsError(output_path)
    sources: set[ExcludedParagraph] = set()
    source_hashes: dict[str, str] = {}
    sample_count = 0
    for path in sample_paths:
        payloads, digest = _read_sample_file(path)
        source_hashes[str(path)] = digest
        for anchor in payloads:
            extracted = _expand_anchor(anchor)
            sample_count += len(extracted)
            sources.update(extracted)
    database_digest, attempted_count = _read_attempted_jobs(jobs_database, sources)
    manifest = ExclusionManifest(paragraphs=sorted(sources, key=_source_sort_key))
    encoded = json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n"
    _write_new_file(output_path, encoded)
    return ExclusionBuildReport(
        manifest_sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        sample_file_sha256=source_hashes,
        jobs_database_sha256=database_digest,
        sample_paragraph_count=sample_count,
        attempted_job_count=attempted_count,
        unique_exclusion_count=len(sources),
    )


def _read_sample_file(path: Path) -> tuple[list[_SampleAnchor], str]:
    data = path.read_bytes()
    try:
        decoded = json.loads(data)
    except json.JSONDecodeError:
        anchors = _jsonl_anchors(data)
    else:
        anchors = _json_anchors(decoded)
    if not anchors:
        raise ValueError(f"sample file contains no recognized source anchors: {path}")
    return anchors, hashlib.sha256(data).hexdigest()


def _json_anchors(decoded: object) -> list[_SampleAnchor]:
    records = decoded.get("sample") if isinstance(decoded, dict) else None
    if records is None:
        records = decoded if isinstance(decoded, list) else [decoded]
    return [_SampleRecord.model_validate(record).source_anchor for record in records]


def _jsonl_anchors(data: bytes) -> list[_SampleAnchor]:
    return [
        _SampleRecord.model_validate(json.loads(line)).source_anchor
        for line in data.decode("utf-8").splitlines()
        if line.strip()
    ]


def _expand_anchor(anchor: _SampleAnchor) -> list[ExcludedParagraph]:
    start, end = anchor.scan_leaf_range
    if start < 0 or end < start:
        raise ValueError("sample scan_leaf_range must be a nonnegative ordered pair")
    return [
        ExcludedParagraph(
            item_identifier=anchor.item_identifier,
            part_number=anchor.part_number,
            scan_leaf=_validated_id_leaf(paragraph_id, start, end),
            paragraph_id=paragraph_id,
        )
        for paragraph_id in anchor.paragraph_ids
    ]


def _validated_id_leaf(paragraph_id: str, start: int, end: int) -> int:
    match = _PARAGRAPH_ID.fullmatch(paragraph_id)
    if match is None:
        raise ValueError(f"unrecognized generated paragraph ID: {paragraph_id}")
    leaf = int(match.group(1))
    if not start <= leaf <= end:
        raise ValueError(f"paragraph ID leaf {leaf} falls outside its declared range")
    return leaf


def _read_attempted_jobs(
    database: Path | None, exclusions: set[ExcludedParagraph]
) -> tuple[str | None, int]:
    if database is None:
        return None, 0
    uri = f"file:{quote(str(database.resolve()))}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        claimed = connection.execute(
            "SELECT COUNT(*) FROM cleanup_jobs WHERE status = 'claimed'"
        ).fetchone()[0]
        if claimed:
            raise ValueError("jobs database has claimed work; retry after the worker stops")
        rows = connection.execute(
            "SELECT attempts, paragraph_id, source_json FROM cleanup_jobs WHERE attempts > 0"
        )
        records = [_database_exclusion(row) for row in rows]
    exclusions.update(records)
    return _sha256_file(database), len(records)


def _database_exclusion(row: tuple[int, str, str]) -> ExcludedParagraph:
    _attempts, paragraph_id, source_json = row
    source_data = json.loads(source_json)
    source = _DatabaseSource.model_validate({**source_data, "paragraph_id": paragraph_id})
    match = _PARAGRAPH_ID.fullmatch(source.paragraph_id)
    if match is None or int(match.group(1)) != source.scan_leaf:
        raise ValueError("attempted cleanup job has an inconsistent generated paragraph ID")
    return ExcludedParagraph(
        item_identifier=source.item_identifier,
        part_number=source.part_number,
        scan_leaf=source.scan_leaf,
        paragraph_id=source.paragraph_id,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_sort_key(source: ExcludedParagraph) -> tuple[str, int, int, str]:
    return source.item_identifier, source.part_number, source.scan_leaf, source.paragraph_id


def _write_new_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as destination:
        destination.write(content)
