"""Explicitly opted-in, sequential Ollama transport for frozen reading requests."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field

from congressional_globe.providers import _ollama_request_lock
from congressional_globe.reading_contracts import (
    EvidenceSpan,
    ReadingCandidate,
    ReadingReply,
    validate_reply,
)
from congressional_globe.reading_controls import control_passes
from congressional_globe.reading_quotes import QuoteReadingReply, validate_quote_reply
from congressional_globe.reading_requests import materialize_record
from congressional_globe.reading_run_store import ReadingRunStore

MAX_CALLS = 60
MAX_TOTAL_SECONDS = 7200
MAX_MODEL_SECONDS = 2400
MAX_CALL_SECONDS = 120


class RequestReadiness(BaseModel):
    """Evidence bound to one exact frozen request; booleans alone cannot authorize it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    token_fit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_expectation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_effort_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_input_tokens: int = Field(ge=0)
    token_fit_verified: bool
    source_expectations_frozen: bool
    review_effort_resolved: bool


class RuntimeCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    checked_at: datetime
    runtime_version: str = Field(min_length=1)
    process_state_verified: bool
    process_observation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_digests: dict[str, str]


def verify_runtime(base_url: str, expected: dict[str, str], timeout: float = 5) -> RuntimeCheck:
    """Read-only fresh Ollama tags/ps check; caller must supply process observation."""
    _check_local_url(base_url)
    tags = _get_json(base_url.rstrip("/") + "/api/tags", timeout)
    ps = _get_json(base_url.rstrip("/") + "/api/ps", timeout)
    version = _get_json(base_url.rstrip("/") + "/api/version", timeout)
    actual = {model["name"]: model["digest"] for model in tags.get("models", [])}
    if any(actual.get(name) != digest for name, digest in expected.items()):
        raise ValueError("runtime model tags do not match the frozen model digests")
    if not isinstance(ps.get("models"), list):
        raise ValueError("runtime process response is malformed")
    return RuntimeCheck(
        checked_at=datetime.now(UTC),
        runtime_version=str(version.get("version") or "unknown"),
        process_state_verified=False,
        process_observation_sha256="0" * 64,
        model_digests={name: actual[name] for name in expected},
    )


def _get_json(url: str, timeout: float) -> dict:
    with urlopen(Request(url, method="GET"), timeout=timeout) as response:
        return json.loads(response.read())


