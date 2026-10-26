"""Explicit offline evidence bindings for reading pickup; never launch work."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from congressional_globe.reading_contracts import ReadingCandidate
from congressional_globe.reading_dispatch import _check_record_images, _parse_and_derive
from congressional_globe.reading_images import verify_index
from congressional_globe.reading_launch import _check_source_and_review
from congressional_globe.reading_quote_expansion import task_id
from congressional_globe.reading_requests import materialize_record, paragraph_input


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class FileRef(EvidenceModel):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class StoreRef(EvidenceModel):
    run_dir: str = Field(min_length=1)
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class InspectionEvidence(EvidenceModel):
    """Inspection recipe only: no provider settings, dispatch or authorization."""

    schema_version: Literal["reading-inspection-v1"]
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    requests: FileRef
    counts: FileRef
    protocol: FileRef
    review: FileRef
    candidates: FileRef
    images: FileRef
    reuse: FileRef | None
    budget: FileRef
    prior_runs: list[StoreRef]
    runtime_binary: str
    counter_binary: str
    review_database: str | None


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked_file(ref: FileRef) -> Path:
    path = Path(ref.path)
    actual = file_hash(path)
    if actual != ref.sha256:
        raise ValueError(f"file_hash_mismatch:{ref.path}:expected={ref.sha256}:actual={actual}")
    return path


def load_json(ref: FileRef) -> dict:
    result = json.loads(checked_file(ref).read_text())
    if not isinstance(result, dict):
        raise ValueError("evidence JSON must be an object")
    return result


def load_spec(path: Path, config_hash: str) -> InspectionEvidence:
    spec = InspectionEvidence.model_validate_json(path.read_text())
    if spec.config_sha256 != config_hash:
        raise ValueError("inspection recipe belongs to a different run config")
    return spec


def _anchored_files(spec: InspectionEvidence, config: dict) -> None:
    for name in ("requests", "counts", "protocol", "review", "candidates", "images"):
        ref = getattr(spec, name)
        if config.get("files", {}).get(ref.path) != ref.sha256:
            raise ValueError(f"file_not_bound_to_run_config:{name}:{ref.path}")
        checked_file(ref)


def _code_bindings(config: dict) -> None:
    for path, sha in config.get("code", {}).items():
        checked_file(FileRef(path=path, sha256=sha))


def _units(spec: InspectionEvidence) -> dict:
    units = {}
    with checked_file(spec.candidates).open() as stream:
        for line in stream:
            unit = ReadingCandidate.model_validate_json(line)
            if unit.id in units:
                raise ValueError("duplicate source candidate")
            units[unit.id] = unit
    return units


def _source_message(record: dict, unit: ReadingCandidate) -> None:
    message = json.loads(record["messages_without_image_payloads"][1]["content"])
    for key, records in (
        ("target", unit.target),
        ("context_before", unit.context_before),
        ("context_after", unit.context_after),
    ):
        if message[key] != [paragraph_input(p) for p in records]:
            raise ValueError("request_source_or_context_mismatch")


def _check_count(record: dict, count: dict) -> None:
    expected = (record["model"], record["model_digest"], record["unit_id"])
    if (count["model"], count["model_digest"], count["unit_id"]) != expected:
        raise ValueError("count_model_or_unit_mismatch")
    _check_count_arithmetic(record, count)
    _count_image_bindings(record, count)


def _image_identity(image: dict) -> tuple:
    return image["id"], image["path"], image["sha256"]


def _count_image_bindings(record: dict, count: dict) -> None:
    actual = [_image_identity(image) for image in record["images"]]
    counted = [_image_identity(image) for image in (count.get("images") or [])]
    if actual != counted:
        raise ValueError("count_image_bindings_mismatch")


def _check_count_arithmetic(record: dict, count: dict) -> None:
    keys = ("text_tokens", "image_tokens", "total_input_tokens")
    if any(type(count[k]) is not int or count[k] < 0 for k in keys):
        raise ValueError("invalid_token_count")
    if count["text_tokens"] + count["image_tokens"] != count["total_input_tokens"]:
        raise ValueError("token_count_sum_mismatch")
    _check_count_envelope(record, count)


def _check_count_envelope(record: dict, count: dict) -> None:
    options = record["options"]
    if (count["requested_num_ctx"], count["requested_num_predict"]) != (
        options["num_ctx"],
        options["num_predict"],
    ):
        raise ValueError("count_context_or_output_reserve_mismatch")
    if count["total_input_tokens"] + options["num_predict"] > options["num_ctx"]:
        raise ValueError("count_exceeds_context_with_reserve")


def _request_bindings(records: list, units: dict, counts: dict) -> None:
    by_hash = {row["request_sha256"]: row for row in counts["counts"]}
    if len(by_hash) != len(counts["counts"]):
        raise ValueError("duplicate_count_request")
    if set(by_hash) != {row["request_sha256"] for row in records}:
        raise ValueError("count_request_set_mismatch")
    for record in records:
        _one_request(record, units)
        _check_count(record, by_hash[record["request_sha256"]])


def _one_request(record: dict, units: dict) -> None:
    if record.get("control_kind") not in {None, "missing_image", "unrelated_image"}:
        raise ValueError("unknown_control_kind")
    unit = units[record["unit_id"]]
    _source_message(record, unit)
    _check_record_images(unit, record, record.get("control_kind"))
    materialize_record(record)


def _journal_bindings(conn, records: list) -> None:
    expected = {task_id(row): (row["request_sha256"], row["model_digest"]) for row in records}
    if len(expected) != len(records):
        raise ValueError("duplicate_manifest_task")
    actual = {}
    for row in conn.execute("SELECT task_id, task_json FROM tasks"):
        task = json.loads(row["task_json"])
        actual[row["task_id"]] = (task.get("request_sha256"), task.get("model_digest"))
    if actual != expected:
        raise ValueError("journal_request_or_model_bindings_mismatch")


def _saved_valid_replies(conn, records: list, units: dict, counts: dict) -> None:
    by_id = {task_id(r): r for r in records}
    tokens = {r["request_sha256"]: r["total_input_tokens"] for r in counts["counts"]}
    for row in conn.execute("SELECT task_id, raw_reply FROM attempts WHERE status='valid'"):
        record = by_id[row["task_id"]]
        ready = {**record, "expected_input_tokens": tokens[record["request_sha256"]]}
        _parse_and_derive(ready, units[record["unit_id"]], json.loads(row["raw_reply"]))


def _check_reused_manifest(spec: InspectionEvidence, manifest: dict, units: dict) -> dict:
    reused = manifest.get("reused_requests", [])
    if spec.reuse is None:
        if reused:
            raise ValueError("reuse_evidence_missing")
        return {"requests": []}
    evidence = load_json(spec.reuse)
    prior = load_json(FileRef.model_validate(evidence["source_manifest"]))
    load_json(FileRef.model_validate(evidence["source_attempt_export"]))
    if [row["request"] for row in evidence["requests"]] != reused:
        raise ValueError("reuse_manifest_mismatch")
    _exact_reused_records(reused, prior, units)
    return evidence


def _exact_reused_records(reused: list, prior: dict, units: dict) -> None:
    prior_requests = {row["request_sha256"]: row for row in prior["requests"]}
    for record in reused:
        if record != prior_requests.get(record["request_sha256"]):
            raise ValueError("reused_request_not_exact_prior_request")
        _one_request(record, units)


def evidence_bindings(spec: InspectionEvidence, config: dict, conn) -> dict:
    _anchored_files(spec, config)
    _code_bindings(config)
    manifest, counts = load_json(spec.requests), load_json(spec.counts)
    if counts["request_manifest"]["sha256"] != spec.requests.sha256:
        raise ValueError("counts_bound_to_wrong_request_manifest")
    units = _units(spec)
    verify_index(checked_file(spec.images), list(units.values()))
    _check_source_and_review(load_json(spec.protocol), load_json(spec.review))
    _request_bindings(manifest["requests"], units, counts)
    _journal_bindings(conn, manifest["requests"])
    _saved_valid_replies(conn, manifest["requests"], units, counts)
    reuse = _check_reused_manifest(spec, manifest, units)
    return {
        "requests": len(manifest["requests"]),
        "reused_requests": len(reuse["requests"]),
        "source_units": len(units),
        "reuse": reuse,
        "counts": counts,
        "manifest": manifest,
    }


def binary_binding(label: str, path: str, expected: str | None) -> dict:
    result = {
        "artifact": label,
        "path": path,
        "expected_sha256": expected,
        "actual_sha256": None,
        "ok": False,
    }
    if not expected:
        result["error"] = "recorded_hash_missing"
        return result
    try:
        result["actual_sha256"] = file_hash(Path(path))
    except OSError:
        result["error"] = "file_unavailable"
        return result
    result["ok"] = result["actual_sha256"] == expected
    return result


def binary_bindings(spec: InspectionEvidence) -> list[dict]:
    counts = load_json(spec.counts)
    return [
        binary_binding("runtime_binary", spec.runtime_binary, counts.get("runtime_binary_sha256")),
        binary_binding("counter_binary", spec.counter_binary, counts.get("counter_binary_sha256")),
    ]
