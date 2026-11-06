"""Static-first orchestration for bounded, resumable corpus runs."""

from __future__ import annotations

import fcntl
import hashlib
import inspect
import json
import os
import re
import shutil
from collections import Counter
from contextlib import contextmanager
from itertools import chain, dropwhile, islice
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from congressional_globe import cleanup
from congressional_globe.extraction import iter_pages, load_page_map
from congressional_globe.inventory import PARTS, expected_paths
from congressional_globe.models import PageRecord, ParagraphRecord, RAGChunk
from congressional_globe.pipeline import (
    _paragraph_payload,
    _read_jsonl,
    _write_line,
    build_rag_from_pages,
    merge_normalized_paragraphs,
)
from congressional_globe.static_cleanup import normalize_jsonl
from congressional_globe.storage import (
    composite_identity,
    create_run,
    iter_jobs_for_run,
    run_summary,
)
from congressional_globe.structure import classify_page, needs_model


class WorkflowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    root: str
    lexicon_path: str
    lexicon_sha256: str
    page_limit: int | None = Field(default=None, ge=1)
    start_leaf: int = Field(default=0, ge=0)
    processing_sha256: str


class SourcePart(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    identifier: str
    part_number: int
    hocr_path: str
    hocr_bytes: int
    hocr_sha256: str
    djvu_path: str
    djvu_bytes: int
    djvu_sha256: str
    page_map_path: str
    page_map_sha256: str
    metadata_raw_path: str | None = None
    metadata_source_path: str | None = None
    metadata_raw_sha256: str | None = None
    metadata_raw_status: Literal["preserved", "not_available"]


class WorkflowManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    run_id: str
    config: WorkflowConfig
    config_sha256: str
    parts: list[SourcePart]
    sample_scope: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    stages: dict[str, str] = Field(default_factory=dict)
    artifact_sha256: dict[str, str] = Field(default_factory=dict)
    latest_report: dict[str, Any] = Field(default_factory=dict)


def run_static_first(
    root: Path,
    run_id: str,
    lexicon_path: Path,
    *,
    output_root: Path = Path("artifacts/runs"),
    page_limit: int | None = None,
    start_leaf: int = 0,
    backend: Literal["none", "ollama", "openai"] = "none",
    model: str | None = None,
    ai_limit: int | None = None,
    plan_only: bool = False,
    benchmark_summary_path: Path | None = None,
    input_usd_per_million: float | None = None,
    output_usd_per_million: float | None = None,
    base_url: str = "http://127.0.0.1:11434/v1",
    progress_interval: int = 30,
) -> dict[str, Any]:
    """Prepare a static-first run, with provider work gated by explicit options."""
    _validate_options(
        root, lexicon_path, run_id, page_limit, start_leaf, backend, model, ai_limit, plan_only
    )
    output_root.mkdir(parents=True, exist_ok=True)
    with _workflow_lock(output_root, run_id):
        return _execute_workflow(
            root,
            run_id,
            lexicon_path,
            output_root,
            page_limit,
            start_leaf,
            backend,
            model,
            ai_limit,
            plan_only,
            benchmark_summary_path,
            input_usd_per_million,
            output_usd_per_million,
            base_url,
            progress_interval,
        )


@contextmanager
def _workflow_lock(output_root: Path, run_id: str):
    lock_path = output_root / f".{run_id}.workflow.lock"
    with lock_path.open("a", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _execute_workflow(
    root: Path,
    run_id: str,
    lexicon_path: Path,
    output_root: Path,
    page_limit: int | None,
    start_leaf: int,
    backend: Literal["none", "ollama", "openai"],
    model: str | None,
    ai_limit: int | None,
    plan_only: bool,
    benchmark_summary_path: Path | None,
    input_rate: float | None,
    output_rate: float | None,
    base_url: str,
    progress_interval: int,
) -> dict[str, Any]:
    run_directory = output_root / run_id
    run_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = run_directory / "workflow_manifest.json"
    started = perf_counter()
    stage_times: dict[str, float] = {}
    stage_started = perf_counter()
    manifest = _load_or_create_manifest(
        manifest_path, root, lexicon_path, run_id, page_limit, start_leaf, run_directory
    )
    stage_times["input_hashing"] = round(perf_counter() - stage_started, 3)
    manifest, counts, stage_times, extraction_valid = _prepare_extraction_stage(
        root, run_directory, page_limit, start_leaf, manifest, manifest_path, stage_times
    )
    manifest, counts, stage_times = _prepare_text_stages(
        run_directory,
        lexicon_path,
        manifest,
        manifest_path,
        counts,
        stage_times,
        extraction_valid,
    )
    report = _base_report(run_id, run_directory, plan_only, page_limit, start_leaf, counts)
    if not plan_only:
        stage_started = perf_counter()
        report.update(
            _run_ai_and_export(
                run_directory,
                run_id,
                run_directory / "static_paragraphs.jsonl",
                run_directory / "residual_paragraphs.jsonl",
                run_directory / "pages.jsonl",
                backend,
                model,
                ai_limit,
                benchmark_summary_path,
                input_rate,
                output_rate,
                stage_times["static_cleanup"],
                base_url,
                progress_interval,
            )
        )
        stage_times["ai_and_export"] = round(perf_counter() - stage_started, 3)
        manifest = _stage(manifest, "materialize", "complete", manifest_path)
        report["cleanup_complete"] = _cleanup_is_complete(report)
    report["elapsed_seconds"] = round(perf_counter() - started, 3)
    report["stage_seconds"] = stage_times
    manifest = manifest.model_copy(update={"latest_report": report})
    _save_manifest(manifest_path, manifest)
    return report


def _prepare_extraction_stage(
    root: Path,
    run_directory: Path,
    page_limit: int | None,
    start_leaf: int,
    manifest: WorkflowManifest,
    manifest_path: Path,
    stage_times: dict[str, float],
) -> tuple[WorkflowManifest, dict[str, int], dict[str, float], bool]:
    stage_started = perf_counter()
    pages_path = run_directory / "pages.jsonl"
    paragraphs_path = run_directory / "paragraphs.jsonl"
    extraction_valid = _artifacts_valid(
        manifest, {"pages": pages_path, "paragraphs": paragraphs_path}
    )
    if extraction_valid:
        counts = {
            "pages": _count_jsonl(pages_path),
            "paragraphs": _count_jsonl(paragraphs_path),
        }
    else:
        counts = _extract_classify(root, run_directory, page_limit, start_leaf)
        manifest = _record_artifacts(
            manifest, {"pages": pages_path, "paragraphs": paragraphs_path}, manifest_path
        )
    stage_times["extraction"] = round(perf_counter() - stage_started, 3)
    manifest = _stage(manifest, "extraction", "complete", manifest_path)
    return manifest, counts, stage_times, extraction_valid


def _prepare_text_stages(
    run_directory: Path,
    lexicon_path: Path,
    manifest: WorkflowManifest,
    manifest_path: Path,
    counts: dict[str, int],
    stage_times: dict[str, float],
    extraction_valid: bool,
) -> tuple[WorkflowManifest, dict[str, int], dict[str, float]]:
    manifest, static_count, static_seconds, static_reused = _prepare_static_stage(
        run_directory, lexicon_path, manifest, manifest_path, extraction_valid
    )
    counts["static_paragraphs"] = static_count
    stage_times["static_cleanup"] = static_seconds
    manifest, residual_count, residual_seconds = _prepare_residual_stage(
        run_directory, manifest, manifest_path, static_reused
    )
    counts["residual_paragraphs"] = residual_count
    stage_times["residual_routing"] = residual_seconds
    return manifest, counts, stage_times


def _prepare_static_stage(
    run_directory: Path,
    lexicon_path: Path,
    manifest: WorkflowManifest,
    manifest_path: Path,
    extraction_valid: bool,
) -> tuple[WorkflowManifest, int, float, bool]:
    stage_started = perf_counter()
    static_path = run_directory / "static_paragraphs.jsonl"
    static_valid = extraction_valid and _artifacts_valid(manifest, {"static": static_path})
    if static_valid:
        count = _count_jsonl(static_path)
    else:
        count = normalize_jsonl(run_directory / "paragraphs.jsonl", lexicon_path, static_path)
        manifest = _record_artifacts(manifest, {"static": static_path}, manifest_path)
    manifest = _stage(manifest, "static_cleanup", "complete", manifest_path)
    return manifest, count, round(perf_counter() - stage_started, 3), static_valid


def _prepare_residual_stage(
    run_directory: Path,
    manifest: WorkflowManifest,
    manifest_path: Path,
    static_reused: bool,
) -> tuple[WorkflowManifest, int, float]:
    stage_started = perf_counter()
    residual_path = run_directory / "residual_paragraphs.jsonl"
    if static_reused and _artifacts_valid(manifest, {"residual": residual_path}):
        count = _count_jsonl(residual_path)
    else:
        count = _write_residuals(run_directory / "static_paragraphs.jsonl", residual_path)
        manifest = _record_artifacts(manifest, {"residual": residual_path}, manifest_path)
    manifest = _stage(manifest, "residual_routing", "complete", manifest_path)
    return manifest, count, round(perf_counter() - stage_started, 3)


def _base_report(
    run_id: str,
    run_directory: Path,
    plan_only: bool,
    page_limit: int | None,
    start_leaf: int,
    counts: dict[str, int],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_directory": str(run_directory),
        "scope": _scope_name(plan_only, page_limit, start_leaf),
        "cleanup_complete": False,
        "parts": list(PARTS),
        "page_limit_per_part": page_limit,
        "start_leaf_per_part": start_leaf,
        **counts,
        "manual_review_candidates": _count_manual_review(run_directory / "static_paragraphs.jsonl"),
    }


def _cleanup_is_complete(report: dict[str, Any]) -> bool:
    return (
        report["pending"] == 0
        and report["claimed"] == 0
        and report["review"] == 0
        and report["manual_review_candidates"] == 0
    )


def _scope_name(plan_only: bool, page_limit: int | None, start_leaf: int = 0) -> str:
    if plan_only:
        return "plan_only"
    return "bounded_sample" if page_limit is not None or start_leaf else "full_five_part_run"


def _validate_options(
    root: Path,
    lexicon: Path,
    run_id: str,
    page_limit: int | None,
    start_leaf: int,
    backend: str,
    model: str | None,
    ai_limit: int | None,
    plan_only: bool,
) -> None:
    _validate_run_id(run_id)
    _validate_input_paths(root, lexicon, page_limit, start_leaf)
    _validate_backend(backend, model, ai_limit, plan_only)


def _validate_run_id(run_id: str) -> None:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id) is None:
        raise ValueError("run_id must be a safe 1-128 character artifact name")


def _validate_input_paths(
    root: Path, lexicon: Path, page_limit: int | None, start_leaf: int
) -> None:
    if not root.is_dir() or not lexicon.is_file():
        raise ValueError("root must be a directory and lexicon_path must be a file")
    if page_limit is not None and page_limit < 1:
        raise ValueError("page_limit must be at least one")
    if start_leaf < 0:
        raise ValueError("start_leaf cannot be negative")


def _validate_backend(
    backend: str, model: str | None, ai_limit: int | None, plan_only: bool
) -> None:
    if ai_limit is not None and ai_limit < 0:
        raise ValueError("ai_limit cannot be negative")
    if plan_only:
        return
    if backend in {"ollama", "openai"}:
        _validate_ai_options(model, ai_limit)
    elif backend != "none":
        raise ValueError(f"unsupported backend: {backend}")


def _validate_ai_options(model: str | None, ai_limit: int | None) -> None:
    if not model:
        raise ValueError("an explicit model is required for AI execution")


def _load_or_create_manifest(
    path: Path,
    root: Path,
    lexicon: Path,
    run_id: str,
    page_limit: int | None,
    start_leaf: int,
    run_directory: Path,
) -> WorkflowManifest:
    config = WorkflowConfig(
        root=str(root.resolve()),
        lexicon_path=str(lexicon.resolve()),
        lexicon_sha256=_sha256_file(lexicon),
        page_limit=page_limit,
        start_leaf=start_leaf,
        processing_sha256=_processing_fingerprint(),
    )
    config_sha = _sha256_text(config.model_dump_json())
    parts = _source_parts(root.resolve(), run_directory / "metadata_raw")
    if path.exists():
        return _validate_existing_manifest(path, run_id, config_sha, parts)
    manifest = WorkflowManifest(
        run_id=run_id,
        config=config,
        config_sha256=config_sha,
        parts=parts,
        sample_scope={
            "per_part_page_limit": page_limit,
            "per_part_start_leaf": start_leaf,
            "part_count": len(PARTS),
        },
        limitations=[
            "A page limit applies independently to each of the five source parts.",
            "Residual model routing covers explicit static flags; "
            "contextual OCR errors may remain.",
            "Low-confidence and date/chamber review hints remain review candidates, "
            "not model jobs.",
        ],
    )
    _save_manifest(path, manifest)
    return manifest


def _processing_fingerprint() -> str:
    module_directory = Path(__file__).parent
    files = (
        "extraction.py",
        "models.py",
        "structure.py",
        "static_cleanup.py",
        "normalization.py",
        "pipeline.py",
        "chunking.py",
    )
    digest = hashlib.sha256()
    for name in files:
        digest.update(name.encode())
        digest.update((module_directory / name).read_bytes())
    stages = (
        _extract_classify,
        _extract_part,
        _write_page_paragraphs,
        _write_residuals,
        _write_residual,
    )
    for stage in stages:
        digest.update(inspect.getsource(stage).encode())
    return digest.hexdigest()


def _validate_existing_manifest(
    path: Path, run_id: str, config_sha: str, parts: list[SourcePart]
) -> WorkflowManifest:
    existing = WorkflowManifest.model_validate_json(path.read_text(encoding="utf-8"))
    if existing.run_id != run_id or existing.config_sha256 != config_sha:
        raise ValueError("run ID already exists with a different root, lexicon, or page limit")
    if existing.parts != parts:
        raise ValueError("source part identities or source files changed for this run ID")
    return existing


def _source_parts(root: Path, metadata_directory: Path) -> list[SourcePart]:
    parts = []
    for identifier, part_number in PARTS.items():
        parts.append(_source_part(root, metadata_directory, identifier, part_number))
    return parts


def _source_part(
    root: Path, metadata_directory: Path, identifier: str, part_number: int
) -> SourcePart:
    hocr = expected_paths(root, identifier)["hocr.html"]
    djvu = expected_paths(root, identifier)["djvu.xml"]
    page_map = expected_paths(root, identifier)["page_numbers.json"]
    if not hocr.is_file() or not djvu.is_file() or not page_map.is_file():
        raise ValueError(f"Missing required source derivative for {identifier}")
    metadata = _metadata_source(root, identifier)
    copied = _preserve_metadata(metadata, metadata_directory)
    return SourcePart(
        identifier=identifier,
        part_number=part_number,
        hocr_path=str(hocr),
        hocr_bytes=hocr.stat().st_size,
        hocr_sha256=_sha256_file(hocr),
        djvu_path=str(djvu),
        djvu_bytes=djvu.stat().st_size,
        djvu_sha256=_sha256_file(djvu),
        page_map_path=str(page_map),
        page_map_sha256=_sha256_file(page_map),
        metadata_raw_path=copied,
        metadata_source_path=str(metadata) if metadata else None,
        metadata_raw_sha256=_sha256_file(metadata) if metadata else None,
        metadata_raw_status="preserved" if copied else "not_available",
    )


def _preserve_metadata(metadata: Path | None, destination: Path) -> str | None:
    if metadata is None:
        return None
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / metadata.name
    if not target.exists():
        shutil.copyfile(metadata, target)
    elif _sha256_file(metadata) != _sha256_file(target):
        raise ValueError(f"preserved metadata copy differs from source: {metadata.name}")
    return str(target)


def _metadata_source(root: Path, identifier: str) -> Path | None:
    candidates = (root / f"{identifier}_meta.json", root / f"{identifier}_meta.xml")
    return next((path for path in candidates if path.is_file()), None)


def _extract_classify(
    root: Path, run_directory: Path, page_limit: int | None, start_leaf: int
) -> dict[str, int]:
    page_path = run_directory / "pages.jsonl"
    paragraph_path = run_directory / "paragraphs.jsonl"
    counts = {"pages": 0, "paragraphs": 0}
    with (
        page_path.open("w", encoding="utf-8") as pages,
        paragraph_path.open("w", encoding="utf-8") as paragraphs,
    ):
        for identifier in PARTS:
            page_count, paragraph_count = _extract_part(
                root, identifier, page_limit, start_leaf, pages, paragraphs
            )
            counts["pages"] += page_count
            counts["paragraphs"] += paragraph_count
    return counts


def _extract_part(
    root: Path,
    identifier: str,
    page_limit: int | None,
    start_leaf: int,
    pages: Any,
    paragraphs: Any,
) -> tuple[int, int]:
    page_map = load_page_map(expected_paths(root, identifier)["page_numbers.json"])
    page_count = 0
    paragraph_count = 0
    page_stream = iter_pages(expected_paths(root, identifier)["hocr.html"], page_map)
    started_pages = dropwhile(lambda page: page.scan_leaf < start_leaf, page_stream)
    bounded_pages = started_pages if page_limit is None else islice(started_pages, page_limit)
    for raw_page in bounded_pages:
        page = classify_page(raw_page)
        _write_line(pages, page.model_dump(mode="json"))
        paragraph_count += _write_page_paragraphs(paragraphs, page)
        page_count += 1
    return page_count, paragraph_count


def _write_page_paragraphs(target: Any, page: PageRecord) -> int:
    for paragraph in page.paragraphs:
        _write_line(target, _paragraph_payload(page, paragraph.model_dump(mode="json")))
    return len(page.paragraphs)


def _write_residuals(static_path: Path, output_path: Path) -> int:
    count = 0
    with output_path.open("w", encoding="utf-8") as target:
        for payload in _read_jsonl(static_path):
            paragraph = ParagraphRecord.model_validate(
                {
                    key: value
                    for key, value in payload.items()
                    if key in ParagraphRecord.model_fields
                }
            )
            count += _write_residual(target, payload, paragraph)
    return count


def _count_jsonl(path: Path) -> int:
    with path.open(encoding="utf-8") as source:
        return sum(bool(line.strip()) for line in source)


def _artifacts_valid(manifest: WorkflowManifest, artifacts: dict[str, Path]) -> bool:
    return all(
        path.is_file() and manifest.artifact_sha256.get(name) == _sha256_file(path)
        for name, path in artifacts.items()
    )


def _record_artifacts(
    manifest: WorkflowManifest, artifacts: dict[str, Path], manifest_path: Path
) -> WorkflowManifest:
    hashes = {
        **manifest.artifact_sha256,
        **{name: _sha256_file(path) for name, path in artifacts.items()},
    }
    updated = manifest.model_copy(update={"artifact_sha256": hashes})
    _save_manifest(manifest_path, updated)
    return updated


def _write_residual(target: Any, payload: dict[str, Any], paragraph: ParagraphRecord) -> int:
    if not needs_model(paragraph):
        return 0
    _write_line(target, payload)
    return 1


def _count_manual_review(static_path: Path) -> int:
    count = 0
    for payload in _read_jsonl(static_path):
        paragraph = ParagraphRecord.model_validate(
            {key: value for key, value in payload.items() if key in ParagraphRecord.model_fields}
        )
        count += bool(paragraph.context.get("review_hint"))
    return count


def _run_ai_and_export(
    run_directory: Path,
    run_id: str,
    static_path: Path,
    residual_path: Path,
    pages_path: Path,
    backend: str,
    model: str | None,
    ai_limit: int | None,
    benchmark_summary_path: Path | None,
    input_rate: float | None,
    output_rate: float | None,
    static_seconds: float,
    base_url: str,
    progress_interval: int,
) -> dict[str, Any]:
    database_path = cleanup.run_database(run_directory)
    queue_created, queued = _initialize_queue(database_path, run_id, residual_path)
    status = run_summary(database_path, run_id)
    pending = int(status.get("pending") or 0)
    effective_limit = pending if ai_limit is None else ai_limit
    preflight_path = _write_preflight(
        run_directory,
        benchmark_summary_path,
        pending,
        static_seconds,
        input_rate,
        output_rate,
        backend,
        model,
    )
    _run_selected_jobs(
        run_directory,
        run_id,
        backend,
        model,
        effective_limit,
        base_url,
        progress_interval,
    )
    final_outputs = _export_final_outputs(run_directory, run_id, static_path, pages_path)
    status = run_summary(database_path, run_id)
    return {
        "queue_created": queue_created,
        "jobs_queued": status.get("total", queued),
        "ai_limit": effective_limit,
        "completed": status["completed"],
        "pending": status["pending"],
        "claimed": status["claimed"],
        "review": status["review"],
        **final_outputs,
        "preflight": str(preflight_path),
    }


def _initialize_queue(database_path: Path, run_id: str, residual_path: Path) -> tuple[bool, int]:
    expected = _residual_identities(residual_path)
    existing_count = _validate_existing_queue(database_path, run_id, expected)
    if existing_count is not None:
        return False, existing_count
    created = create_run(database_path, run_id, residual_path)
    if created != len(expected):
        raise ValueError("created cleanup queue count does not match residual inputs")
    return True, created


def _validate_existing_queue(
    database_path: Path, run_id: str, expected: set[tuple[str, str]]
) -> int | None:
    if not database_path.exists():
        return None
    jobs = iter_jobs_for_run(database_path, run_id)
    first = next(jobs, None)
    if first is None:
        return None
    return _match_existing_queue(chain((first,), jobs), expected)


def _match_existing_queue(jobs: Any, expected: set[tuple[str, str]]) -> int:
    remaining = expected.copy()
    count = 0
    for job in jobs:
        identity = _job_identity(job)
        if identity not in remaining:
            raise ValueError("existing cleanup queue does not match this run's residual inputs")
        remaining.remove(identity)
        count += 1
    if remaining:
        raise ValueError("existing cleanup queue does not match this run's residual inputs")
    return count


def _job_identity(job: Any) -> tuple[str, str]:
    payload = json.loads(job.source_json)
    identity = composite_identity(payload)
    text = payload.get("text_normalized")
    if text is None:
        text = payload["text_ocr"]
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    if (
        (job.identity is not None and job.identity != identity)
        or (job.input_hash is not None and job.input_hash != text_hash)
        or job.source_text != text
    ):
        raise ValueError("existing cleanup queue contains a mismatched job payload")
    return identity, text_hash


def _residual_identities(path: Path) -> set[tuple[str, str]]:
    identities = set()
    for payload in _read_jsonl(path):
        text = payload.get("text_normalized")
        if text is None:
            text = payload["text_ocr"]
        identities.add((composite_identity(payload), hashlib.sha256(text.encode()).hexdigest()))
    return identities


def _write_preflight(
    run_directory: Path,
    benchmark_summary_path: Path | None,
    pending: int,
    static_seconds: float,
    input_rate: float | None,
    output_rate: float | None,
    backend: str,
    model: str | None,
) -> Path:
    report = _preflight(
        benchmark_summary_path,
        pending,
        static_seconds,
        input_rate,
        output_rate,
        backend,
        model,
    )
    path = run_directory / "preflight.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, separators=(",", ":")), flush=True)
    return path


def _run_selected_jobs(
    run_directory: Path,
    run_id: str,
    backend: str,
    model: str | None,
    limit: int,
    base_url: str,
    progress_interval: int,
) -> None:
    if backend != "none" and limit > 0:
        cleanup.run_jobs(
            run_directory, run_id, backend, model or "", limit, base_url, progress_interval
        )


def _export_final_outputs(
    run_directory: Path, run_id: str, static_path: Path, pages_path: Path
) -> dict[str, Any]:
    normalized_path = run_directory / "normalized.jsonl"
    cleanup.materialize_all(run_directory, run_id, static_path, normalized_path)
    return _stage_and_publish_outputs(run_directory, pages_path, normalized_path)


def _stage_and_publish_outputs(
    run_directory: Path, pages_path: Path, normalized_path: Path
) -> dict[str, Any]:
    names = ("canonical_pages.jsonl", "chunks.jsonl", "manual_review.jsonl")
    with TemporaryDirectory(prefix=".final-stage-", dir=run_directory) as temp:
        staged = Path(temp)
        canonical, chunks, review_file = (staged / name for name in names)
        merge_normalized_paragraphs(pages_path, normalized_path, canonical)
        chunk_count = build_rag_from_pages(canonical, chunks)
        review_counts = _write_manual_review(normalized_path, review_file)
        validation = _validate_final_outputs(pages_path, canonical, chunks, chunk_count)
        validation.update(review_counts)
        validation["outputs"] = _output_hashes(staged, names)
        report = staged / "validation_report.json"
        report.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
        for name in names:
            os.replace(staged / name, run_directory / name)
        os.replace(report, run_directory / "validation_report.json")
    return {
        "canonical_pages": str(run_directory / names[0]),
        "chunks": str(run_directory / names[1]),
        "manual_review": str(run_directory / names[2]),
        "validation_report": str(run_directory / "validation_report.json"),
        "validation_report_sha256": _sha256_file(run_directory / "validation_report.json"),
        "chunks_written": chunk_count,
        "manual_review_records": review_counts["manual_review_records"],
        "manual_flags": review_counts["manual_flags"],
        "model_queue_records": review_counts["model_queue_records"],
        "unknown_edition_date_pages": validation["unknown_edition_date_pages"],
        "unknown_chamber_pages": validation["unknown_chamber_pages"],
    }


def _write_manual_review(normalized_path: Path, destination: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    records = 0
    with destination.open("w", encoding="utf-8") as target:
        for payload in _read_jsonl(normalized_path):
            reasons = _review_reasons(payload, counts)
            if reasons:
                _write_line(target, _manual_review_payload(payload, reasons))
                records += 1
    return {
        "manual_review_records": records,
        "manual_flags": counts["manual_flag"],
        "model_queue_records": counts["model_queue_record"],
        "model_pending": counts["pending"],
        "model_claimed": counts["claimed"],
        "model_review": counts["review"],
        "model_completed": counts["completed"],
    }


def _review_reasons(payload: dict[str, Any], counts: Counter[str]) -> list[str]:
    reasons = []
    context = payload.get("context", {})
    _append_manual_hints(reasons, context, counts)
    status = payload.get("cleanup_status")
    if status in {"pending", "claimed", "review", "completed"}:
        counts[status] += 1
    if status in {"pending", "claimed", "review"}:
        reasons.append(f"model_cleanup_status:{status}")
        counts["model_queue_record"] += 1
    return reasons


def _append_manual_hints(reasons: list[str], context: dict[str, Any], counts: Counter[str]) -> None:
    for field in ("review_hint", "model_review_reason"):
        hint = context.get(field)
        if hint:
            reasons.append(f"{field}:{hint}")
            counts["manual_flag"] += 1


def _manual_review_payload(payload: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    anchors = (
        "item_identifier",
        "part_number",
        "scan_leaf",
        "printed_page",
        "hocr_page_id",
        "id",
        "line_ids",
        "bbox",
    )
    return {
        **{key: payload.get(key) for key in anchors},
        "role": payload.get("role"),
        "reasons": reasons,
        "cleanup_status": payload.get("cleanup_status"),
        "text_ocr": payload.get("text_ocr"),
        "text_normalized": payload.get("text_normalized"),
        "unresolved_wrap_hints": payload.get("unresolved_wrap_hints", []),
    }


def _validate_final_outputs(
    source_pages: Path, canonical: Path, chunks: Path, expected_chunks: int
) -> dict[str, Any]:
    source_count = _count_jsonl(source_pages)
    page_counts = _canonical_page_counts(canonical)
    chunks_count = _validate_chunks(chunks)
    _validate_output_counts(
        page_counts["canonical_pages"], source_count, chunks_count, expected_chunks
    )
    return {
        "validation_passed": True,
        **page_counts,
        "chunks": chunks_count,
    }


def _canonical_page_counts(path: Path) -> dict[str, int]:
    counts = Counter()
    for payload in _read_jsonl(path):
        page = PageRecord.model_validate(payload)
        counts["pages"] += 1
        counts["paragraphs"] += len(page.paragraphs)
        _count_page_metadata_gaps(counts, page)
    return {
        "canonical_pages": counts["pages"],
        "paragraphs": counts["paragraphs"],
        "unknown_edition_date_pages": counts["unknown_date"],
        "unknown_chamber_pages": counts["unknown_chamber"],
        "pages_missing_date_or_chamber": counts["missing_either"],
    }


def _count_page_metadata_gaps(counts: Counter[str], page: PageRecord) -> None:
    has_date = any(p.context.get("edition_date") for p in page.paragraphs)
    has_chamber = any(p.context.get("chamber") for p in page.paragraphs)
    counts["unknown_date"] += not has_date
    counts["unknown_chamber"] += not has_chamber
    counts["missing_either"] += not (has_date and has_chamber)


def _validate_output_counts(
    pages: int, source_pages: int, chunks: int, expected_chunks: int
) -> None:
    if pages != source_pages or chunks != expected_chunks:
        raise ValueError("final artifact counts do not match their source/export stages")


def _validate_chunks(path: Path) -> int:
    count = 0
    for payload in _read_jsonl(path):
        RAGChunk.model_validate(payload)
        count += 1
    return count


def _output_hashes(directory: Path, names: tuple[str, ...]) -> dict[str, dict[str, str]]:
    return {name: {"path": name, "sha256": _sha256_file(directory / name)} for name in names}


def _preflight(
    summary_path: Path | None,
    eligible_jobs: int,
    static_seconds: float,
    input_rate: float | None,
    output_rate: float | None,
    backend: str,
    model: str | None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "eligible_jobs": eligible_jobs,
        "static_cleanup_seconds": static_seconds,
        "benchmark_summary": str(summary_path) if summary_path else None,
        "estimate": None,
    }
    if summary_path is None and (input_rate is not None or output_rate is not None):
        raise ValueError("a benchmark summary is required when supplying token prices")
    if summary_path is not None:
        from congressional_globe.planning import estimate, load_summary

        summary = load_summary(summary_path)
        _validate_benchmark_match(summary, backend, model)
        report["estimate"] = estimate(
            summary,
            eligible_jobs,
            input_usd_per_million=input_rate,
            output_usd_per_million=output_rate,
        ).model_dump(mode="json")
    return report


def _validate_benchmark_match(summary: Any, backend: str, model: str | None) -> None:
    if backend == "none":
        return
    if summary.backend != backend or (model is not None and summary.model != model):
        raise ValueError("benchmark backend/model must match the selected cleanup backend/model")


def _empty_status() -> dict[str, int]:
    return {"total": 0, "completed": 0, "pending": 0, "claimed": 0, "review": 0}


def _stage(manifest: WorkflowManifest, name: str, state: str, path: Path) -> WorkflowManifest:
    stages = {**manifest.stages, name: state}
    updated = manifest.model_copy(update={"stages": stages})
    _save_manifest(path, updated)
    return updated


def _save_manifest(path: Path, manifest: WorkflowManifest) -> None:
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
