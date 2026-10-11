"""Resumable cleanup orchestration and local observability artifacts."""

from __future__ import annotations

import fcntl
import hashlib
import json
from contextlib import contextmanager
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
    composite_identity,
    jobs_for_run,
    progress,
    release_claimed,
    retry_job,
    review_job,
    review_job_result,
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
    with _worker_lock(run_directory, run_id):
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


@contextmanager
def _worker_lock(run_directory: Path, run_id: str):
    run_directory.mkdir(parents=True, exist_ok=True)
    lock_path = run_directory / f"{run_id}.worker.lock"
    with lock_path.open("a", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"A cleanup worker already holds the lock for {run_id}") from error
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def export_results(run_directory: Path, run_id: str, output: Path) -> int:
    jobs = completed_jobs(run_database(run_directory), run_id)
    with output.open("w", encoding="utf-8") as target:
        for job in jobs:
            target.write(json.dumps(_export_payload(job), separators=(",", ":")) + "\n")
    return len(jobs)


def materialize_all(run_directory: Path, run_id: str, static_path: Path, output_path: Path) -> int:
    """Compose a full static corpus with only matching, validated completed AI results."""
    _reject_materialize_alias(static_path, output_path)
    jobs = _jobs_by_identity(jobs_for_run(run_database(run_directory), run_id))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with (
        static_path.open(encoding="utf-8") as source,
        output_path.open("w", encoding="utf-8") as target,
    ):
        for line in source:
            if not line.strip():
                continue
            payload = json.loads(line)
            composed = _compose_record(payload, jobs)
            target.write(json.dumps(composed, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count


def _reject_materialize_alias(static_path: Path, output_path: Path) -> None:
    if static_path.resolve() == output_path.resolve():
        raise ValueError("materialized output must differ from static input")
    if static_path.exists() and output_path.exists() and static_path.samefile(output_path):
        raise ValueError("materialized output must differ from static input")


def _jobs_by_identity(jobs: list[CleanupJob]) -> dict[tuple[str, str], CleanupJob]:
    return {
        (
            job.identity or composite_identity(json.loads(job.source_json)),
            job.input_hash or hashlib.sha256(job.source_text.encode()).hexdigest(),
        ): job
        for job in jobs
    }


def _compose_record(
    payload: dict[str, Any], jobs: dict[tuple[str, str], CleanupJob]
) -> dict[str, Any]:
    text = payload.get("text_normalized")
    if text is None:
        text = payload["text_ocr"]
    input_hash = hashlib.sha256(text.encode()).hexdigest()
    job = jobs.get((composite_identity(payload), input_hash))
    if job is None:
        return {**payload, "cleanup_status": "not_queued"}
    if job.status != "completed":
        return {**payload, "cleanup_status": job.status}
    return _compose_completed(payload, job, text, input_hash)


def _compose_completed(
    payload: dict[str, Any], job: CleanupJob, ai_input: str, input_hash: str
) -> dict[str, Any]:
    result = json.loads(job.result_json or "{}")
    cleanup = CleanupResult.model_validate(result["cleanup"])
    if cleanup.needs_image_review:
        return {**payload, "cleanup_status": "review"}
    edits = [TextEdit.model_validate(edit) for edit in result["applied_edits"]]
    _validate_static_input(payload, job.source_text)
    normalized = apply_edits(ai_input, edits)
    if normalized != result.get("text_normalized"):
        raise ValueError(f"Completed cleanup output mismatch for {job.id}")
    return {
        **payload,
        "text_normalized": normalized,
        "ai_edits": [edit.model_dump(mode="json") for edit in edits],
        "ai_input_text": ai_input,
        "ai_input_sha256": input_hash,
        "cleanup_status": "completed",
        "ai_provenance": _ai_provenance(payload, edits, input_hash, job, result.get("usage", {})),
    }


def _validate_static_input(payload: dict[str, Any], input_text: str) -> None:
    raw = payload["text_ocr"]
    static_edits = [TextEdit.model_validate(edit) for edit in payload.get("static_edits", [])]
    if apply_edits(raw, static_edits) != input_text:
        raise ValueError("static edit ledger does not reproduce AI input")


def _combined_ledger(
    payload: dict[str, Any], edits: list[TextEdit], input_hash: str, job: CleanupJob
) -> list[dict[str, Any]]:
    return [
        {"stage": "static", "edits": payload.get("static_edits", [])},
        {
            "stage": "ai",
            "input_hash": input_hash,
            "model_identity": f"{job.backend}:{job.model}",
            "edits": [edit.model_dump(mode="json") for edit in edits],
        },
    ]


def _ai_provenance(
    payload: dict[str, Any],
    edits: list[TextEdit],
    input_hash: str,
    job: CleanupJob,
    usage: dict[str, int],
) -> dict[str, Any]:
    return {
        "model_identity": f"{job.backend}:{job.model}",
        "usage": usage,
        "edit_ledger": _combined_ledger(payload, edits, input_hash, job),
    }


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
    provider_result = None
    try:
        provider_result = provider.clean(job.source_text)
        _raw_response_path(run_directory, job).write_text(
            provider_result.raw_response, encoding="utf-8"
        )
        if provider_result.cleanup.needs_image_review:
            _record_provider_review(run_directory, database_path, job, provider_result, started)
            return True
        applied_edits = resolve_edits(job.source_text, provider_result.cleanup.edits)
        normalized = apply_edits(job.source_text, applied_edits)
    except APIConnectionError as error:
        _record_retry(run_directory, database_path, job, str(error), started)
        return False
    except Exception as error:
        _record_review(run_directory, database_path, job, str(error), started, provider_result)
        return True
    else:
        _record_completion(
            run_directory,
            database_path,
            job,
            provider_result,
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
    provider_result: Any,
    applied_edits: list[TextEdit],
    normalized: str,
    started: float,
) -> None:
    duration_ms = _duration(started)
    source = json.loads(job.source_json)
    input_hash = hashlib.sha256(job.source_text.encode()).hexdigest()
    _validate_static_input(source, job.source_text)
    payload = {
        "cleanup": provider_result.cleanup.model_dump(mode="json"),
        "applied_edits": [edit.model_dump(mode="json") for edit in applied_edits],
        "text_normalized": normalized,
        "ai_edits": [edit.model_dump(mode="json") for edit in applied_edits],
        "ai_input_text": job.source_text,
        "ai_input_sha256": input_hash,
        "usage": provider_result.usage,
        "ai_provenance": _ai_provenance(
            source, applied_edits, input_hash, job, provider_result.usage
        ),
    }
    complete_job(
        database_path,
        job.id,
        payload,
        duration_ms,
        provider_result.raw_response,
        provider_result.usage,
    )
    _event(
        run_directory,
        job,
        "completed",
        duration_ms,
        {"edit_count": len(applied_edits), "usage": provider_result.usage},
    )


def _record_review(
    run_directory: Path,
    database_path: Path,
    job: CleanupJob,
    error: str,
    started: float,
    provider_result: Any = None,
) -> None:
    duration_ms = _duration(started)
    if provider_result is None:
        review_job(database_path, job.id, error, duration_ms)
    else:
        review_job_result(
            database_path,
            job.id,
            error,
            duration_ms,
            provider_result.raw_response,
            provider_result.usage,
        )
    _event(run_directory, job, "review", duration_ms, {"reason": error})


def _record_provider_review(
    run_directory: Path,
    database_path: Path,
    job: CleanupJob,
    provider_result: Any,
    started: float,
) -> None:
    reason = provider_result.cleanup.review_reason or "provider requested image review"
    _record_review(run_directory, database_path, job, reason, started, provider_result)


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