def _post_raw(url: str, body: bytes, timeout: float, opener: Callable = urlopen) -> str:
    request = Request(url, data=body, headers={"Content-Type": "application/json"})
    with opener(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def _guard_readiness(record: dict, evidence: RequestReadiness | dict) -> RequestReadiness:
    proof = RequestReadiness.model_validate(evidence)
    if (proof.request_sha256, proof.model_digest) != (
        record["request_sha256"],
        record["model_digest"],
    ):
        raise ValueError("readiness evidence does not bind this exact request and model")
    return proof


def _coverage(record: dict) -> dict[str, list[EvidenceSpan]]:
    return {
        image["id"]: [EvidenceSpan.model_validate(span) for span in image["sources"]]
        for image in record["images"]
    }


def _task_id(record: dict) -> str:
    control = record.get("control_kind")
    if control is not None and control not in {"missing_image", "unrelated_image"}:
        raise ValueError("unknown frozen reading control kind")
    if control:
        return f"{record['model']}::{control}::{record['unit_id']}"
    return f"{record['model']}::{record['unit_id']}"


def _usage(reply: dict) -> dict | None:
    keys = ("prompt_eval_count", "eval_count", "total_duration", "load_duration")
    usage = {key: reply[key] for key in keys if key in reply}
    return usage or None


def _check_local_url(base_url: str) -> None:
    parsed = urlsplit(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Ollama dispatch must target a local loopback HTTP endpoint")


def _response_content(reply: dict) -> str:
    message = reply.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ValueError("Ollama response has no message content")
    return message["content"]


def _attempt(
    store: ReadingRunStore,
    record: dict,
    unit: ReadingCandidate,
    base_url: str,
    timeout: float,
    opener: Callable,
) -> dict:
    request_body = materialize_record(record)
    task_id = _task_id(record)
    attempt_id = store.claim(task_id, json.loads(request_body))
    started = time.monotonic()
    raw_or_error = _send(
        store, attempt_id, task_id, base_url, request_body, timeout, opener, started
    )
    if isinstance(raw_or_error, dict):
        return raw_or_error
    return _save_and_validate(store, attempt_id, task_id, record, unit, raw_or_error, started)


def _send(store, attempt_id, task_id, base_url, request_body, timeout, opener, started):
    try:
        return _post_raw(base_url.rstrip("/") + "/api/chat", request_body, timeout, opener)
    except TimeoutError as error:
        elapsed = time.monotonic() - started
        store.record_transport_error(attempt_id, str(error), elapsed)
        return {"task_id": task_id, "status": "timeout", "attempt_id": attempt_id}
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        store.record_reply(attempt_id, f"HTTP {error.code}: {detail}", None)
        store.record_elapsed(attempt_id, time.monotonic() - started)
        store.fail(attempt_id, "failed", f"HTTP {error.code}: {detail}")
        return {"task_id": task_id, "status": "failed", "attempt_id": attempt_id}
    except (URLError, OSError, ValueError) as error:
        elapsed = time.monotonic() - started
        store.record_transport_error(attempt_id, str(error), elapsed)
        return {"task_id": task_id, "status": "inflight", "attempt_id": attempt_id}


def _invalid_reply(store, attempt_id, task_id, raw, detail, started, is_control=False):
    store.record_reply(attempt_id, raw, None)
    store.complete(attempt_id, "invalid", detail)
    result = {
        "task_id": task_id,
        "status": "invalid",
        "detail": detail,
        "attempt_id": attempt_id,
        "elapsed_seconds": time.monotonic() - started,
    }
    if is_control:
        result["control_result"] = "failed"
    return result


def _save_and_validate(store, attempt_id, task_id, record, unit, raw, started):
    try:
        reply = json.loads(raw)
    except ValueError as error:
        return _invalid_reply(
            store, attempt_id, task_id, raw, str(error), started, bool(record.get("control_kind"))
        )
    if not isinstance(reply, dict):
        return _invalid_reply(
            store,
            attempt_id,
            task_id,
            raw,
            "Ollama response must be a JSON object",
            started,
            bool(record.get("control_kind")),
        )
    usage = _usage(reply)
    store.record_reply(attempt_id, raw, usage)
    store.record_elapsed(attempt_id, time.monotonic() - started)
    return _validate_saved_reply(store, attempt_id, task_id, record, unit, reply, usage, started)


def _validate_saved_reply(store, attempt_id, task_id, record, unit, reply, usage, started):
    try:
        parsed, derived = _parse_and_derive(record, unit, reply)
    except (ValueError, TypeError) as error:
        return _invalid_saved_reply(store, attempt_id, task_id, record, error, started)
    store.complete(attempt_id, "valid")
    return {
        "task_id": task_id,
        "status": "valid",
        "reply": parsed.model_dump(),
        "derived": derived,
        "attempt_id": attempt_id,
        "elapsed_seconds": time.monotonic() - started,
        "usage": usage,
        **({"control_result": "passed"} if record.get("control_kind") else {}),
    }


def _parse_and_derive(record, unit, reply):
    expected = record["expected_input_tokens"]
    _validate_response(reply, record, expected)
    coverage = {} if record.get("control_kind") else _coverage(record)
    parsed, derived = _derive_response(record, unit, _response_content(reply), coverage)
    if record.get("control_kind") and not control_passes(unit, parsed):
        raise ValueError("source-evidence control did not preserve uncertainty across targets")
    return parsed, derived


def _derive_response(record, unit, content, coverage):
    contract = record.get("response_contract", "offset-v1")
    if contract == "quote-v2":
        return validate_quote_reply(unit, QuoteReadingReply.model_validate_json(content), coverage)
    if contract != "offset-v1":
        raise ValueError("unknown reading response contract")
    parsed = ReadingReply.model_validate_json(content)
    return parsed, validate_reply(unit, parsed, coverage)


def _invalid_saved_reply(store, attempt_id, task_id, record, error, started):
    store.complete(attempt_id, "invalid", str(error))
    result = _invalid_result(task_id, attempt_id, str(error), started)
    if isinstance(error, _InputParityError):
        result["halt_batch"] = True
    if record.get("control_kind"):
        result["control_result"] = "failed"
    return result


def _invalid_result(task_id, attempt_id, detail, started):
    return {
        "task_id": task_id,
        "status": "invalid",
        "detail": detail,
        "attempt_id": attempt_id,
        "elapsed_seconds": time.monotonic() - started,
    }


class _InputParityError(ValueError):
    pass


def _validate_response(reply: dict, record: dict, expected_input_tokens: int) -> None:
    options = record["options"]
    _validate_reply_identity(reply, record)
    prompt_tokens, output_tokens = _require_token_counts(reply)
    if prompt_tokens != expected_input_tokens:
        raise _InputParityError(
            f"prompt token parity mismatch: expected {expected_input_tokens}, got {prompt_tokens}"
        )
    _validate_context_envelope(prompt_tokens, output_tokens, options)
    if reply.get("done_reason") == "length":
        raise ValueError("Ollama response is incomplete or output-truncated")


def _validate_reply_identity(reply: dict, record: dict) -> None:
    if reply.get("model") != record["model"]:
        raise _InputParityError("Ollama response model does not match the frozen request")
    done_reason = reply.get("done_reason")
    if reply.get("done") is not True or not isinstance(done_reason, str) or not done_reason:
        raise ValueError("Ollama response is incomplete or lacks a completion reason")


def _require_token_counts(reply: dict) -> tuple[int, int]:
    prompt_tokens = reply.get("prompt_eval_count")
    output_tokens = reply.get("eval_count")
    if not isinstance(prompt_tokens, int) or not isinstance(output_tokens, int):
        raise ValueError("Ollama response lacks token usage required for envelope checks")
    return prompt_tokens, output_tokens


def _validate_context_envelope(prompt_tokens: int, output_tokens: int, options: dict) -> None:
    if prompt_tokens + options["num_predict"] > options["num_ctx"]:
        raise ValueError("Ollama prompt usage plus output reserve exceeds request context")
    if output_tokens > options["num_predict"]:
        raise ValueError("Ollama output token count exceeds the frozen output reserve")


def dispatch(
    store: ReadingRunStore,
    records: list[dict],
    units: dict[str, ReadingCandidate],
    readiness: dict[str, RequestReadiness | dict],
    runtime: RuntimeCheck | dict,
    base_url: str,
    *,
    opt_in: bool = False,
    opener: Callable = urlopen,
    lock_factory: Callable = _ollama_request_lock,
    max_calls: int = MAX_CALLS,
    total_seconds: int = MAX_TOTAL_SECONDS,
    per_model_seconds: int = MAX_MODEL_SECONDS,
    call_seconds: int = MAX_CALL_SECONDS,
    stop_file: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Dispatch in manifest order; never resumes an unresolved request or retries."""
    proof = RuntimeCheck.model_validate(runtime)
    _check_local_url(base_url)
    _check_launch(
        store, records, proof, opt_in, max_calls, total_seconds, per_model_seconds, call_seconds
    )
    _guard_manifest(store, records, units, readiness, proof)
    return _run_pending(
        store,
        [
            {
                **record,
                "expected_input_tokens": RequestReadiness.model_validate(
                    readiness[_task_id(record)]
                ).expected_input_tokens,
            }
            for record in records
        ],
        units,
        base_url,
        opener,
        lock_factory,
        total_seconds,
        per_model_seconds,
        call_seconds,
        max_calls,
        Path(stop_file) if stop_file is not None else None,
    )


def _check_launch(
    store, records, proof, opt_in, max_calls, total_seconds, per_model_seconds, call_seconds
) -> None:
    _check_opt_in(opt_in)
    _check_runtime_observation(proof)
    _check_limits(records, max_calls, total_seconds, per_model_seconds, call_seconds)
    _check_unresolved(store)
    _check_prior_budget(store, max_calls)


def _check_opt_in(opt_in: bool) -> None:
    if not opt_in:
        raise ValueError("dispatch requires explicit opt_in=True")


def _check_runtime_observation(proof: RuntimeCheck) -> None:
    if not proof.process_state_verified or not proof.process_observation_sha256:
        raise ValueError("fresh process/queue state must be verified before dispatch")
    if (datetime.now(UTC) - proof.checked_at).total_seconds() > 60:
        raise ValueError("runtime check is stale; recheck immediately before dispatch")


def _check_limits(records, max_calls, total_seconds, per_model_seconds, call_seconds) -> None:
    values = (max_calls, total_seconds, per_model_seconds, call_seconds)
    caps = (MAX_CALLS, MAX_TOTAL_SECONDS, MAX_MODEL_SECONDS, MAX_CALL_SECONDS)
    if any(value <= 0 or value > cap for value, cap in zip(values, caps, strict=True)):
        raise ValueError("dispatch bounds must be positive and within approved scorecard limits")


def _check_prior_budget(store, max_calls) -> None:
    if not store.summary()["pending"]:
        return
    summary = store.timing_summary()
    if summary["unknown_elapsed_attempts"] or summary["unknown_model_attempts"]:
        raise ValueError("prior attempt time is unknown; reconcile the run budget before dispatch")
    if summary["calls"] >= max_calls and store.summary()["pending"]:
        raise ValueError("run has no remaining call allowance")


def _check_unresolved(store: ReadingRunStore) -> None:
    if store.summary()["inflight"]:
        raise ValueError("an attempt is unresolved; reconcile before dispatch")


def _run_pending(
    store,
    records,
    units,
    base_url,
    opener,
    lock_factory,
    total_seconds,
    per_model_seconds,
    call_seconds,
    max_calls,
    stop_file,
):
    by_id = {_task_id(record): record for record in records}
    timing = store.timing_summary()
    deadline = time.monotonic() + max(0, total_seconds - timing["seconds"])
    lock_context = lock_factory() if lock_factory else nullcontext()
    with lock_context:
        return _dispatch_loop(
            store,
            by_id,
            units,
            base_url,
            opener,
            deadline,
            per_model_seconds,
            call_seconds,
            max_calls,
            stop_file,
        )


def _dispatch_loop(
    store,
    by_id,
    units,
    base_url,
    opener,
    deadline,
    per_model_seconds,
    call_seconds,
    max_calls,
    stop_file,
):
    results = []
    while _has_dispatch_time(store, deadline):
        stopped = _stop_requested(store, stop_file)
        if stopped is not None:
            results.append(stopped)
            break
        result = _dispatch_next(
            store,
            by_id,
            units,
            base_url,
            opener,
            deadline,
            per_model_seconds,
            call_seconds,
            max_calls,
        )
        if not _record_and_continue(results, result):
            break
    return results


def _stop_requested(store, stop_file: Path | None) -> dict | None:
    if stop_file is None or not stop_file.exists():
        return None
    pending = store.summary()["pending"]
    store.record_stop_report(str(stop_file), pending)
    return {
        "status": "stopped",
        "reason": "stop_file_present",
        "stop_file": str(stop_file),
        "pending_tasks": pending,
    }


def _has_dispatch_time(store, deadline) -> bool:
    return bool(store.summary()["pending"]) and time.monotonic() < deadline


def _record_and_continue(results, result) -> bool:
    if result is None:
        return False
    results.append(result)
    return not result.get("halt_batch") and result["status"] not in {
        "timeout",
        "failed",
        "inflight",
    }


def _dispatch_next(
    store,
    by_id,
    units,
    base_url,
    opener,
    deadline,
    per_model_seconds,
    call_seconds,
    max_calls,
):
    task = store.next_pending()
    if task is None:
        return None
    record = by_id.get(task["task_id"])
    if record is None:
        raise ValueError("journal task is absent from frozen request manifest")
    remaining = _remaining_budget(store, record, deadline, per_model_seconds, max_calls)
    if remaining <= 0:
        return None
    return _attempt(
        store,
        record,
        units[record["unit_id"]],
        base_url,
        min(call_seconds, remaining, MAX_CALL_SECONDS),
        opener,
    )


def _remaining_budget(store, record, deadline, per_model_seconds, max_calls) -> float:
    summary = store.timing_summary()
    if summary["calls"] >= max_calls:
        return 0
    model_used = summary["models"].get(record["model"], {"seconds": 0})["seconds"]
    return min(
        deadline - time.monotonic(),
        per_model_seconds - model_used,
        MAX_MODEL_SECONDS - model_used,
    )


def _guard_manifest(
    store: ReadingRunStore, records: list[dict], units: dict, readiness: dict, runtime: RuntimeCheck
) -> None:
    ids = [_task_id(record) for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("frozen dispatch manifest has duplicate task IDs")
    for record in records:
        _check_record(record, units, readiness, runtime)
    _check_store_tasks(store, records, ids)


def _check_store_tasks(store, records, ids) -> None:
    stored = {task["task_id"]: task for task in store.tasks}
    if set(stored) != set(ids):
        raise ValueError("run journal task set differs from frozen request manifest")
    if any(
        (
            stored[_task_id(record)].get("request_sha256"),
            stored[_task_id(record)].get("model_digest"),
        )
        != (record["request_sha256"], record["model_digest"])
        for record in records
    ):
        raise ValueError("run journal is not anchored to exact request/model identities")


def _check_record(record, units, readiness, runtime) -> None:
    task_id = _task_id(record)
    if record["unit_id"] not in units or task_id not in readiness:
        raise ValueError("request lacks its exact source unit or readiness evidence")
    _check_request_token_fit(record)
    if runtime.model_digests.get(record["model"]) != record["model_digest"]:
        raise ValueError("fresh runtime digest does not match request model")
    control = record.get("control_kind")
    _check_record_images(units[record["unit_id"]], record, control)
    proof = _guard_readiness(record, readiness[task_id])
    _require_complete_readiness(proof)
    materialize_record(record)


def _check_request_token_fit(record: dict) -> None:
    if record["token_fit"] != "verified" or record["launch_ready"] is not True:
        raise ValueError("exact request token fit is not verified")


def _check_record_images(unit: ReadingCandidate, record: dict, control: str | None) -> None:
    if control:
        _check_control_images(unit, record, control)
        return
    _check_image_coverage(unit, record)


def _check_control_images(unit: ReadingCandidate, record: dict, control: str) -> None:
    target_ids = {paragraph.source_id for paragraph in unit.target}
    spans = [span for image in record["images"] for span in image["sources"]]
    if _invalid_missing_image(control, record):
        raise ValueError("missing-image control must not contain image inputs")
    if _invalid_unrelated_image(control, record, spans, target_ids):
        raise ValueError("unrelated-image control must bind only a separate source image")


def _invalid_missing_image(control: str, record: dict) -> bool:
    return control == "missing_image" and bool(record["images"])


def _invalid_unrelated_image(control: str, record: dict, spans: list, target_ids: set) -> bool:
    return control == "unrelated_image" and (
        not record["images"] or any(span["source_id"] in target_ids for span in spans)
    )


def _check_image_coverage(unit: ReadingCandidate, record: dict) -> None:
    targets = {paragraph.source_id: paragraph for paragraph in unit.target}
    coverage = _coverage(record)
    spans = [span for image_spans in coverage.values() for span in image_spans]
    if not _covers_all_targets(spans, targets):
        raise ValueError("verified request images do not cover every target source")
    if not _spans_match_targets(spans, targets):
        raise ValueError("verified request image span does not match its target source")


def _covers_all_targets(spans, targets) -> bool:
    return {span.source_id for span in spans} == set(targets)


def _spans_match_targets(spans, targets) -> bool:
    return all(
        span.raw_sha256 == targets[span.source_id].raw_sha256
        and (span.start, span.end) == (0, len(targets[span.source_id].raw))
        for span in spans
    )


def _require_complete_readiness(proof: RequestReadiness) -> None:
    if not all(
        (proof.token_fit_verified, proof.source_expectations_frozen, proof.review_effort_resolved)
    ):
        raise ValueError("token fit, frozen source expectations and review effort must be verified")
