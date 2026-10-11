"""Resumable cleanup orchestration and local observability artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Event, Lock, Thread
from time import perf_counter
from typing import Any

from openai import APIConnectionError

from congressional_globe.models import CleanupResult, TextEdit
from congressional_globe.normalization import apply_edits, resolve_edits
from congressional_globe.providers import CleanupProvider, OllamaProvider, OpenAIResponsesProvider
from congressional_globe.storage import (
    CleanupJob,
    claim_next,
    complete_job,
    completed_jobs,
    progress,
    release_claimed,
    retry_job,
    review_job,
)

EVENT_LOCK = Lock()


def run_database(run_directory: Path) -> Path:
    return run_directory / "jobs.sqlite"


def run_jobs(
    run_directory: Path,
    run_id: str,
    backend: str,
    model: str,
    limit: int,
    base_url: str,
    progress_interval: int,
) -> dict[str, int]:
    provider = _provider(backend, model, base_url)
    database_path = run_database(run_directory)
    release_claimed(database_path, run_id)
    for _ in range(limit):
        job = claim_next(database_path, run_id, backend, model)
        if job is None:
            break
        _event(run_directory, job, "claimed", 0, {})
        if not _process_job(run_directory, database_path, job, provider, progress_interval):
            break
    return progress(database_path, run_id)


def export_results(run_directory: Path, run_id: str, output: Path) -> int:
    jobs = completed_jobs(run_database(run_directory), run_id)
    with output.open("w", encoding="utf-8") as target:
        for job in jobs:
            target.write(json.dumps(_export_payload(job), separators=(",", ":")) + "\n")
    return len(jobs)


def _provider(backend: str, model: str, base_url: str) -> CleanupProvider:
    if backend == "ollama":
        return OllamaProvider(model, base_url)
    if backend == "openai":
        return OpenAIResponsesProvider(model)
    raise ValueError(f"Unsupported backend: {backend}")


def _process_job(
    run_directory: Path,
    database_path: Path,
    job: CleanupJob,
    provider: CleanupProvider,
    progress_interval: int,
) -> bool:
    started = perf_counter()
    stop, heartbeat = _start_heartbeat(run_directory, job, started, progress_interval)
    try:
        result = provider.clean(job.source_text)
        _raw_response_path(run_directory, job).write_text(result.raw_response, encoding="utf-8")
        applied_edits = resolve_edits(job.source_text, result.cleanup.edits)
        normalized = apply_edits(job.source_text, applied_edits)
    except APIConnectionError as error:
        _record_retry(run_directory, database_path, job, str(error), started)
        return False
    except Exception as error:
        _record_review(run_directory, database_path, job, str(error), started)
        return True
    else:
        _record_completion(
            run_directory,
            database_path,
            job,
            result.cleanup,
            applied_edits,
            normalized,
            started,
        )
        return True
    finally:
        stop.set()
        heartbeat.join()


def _record_completion(
    run_directory: Path,
    database_path: Path,
    job: CleanupJob,
    cleanup: CleanupResult,
    applied_edits: list[TextEdit],
    normalized: str,
    started: float,
) -> None:
    duration_ms = _duration(started)
    payload = {
        "cleanup": cleanup.model_dump(mode="json"),
        "applied_edits": [edit.model_dump(mode="json") for edit in applied_edits],
        "text_normalized": normalized,
    }
    complete_job(database_path, job.id, payload, duration_ms)
    _event(run_directory, job, "completed", duration_ms, {"edit_count": len(applied_edits)})


def _record_review(
    run_directory: Path, database_path: Path, job: CleanupJob, error: str, started: float
) -> None:
    duration_ms = _duration(started)
    review_job(database_path, job.id, error, duration_ms)
    _event(run_directory, job, "review", duration_ms, {"reason": error})


def _record_retry(
    run_directory: Path, database_path: Path, job: CleanupJob, error: str, started: float
) -> None:
    duration_ms = _duration(started)
    retry_job(database_path, job.id, error, duration_ms)
    _event(run_directory, job, "retry", duration_ms, {"reason": error})


def _event(
    run_directory: Path,
    job: CleanupJob,
    outcome: str,
    duration_ms: int,
    details: dict[str, Any],
) -> None:
    payload = {
        "event": f"job_{outcome}",
        "job_id": job.id,
        "paragraph_id": job.paragraph_id,
        "backend": job.backend,
        "model": job.model,
        "duration_ms": duration_ms,
        **details,
    }
    with EVENT_LOCK:
        with (run_directory / "events.jsonl").open("a", encoding="utf-8") as target:
            target.write(json.dumps(payload, separators=(",", ":")) + "\n")
        print(json.dumps(payload, separators=(",", ":")), flush=True)


def _start_heartbeat(
    run_directory: Path, job: CleanupJob, started: float, progress_interval: int
) -> tuple[Event, Thread]:
    if progress_interval < 1:
        raise ValueError("progress_interval must be at least one second")
    stop = Event()
    heartbeat = Thread(
        target=_heartbeat,
        args=(run_directory, job, started, progress_interval, stop),
        daemon=True,
    )
    heartbeat.start()
    return stop, heartbeat


def _heartbeat(
    run_directory: Path, job: CleanupJob, started: float, progress_interval: int, stop: Event
) -> None:
    while not stop.wait(progress_interval):
        _event(run_directory, job, "heartbeat", _duration(started), {})


def _raw_response_path(run_directory: Path, job: CleanupJob) -> Path:
    directory = run_directory / "responses"
    directory.mkdir(exist_ok=True)
    return directory / f"{job.id}.json"


def _duration(started: float) -> int:
    return round((perf_counter() - started) * 1000)


def _export_payload(job: CleanupJob) -> dict[str, Any]:
    source = json.loads(job.source_json)
    result = json.loads(job.result_json or "{}")
    return {
        **source,
        **result,
        "cleanup_job_id": job.id,
        "cleanup_backend": job.backend,
        "cleanup_model": job.model,
    }
