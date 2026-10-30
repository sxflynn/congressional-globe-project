"""Offline-injectable productive OCR execution over the existing immutable journal.

No provider adapter or CLI is supplied here. A future real adapter must prove its
owned-call deadline/cancellation/observation behavior before live readiness.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import tempfile
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field

from congressional_globe.bracket_cues import Contract
from congressional_globe.productive_ocr_control import (
    cancel_observe,
    observe_returned,
    read_observation,
    safe_stop,
    write_observation,
)
from congressional_globe.productive_ocr_host import EvidenceRegistry
from congressional_globe.role_run_store import RoleRunStore
from congressional_globe.scan_models import Sha256


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class SessionBounds(Contract):
    contract: Literal["productive-ocr-session-v2"] = "productive-ocr-session-v2"
    execution_mode: Literal["offline_fake_only"] = "offline_fake_only"
    started_at_epoch: float = Field(gt=0, allow_inf_nan=False)
    max_wall_seconds: float = Field(gt=0, le=1800, allow_inf_nan=False)
    max_request_seconds: float = Field(gt=0, le=840, allow_inf_nan=False)
    timeout_seconds: float = Field(gt=0, le=120, allow_inf_nan=False)
    max_calls: int = Field(ge=1, le=7)
    max_input_tokens: int = Field(ge=1, le=42000)
    max_output_tokens: int = Field(ge=1, le=10500)
    per_call_output_tokens: int = Field(ge=1, le=1500)


class FrozenJob(Contract):
    window_id: str = Field(min_length=1)
    host: dict
    body_utf8: str = Field(min_length=1, max_length=24 * 1024 * 1024)
    body_sha256: Sha256
    input_tokens: int = Field(ge=1, le=6000)
    token_fit_sha256: Sha256


class TokenFit(Contract):
    model_name: str = Field(min_length=1)
    body_sha256: Sha256
    model_digest: Sha256
    input_tokens: int = Field(ge=1, le=6000)
    output_tokens: int = Field(ge=1, le=1500)
    evidence_scope: Literal["synthetic_test", "actual_tokenizer"]


class OwnedFailure(RuntimeError):
    def __init__(self, observation: str):
        super().__init__("owned request failed; outcome/usage unknown")
        self.owned_stop_observation = observation


class OwnedCall(Protocol):
    def result(self, timeout: float) -> dict: ...
    def cancel(self) -> None: ...
    def observe(self) -> Literal["stopped", "running", "unknown"]: ...


class OwnedClient(Protocol):
    offline_test_double: bool

    def start(self, body: bytes) -> OwnedCall: ...


@dataclass(frozen=True)
class RunnerContext:
    """Explicit dependencies, kept outside immutable serialized journal identity."""

    registry: EvidenceRegistry
    client: OwnedClient
    clock: Callable[[], float] = time.time
    monotonic: Callable[[], float] = time.monotonic
    checkpoint: Callable[[str], None] = lambda _: None


def code_identity() -> dict[str, str]:
    paths = list(Path(__file__).parent.glob("productive_ocr_*.py"))
    paths += [
        Path(__file__).with_name(name)
        for name in ("role_run_store.py", "deterministic_models.py", "bracket_cues.py")
    ]
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}


def freeze_job(
    host: dict,
    registry,
    prompt: str,
    schema_text: str,
    model: str,
    input_tokens: int,
    token_fit_sha256: str,
    output_tokens: int = 1500,
) -> FrozenJob:
    """Freeze actual caller bytes after host validation; token fit is external evidence."""
    from congressional_globe.productive_ocr_host import project_provider, validate_host

    schema_text = canonical(json.loads(schema_text))
    checked = validate_host(host, registry)
    payload = checked["payload"]
    _verify_prompt_schema(payload, prompt, schema_text)
    image = payload["image"]
    image_bytes = registry.image_bytes[image["sha256"]]
    body = {
        "model": model,
        "stream": False,
        "think": False,
        "messages": [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": canonical(project_provider(checked)),
                "images": [base64.b64encode(image_bytes).decode("ascii")],
            },
        ],
        "format": json.loads(schema_text),
        "options": {"num_predict": output_tokens},
    }
    encoded = canonical(body)
    return FrozenJob(
        window_id=payload["unit_id"],
        host=checked,
        body_utf8=encoded,
        body_sha256=hashlib.sha256(encoded.encode()).hexdigest(),
        input_tokens=input_tokens,
        token_fit_sha256=token_fit_sha256,
    )


def _verify_prompt_schema(payload: dict, prompt: str, schema_text: str) -> None:
    actual = (
        hashlib.sha256(prompt.encode()).hexdigest(),
        hashlib.sha256(schema_text.encode()).hexdigest(),
    )
    if actual != (payload["prompt_sha256"], payload["response_schema_sha256"]):
        raise ValueError("actual prompt/schema bytes disagree with host identity")


def execute(
    output: Path, jobs: tuple[FrozenJob, ...], bounds: SessionBounds, context: RunnerContext
) -> dict:
    """Run/recover only explicit injected clients under the shared Ollama lock."""
    jobs = tuple(FrozenJob.model_validate_json(job.model_dump_json()) for job in jobs)
    if getattr(context.client, "offline_test_double", None) is not True:
        raise ValueError("this runner version accepts declared offline test doubles only")
    packets = [job.model_dump(mode="json") for job in jobs]
    bounds = SessionBounds.model_validate(bounds)
    _verify_jobs(jobs, bounds, context)
    config = {
        "contract": bounds.contract,
        "bounds": bounds.model_dump(mode="json"),
        "code_hashes": code_identity(),
        "max_output_tokens": bounds.per_call_output_tokens,
        "request_hashes": {p["window_id"]: fingerprint(p) for p in packets},
    }
    with _session_lock():
        store = RoleRunStore(output / "jobs.sqlite", config, packets)
        try:
            return _execute_store(store, jobs, bounds, context)
        finally:
            store.close()


@contextmanager
def _session_lock():
    path = Path(tempfile.gettempdir()) / "congressional-globe-ollama-request.lock"
    with path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _verify_jobs(
    jobs: tuple[FrozenJob, ...], bounds: SessionBounds, context: RunnerContext
) -> None:
    from congressional_globe.productive_ocr_host import validate_host

    if not jobs or len(jobs) > bounds.max_calls:
        raise ValueError("explicit frozen task count exceeds bounds")
    if len({job.window_id for job in jobs}) != len(jobs):
        raise ValueError("duplicate frozen window IDs")
    for job in jobs:
        validate_host(job.host, context.registry)
        _verify_job_bytes(job, bounds)
        _verify_job_evidence(job, bounds, context.registry)


def _verify_job_evidence(job, bounds, registry) -> None:
    payload = job.host["payload"]
    expected = (fingerprint(code_identity()), fingerprint(bounds.model_dump(mode="json")))
    if (payload["code_sha256"], payload["bounds_sha256"]) != expected:
        raise ValueError("actual implementation/session bounds differ from host identity")
    data = registry.files.get(job.token_fit_sha256)
    if data is None or hashlib.sha256(data).hexdigest() != job.token_fit_sha256:
        raise ValueError("missing or changed exact token-fit evidence")
    fit = TokenFit.model_validate_json(data)
    if fit.model_name != json.loads(job.body_utf8)["model"]:
        raise ValueError("token-fit model name differs from exact provider request")
    if (fit.body_sha256, fit.model_digest, fit.input_tokens, fit.output_tokens) != (
        job.body_sha256,
        payload["model_digest"],
        job.input_tokens,
        bounds.per_call_output_tokens,
    ):
        raise ValueError("token-fit evidence does not bind exact request/model/limits")


def _verify_job_bytes(job: FrozenJob, bounds: SessionBounds) -> None:
    if hashlib.sha256(job.body_utf8.encode()).hexdigest() != job.body_sha256:
        raise ValueError("frozen provider bytes mismatch")
    body = json.loads(job.body_utf8)
    if body["options"]["num_predict"] != bounds.per_call_output_tokens:
        raise ValueError("frozen output ceiling differs from session")
    if job.window_id != job.host["payload"]["unit_id"]:
        raise ValueError("frozen unit identity mismatch")
    _verify_wire_projection(job, body)


def _verify_wire_projection(job: FrozenJob, body: dict) -> None:
    from congressional_globe.productive_ocr_host import project_provider

    messages = body["messages"]
    _verify_prompt_schema(job.host["payload"], messages[0]["content"], canonical(body["format"]))
    expected = {
        "model": body["model"],
        "stream": False,
        "think": False,
        "messages": [
            {"role": "system", "content": messages[0]["content"]},
            {
                "role": "user",
                "content": canonical(project_provider(job.host)),
                "images": messages[1]["images"],
            },
        ],
        "format": body["format"],
        "options": body["options"],
    }
    if body != expected or set(body["options"]) != {"num_predict"}:
        raise ValueError("foreign fields in frozen provider request")
    if len(messages[1]["images"]) != 1:
        raise ValueError("expected exactly one frozen image")
    if messages[1]["content"] != canonical(project_provider(job.host)):
        raise ValueError("frozen provider projection mismatch")
    image = base64.b64decode(messages[1]["images"][0], validate=True)
    if hashlib.sha256(image).hexdigest() != job.host["payload"]["image"]["sha256"]:
        raise ValueError("frozen provider image mismatch")


def _execute_store(store: RoleRunStore, jobs, bounds, context) -> dict:
    by_id = {job.window_id: job for job in jobs}
    _recover(store, by_id, context)
    _guard_saved(store)
    packet = store.next_pending()
    while packet is not None:
        job = by_id[packet["window_id"]]
        if not _capacity(store, job, bounds, context.clock()):
            break
        status = _attempt(store, job, bounds, context)
        packet = _next_packet(store, status)
    return {
        **store.summary(),
        "usage": store.budget_summary(),
        "results": store.results(),
        "historical_status": "unreviewed_proposals_not_verified_print",
        "backend_stop_scope": "injected_owned_client_only; actual_backend_unproved",
    }


def _next_packet(store: RoleRunStore, status: str) -> dict | None:
    if status != "valid":
        return None
    _guard_saved(store)
    return store.next_pending()


def _capacity(store, job, bounds, now: float) -> bool:
    usage = store.budget_summary()
    if usage["unknown_elapsed"] or usage["unknown_usage"]:
        return False
    if now < bounds.started_at_epoch:
        raise ValueError("session clock precedes frozen start; observation unknown")
    elapsed = now - bounds.started_at_epoch
    return all(
        (
            usage["calls"] < bounds.max_calls,
            elapsed + bounds.timeout_seconds <= bounds.max_wall_seconds,
            usage["seconds"] + bounds.timeout_seconds <= bounds.max_request_seconds,
            usage["input_tokens"] + job.input_tokens <= bounds.max_input_tokens,
            usage["output_tokens"] + bounds.per_call_output_tokens <= bounds.max_output_tokens,
            not usage["output_limit_exceeded"],
        )
    )


def _guard_saved(store: RoleRunStore) -> None:
    counts = store.summary()["statuses"]
    if counts["inflight"] or counts["unresolved"]:
        raise ValueError("ambiguous owned request; reconcile actual worker/server before dispatch")
    for row in store.results():
        _guard_terminal(row)


def _guard_terminal(row: dict) -> None:
    if row["status"] != "valid":
        raise ValueError("prior invalid/error result blocks subsequent dispatch")
    if row["result"].get("proposal_status") not in {"findings", "no_finding"}:
        raise ValueError("incomplete/unresolved inspection blocks subsequent dispatch")


def _recover(store: RoleRunStore, jobs: dict, context: RunnerContext) -> None:
    for saved in store.saved_responses():
        job = jobs[saved["window_id"]]
        observation = read_observation(
            store.path.parent, saved["attempt_id"], job, saved["response"]
        )
        status, validation = _validate_observed(saved["response"], job, observation)
        result = {**saved["response"], **validation, "elapsed_seconds": saved["elapsed_seconds"]}
        store.finish(saved["attempt_id"], result, status)
        context.checkpoint("after_terminal")


def _attempt(store, job, bounds, context) -> str:
    context.checkpoint("before_claim")
    attempt = store.start(job.window_id, job.model_dump(mode="json"))
    context.checkpoint("after_claim")
    started = context.monotonic()
    try:
        response, owned = _owned_response(job, bounds, context)
    except Exception as error:
        result = {
            "error_type": type(error).__name__,
            "owned_stop_observation": getattr(error, "owned_stop_observation", "unknown"),
            "usage": None,
            "elapsed_seconds": context.monotonic() - started,
            "outcome": "owned request failed; outcome/usage unknown; no retry",
        }
        store.finish(attempt, result, "unresolved")
        return "unresolved"
    elapsed = context.monotonic() - started
    store.record_response(attempt, response, elapsed)
    context.checkpoint("after_raw_before_observation")
    deadline = bounds.started_at_epoch + bounds.max_wall_seconds
    observation = observe_returned(attempt, job, response, owned, deadline, context.clock)
    write_observation(store.path.parent, observation)
    context.checkpoint("after_raw")
    status, validation = _validate_observed(response, job, observation)
    store.finish(attempt, {**response, **validation, "elapsed_seconds": elapsed}, status)
    context.checkpoint("after_terminal")
    return status


def _owned_response(job, bounds, context) -> tuple[dict, OwnedCall]:
    _remaining_timeout(bounds, context)
    owned = context.client.start(job.body_utf8.encode())
    context.checkpoint("after_send")
    try:
        timeout = _remaining_timeout(bounds, context)
        response = owned.result(timeout=max(0.0, timeout))
    except Exception as error:
        observed = cancel_observe(owned)
        failure = OwnedFailure(observed)
        raise failure from error
    return response, owned


def _remaining_timeout(bounds, context) -> float:
    now = context.clock()
    remaining = bounds.started_at_epoch + bounds.max_wall_seconds - now
    if now < bounds.started_at_epoch or remaining <= 0:
        raise TimeoutError("no positive verified session window before dispatch")
    return min(bounds.timeout_seconds, remaining)


def _validate_observed(response, job, observation) -> tuple[str, dict]:
    if not safe_stop(observation):
        return "unresolved", {
            "owned_stop_observation": observation.model_dump(mode="json"),
            "outcome": "saved raw reply; owned stop/deadline unproved",
        }
    status, validation = _validate(response, job)
    return status, {**validation, "owned_stop_observation": observation.model_dump(mode="json")}


def _validate(response: dict, job: FrozenJob) -> tuple[str, dict]:
    from congressional_globe.productive_ocr_reply import validate_reply

    try:
        _provider_complete(response)
        if job.host["payload"]["contract"] == "ocr-productive-repair-host-input-v3":
            from congressional_globe.productive_ocr_text_reply import export_text_reply

            exported = export_text_reply(job.host, job.body_utf8, response["output_text"])
            mapped = exported.model_dump(mode="json")
            status = exported.outcome["proposal_status"]
        else:
            mapped = validate_reply(response["output_text"], job.host)
            status = json.loads(response["output_text"])["status"]
        return "valid", {
            "source_mapped_proposals": mapped,
            "proposal_status": status,
            "quality": "host_replay_only; print_accuracy_unreviewed",
        }
    except (ValueError, KeyError, TypeError) as error:
        return "invalid", {"validation_error": str(error)[:1000]}


def _provider_complete(response: dict) -> None:
    if response.get("status") != "completed" or response.get("finish_reason") == "length":
        raise ValueError("provider reply incomplete/refused")
    if not isinstance(response.get("raw_response"), str):
        raise ValueError("raw provider response missing")
