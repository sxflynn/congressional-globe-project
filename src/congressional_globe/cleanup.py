"""Resumable cleanup orchestration and local observability artifacts."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Lock, Thread
from time import perf_counter
from typing import Any

from openai import APIConnectionError

from congressional_globe.models import CleanupResult, TextEdit
from congressional_globe.normalization import apply_edits, resolve_edits, validate_edit_shapes
from congressional_globe.providers import (
    CleanupProvider,
    OllamaProvider,
    OpenAIResponsesProvider,
    ProviderOutputError,
)
from congressional_globe.storage import (
    CleanupJob,
    claim_next,
    complete_job,
    completed_jobs,
    composite_identity,
    materialization_lookup,
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
    max_seconds: float | None = None,
) -> dict[str, int]:
    if max_seconds is not None and max_seconds <= 0:
        raise ValueError("max_seconds must be positive")
    deadline = None if max_seconds is None else perf_counter() + max_seconds
    with _worker_lock(run_directory, run_id):
        provider = _provider(backend, model, base_url)
        database_path = run_database(run_directory)
        release_claimed(database_path, run_id)
        _drain_jobs(
            run_directory,
            database_path,
            run_id,
            backend,
            model,
            limit,
            provider,
            progress_interval,
            deadline,
        )
        return progress(database_path, run_id)


def _drain_jobs(
    run_directory: Path,
    database_path: Path,
    run_id: str,
    backend: str,
    model: str,
    limit: int,
    provider: CleanupProvider,
    progress_interval: int,
    deadline: float | None,
) -> None:
    for _ in range(limit):
        job = _claim_before_deadline(database_path, run_id, backend, model, deadline)
        if job is None or not _process_claimed_job(
            run_directory, database_path, job, provider, progress_interval
        ):
            return


def _claim_before_deadline(
    database_path: Path,
    run_id: str,
    backend: str,
    model: str,
    deadline: float | None,
) -> CleanupJob | None:
    if deadline is not None and perf_counter() >= deadline:
        return None
    return claim_next(database_path, run_id, backend, model)


def _process_claimed_job(
    run_directory: Path,
    database_path: Path,
    job: CleanupJob,
    provider: CleanupProvider,
    progress_interval: int,
) -> bool:
    _event(run_directory, job, "claimed", 0, {})
    return _process_job(run_directory, database_path, job, provider, progress_interval)


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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with (
            os.fdopen(descriptor, "w", encoding="utf-8") as target,
            _worker_lock(run_directory, run_id),
        ):
            count = _write_materialized(run_directory, run_id, static_path, target)
        os.replace(temporary_path, output_path)
        return count
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _write_materialized(run_directory: Path, run_id: str, static_path: Path, target: Any) -> int:
    count = 0
    with (
        materialization_lookup(run_database(run_directory), run_id) as lookup,
        static_path.open(encoding="utf-8") as source,
    ):
        find_job, mark_review = lookup
        for line in source:
            if not line.strip():
                continue
            payload = json.loads(line)
            text = payload.get("text_normalized")
            if text is None:
                text = payload["text_ocr"]
            input_hash = hashlib.sha256(text.encode()).hexdigest()
            job = find_job(composite_identity(payload), input_hash, payload["id"])
            composed = _compose_record(payload, job, text, input_hash, mark_review)
            target.write(json.dumps(composed, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count


def _reject_materialize_alias(static_path: Path, output_path: Path) -> None:
    if static_path.resolve() == output_path.resolve():
        raise ValueError("materialized output must differ from static input")
    if static_path.exists() and output_path.exists() and static_path.samefile(output_path):
        raise ValueError("materialized output must differ from static input")


def _compose_record(
    payload: dict[str, Any],
    job: CleanupJob | None,
    text: str,
    input_hash: str,
    mark_review: Any,
) -> dict[str, Any]:
    if job is None:
        return {**payload, "cleanup_status": "not_queued"}
    if job.status != "completed":
        return (
            _review_payload(payload, job.error)
            if job.status == "review"
            else {
                **payload,
                "cleanup_status": job.status,
            }
        )
    return _compose_completed(payload, job, text, input_hash, mark_review)


def _compose_completed(
    payload: dict[str, Any],
    job: CleanupJob,
    ai_input: str,
    input_hash: str,
    mark_review: Any,
) -> dict[str, Any]:
    try:
        result, edits, normalized = _validated_completed_result(payload, job, ai_input)
    except (KeyError, TypeError, ValueError) as error:
        reason = f"materialization validation failed: {error}"
        mark_review(job, reason)
        return _review_payload(payload, reason)
    return {
        **payload,
        "text_normalized": normalized,
        "ai_edits": [edit.model_dump(mode="json") for edit in edits],
        "ai_input_text": ai_input,
        "ai_input_sha256": input_hash,
        "cleanup_status": "completed",
        "ai_provenance": _ai_provenance(payload, edits, input_hash, job, result.get("usage", {})),
    }


def _validated_completed_result(
    payload: dict[str, Any], job: CleanupJob, ai_input: str
) -> tuple[dict[str, Any], list[TextEdit], str]:
    result = json.loads(job.result_json or "{}")
    cleanup = CleanupResult.model_validate(result["cleanup"])
    if cleanup.needs_image_review:
        raise ValueError(cleanup.review_reason or "provider requested image review")
    edits = [TextEdit.model_validate(edit) for edit in result["applied_edits"]]
    _validate_static_input(payload, job.source_text)
    validate_edit_shapes(ai_input, edits)
    normalized = apply_edits(ai_input, edits)
    if normalized != result.get("text_normalized"):
        raise ValueError(f"Completed cleanup output mismatch for {job.id}")
    return result, edits, normalized


def _review_payload(payload: dict[str, Any], reason: str | None) -> dict[str, Any]:
    context = dict(payload.get("context") or {})
    context["model_review_reason"] = reason or "cleanup result requires review"
    return {**payload, "cleanup_status": "review", "context": context}


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
        validate_edit_shapes(job.source_text, applied_edits)
        normalized = apply_edits(job.source_text, applied_edits)
    except APIConnectionError as error:
        _record_retry(run_directory, database_path, job, str(error), started)
        return False
    except Exception as error:
        _record_review(
            run_directory,
            database_path,
            job,
            str(error),
            started,
            provider_result,
            error if isinstance(error, ProviderOutputError) else None,
        )
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
    _result_event(
        run_directory,
        job,
        duration_ms,
        "completed",
        normalized,
        "accepted_normalized",
        applied_edits,
        provider_result=provider_result,
    )


def _record_review(
    run_directory: Path,
    database_path: Path,
    job: CleanupJob,
    error: str,
    started: float,
    provider_result: Any = None,
    provider_error: ProviderOutputError | None = None,
) -> None:
    duration_ms = _duration(started)
    raw_response = None
    usage = None
    if provider_result is None:
        if provider_error is None:
            review_job(database_path, job.id, error, duration_ms)
        else:
            raw_response = provider_error.raw_response
            usage = provider_error.usage
            _raw_response_path(run_directory, job).write_text(raw_response, encoding="utf-8")
            review_job_result(database_path, job.id, error, duration_ms, raw_response, usage)
    else:
        raw_response = provider_result.raw_response
        usage = provider_result.usage
        review_job_result(
            database_path,
            job.id,
            error,
            duration_ms,
            provider_result.raw_response,
            provider_result.usage,
        )
    _event(run_directory, job, "review", duration_ms, {"reason": error})
    _result_event(
        run_directory,
        job,
        duration_ms,
        "review",
        job.source_text,
        "unchanged_retained_input",
        [],
        provider_result=provider_result,
        error=error,
        raw_response=raw_response,
        usage=usage,
        finish_reason=getattr(provider_error, "finish_reason", None),
        output_status=getattr(provider_error, "output_status", None),
    )


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
    _result_event(
        run_directory,
        job,
        duration_ms,
        "retry_pending",
        job.source_text,
        "unchanged_retained_input",
        [],
        error=error,
    )


def _result_event(
    run_directory: Path,
    job: CleanupJob,
    duration_ms: int,
    status: str,
    after_text: str,
    after_text_kind: str,
    applied_edits: list[TextEdit],
    *,
    provider_result: Any = None,
    error: str | None = None,
    raw_response: str | None = None,
    usage: dict[str, int] | None = None,
    finish_reason: str | None = None,
    output_status: str | None = None,
) -> None:
    source = json.loads(job.source_json)
    details = {
        "run_id": job.run_id,
        "identity": job.identity,
        "item_identifier": source.get("item_identifier"),
        "part_number": source.get("part_number"),
        "scan_leaf": source.get("scan_leaf"),
        "printed_page": source.get("printed_page"),
        "hocr_page_id": source.get("hocr_page_id"),
        "line_ids": source.get("line_ids"),
        "bbox": source.get("bbox"),
        "status": status,
        "recorded_at": datetime.now(UTC).isoformat(),
        "before_text": job.source_text,
        "after_text": after_text,
        "after_text_kind": after_text_kind,
        "applied_edits": [edit.model_dump(mode="json") for edit in applied_edits],
        "error": error,
        "raw_response": (
            raw_response
            if raw_response is not None
            else getattr(provider_result, "raw_response", None)
        ),
        "usage": usage if usage is not None else getattr(provider_result, "usage", {}),
        "finish_reason": finish_reason or getattr(provider_result, "finish_reason", None),
        "output_status": output_status or getattr(provider_result, "output_status", None),
    }
    _event(run_directory, job, "result", duration_ms, details)


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
