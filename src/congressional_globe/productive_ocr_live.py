"""Explicit one-request owned-local execution; no automatic batch or readiness override."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Literal, cast

from pydantic import Field

from congressional_globe.bracket_cues import Contract
from congressional_globe.productive_ocr_authority import verify_real_authority, verify_simulation
from congressional_globe.productive_ocr_control import (
    StopObservation,
    observe_returned,
    read_observation,
    write_observation,
)
from congressional_globe.productive_ocr_export import export_reply, export_transport_failure
from congressional_globe.productive_ocr_fit import PreparedOwnedJob, require_complete_fit
from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
from congressional_globe.productive_ocr_local import OwnedLocalClient, read_spool
from congressional_globe.productive_ocr_runner import (
    RunnerContext,
    SessionBounds,
    _capacity,
    _guard_saved,
    _owned_response,
    _session_lock,
    _validate_observed,
    _verify_job_bytes,
    _verify_job_evidence,
    code_identity,
    fingerprint,
)
from congressional_globe.role_run_store import RoleRunStore
from congressional_globe.scan_models import Sha256


class OwnedBounds(Contract):
    contract: Literal["productive-ocr-owned-session-v3"] = "productive-ocr-owned-session-v3"
    execution_mode: Literal["owned_local_http"] = "owned_local_http"
    started_at_epoch: float = Field(gt=0, allow_inf_nan=False)
    max_wall_seconds: float = Field(gt=0, le=1800, allow_inf_nan=False)
    max_request_seconds: float = Field(gt=0, le=840, allow_inf_nan=False)
    timeout_seconds: float = Field(gt=0, le=120, allow_inf_nan=False)
    max_calls: int = Field(ge=1, le=7)
    max_input_tokens: int = Field(ge=1, le=42000)
    max_output_tokens: int = Field(ge=1, le=10500)
    per_call_output_tokens: int = Field(ge=1, le=1500)


class ReadyJob(Contract):
    window_id: str = Field(min_length=1)
    job_sha256: Sha256
    body_sha256: Sha256
    full_fit_sha256: Sha256


class OwnedReadiness(Contract):
    contract: Literal["productive-ocr-owned-readiness-v1"]
    authorization_sha256: Sha256
    execution_profile: Literal["approved_first_chunk", "synthetic_http_fixture"] = (
        "approved_first_chunk"
    )
    clearance_sha256: Sha256 | None = None
    bounds_sha256: Sha256
    code_sha256: Sha256
    backend_plan_sha256: Sha256
    jobs: tuple[ReadyJob, ...] = Field(min_length=1, max_length=7)


class RuntimeObservation(Contract):
    """External operator evidence; required fresh for every individually dispatched job."""

    contract: Literal["productive-ocr-live-runtime-observation-v1"]
    readiness_sha256: Sha256
    window_id: str = Field(min_length=1)
    checked_at_epoch: float = Field(gt=0, allow_inf_nan=False)
    process_evidence_sha256: Sha256
    queue_evidence_sha256: Sha256
    log_evidence_sha256: Sha256
    model_metadata_sha256: Sha256
    competing_requests: Literal[0]


def _registered(registry, digest: str) -> bytes:
    data = registry.files.get(digest)
    if data is None or sha256_bytes(data) != digest:
        raise ValueError("missing or changed registered execution evidence")
    return data


def _verify_readiness(prepared, bounds, context, readiness_sha, authorization_sha, simulation):
    if not isinstance(context.client, OwnedLocalClient):
        raise ValueError("owned execution requires the explicit owned local client")
    readiness = OwnedReadiness.model_validate_json(_registered(context.registry, readiness_sha))
    _registered(context.registry, authorization_sha)
    expected = (
        authorization_sha,
        fingerprint(bounds.model_dump(mode="json")),
        fingerprint(code_identity()),
        fingerprint(context.client.plan.model_dump(mode="json")),
    )
    actual = (
        readiness.authorization_sha256,
        readiness.bounds_sha256,
        readiness.code_sha256,
        readiness.backend_plan_sha256,
    )
    if actual != expected:
        raise ValueError("live readiness does not bind approval/bounds/code/backend plan")
    identities = tuple(_ready_job(p) for p in prepared)
    if readiness.jobs != identities:
        raise ValueError("live readiness does not bind exact frozen jobs and full fit")
    _verify_owned_plan(bounds, context.client)
    _verify_execution_profile(readiness, prepared, context, authorization_sha, simulation)
    return readiness


def _verify_execution_profile(readiness, prepared, context, authorization_sha, simulation):
    if simulation:
        verify_simulation(readiness, context.client)
        return
    verify_real_authority(readiness, prepared, context.client, context.registry, authorization_sha)


def _ready_job(prepared: PreparedOwnedJob) -> ReadyJob:
    return ReadyJob(
        window_id=prepared.job.window_id,
        job_sha256=fingerprint(prepared.job.model_dump(mode="json")),
        body_sha256=prepared.job.body_sha256,
        full_fit_sha256=prepared.full_fit_sha256,
    )


def _verify_owned_plan(bounds: OwnedBounds, client: OwnedLocalClient) -> None:
    deadline = bounds.started_at_epoch + bounds.max_wall_seconds
    if client.plan.session_deadline_epoch != deadline:
        raise ValueError("owned backend must bind exact whole-session deadline")
    if client.plan.request_timeout_seconds > bounds.timeout_seconds:
        raise ValueError("owned backend request timeout exceeds session bounds")


def _verify_jobs(prepared, bounds, context) -> None:
    if not prepared or len(prepared) > bounds.max_calls:
        raise ValueError("owned frozen task count exceeds bounds")
    if len({p.job.window_id for p in prepared}) != len(prepared):
        raise ValueError("duplicate owned frozen unit IDs")
    for item in prepared:
        require_complete_fit(item, context.registry)
        # These private v2 helpers consume common budget fields, not mode/contract.
        _verify_job_bytes(item.job, cast(SessionBounds, bounds))
        _verify_job_evidence(item.job, bounds, context.registry)
        _verify_job_model(item.job, context.client)


def _verify_job_model(job, client) -> None:
    body = json.loads(job.body_utf8)
    expected = (client.plan.model_name, client.plan.model_digest)
    if (body["model"], job.host["payload"]["model_digest"]) != expected:
        raise ValueError("owned backend model does not bind frozen request")


def _verify_runtime(context, readiness_sha, window_id, runtime_sha):
    proof = RuntimeObservation.model_validate_json(_registered(context.registry, runtime_sha))
    if (proof.readiness_sha256, proof.window_id) != (readiness_sha, window_id):
        raise ValueError("runtime observation belongs to another request/readiness")
    age = context.clock() - proof.checked_at_epoch
    if not 0 <= age <= 30:
        raise ValueError("runtime observation is stale or from a future clock")
    for digest in (
        proof.process_evidence_sha256,
        proof.queue_evidence_sha256,
        proof.log_evidence_sha256,
        proof.model_metadata_sha256,
    ):
        _registered(context.registry, digest)
    return proof


def execute_owned_once(
    output: Path,
    prepared: tuple[PreparedOwnedJob, ...],
    bounds: OwnedBounds,
    context: RunnerContext,
    readiness_sha256: str,
    authorization_sha256: str,
    runtime_observation_sha256: str,
) -> dict:
    """Dispatch at most one pending request after explicit complete/fresh evidence.

    Callers must perform actual operator process/queue/log/model checks and
    register their original evidence. This function verifies bindings/freshness;
    it cannot turn fabricated operator observations into real runtime evidence.
    """
    return _execute_checked(
        output,
        prepared,
        bounds,
        context,
        readiness_sha256,
        authorization_sha256,
        runtime_observation_sha256,
        False,
    )


def execute_simulated_once(
    output,
    prepared,
    bounds,
    context,
    readiness_sha256,
    authorization_sha256,
    runtime_observation_sha256,
):
    """Exercise real HTTP/process machinery with a verified non-model toy store only."""
    return _execute_checked(
        output,
        prepared,
        bounds,
        context,
        readiness_sha256,
        authorization_sha256,
        runtime_observation_sha256,
        True,
    )


def _execute_checked(
    output,
    prepared,
    bounds,
    context,
    readiness_sha256,
    authorization_sha256,
    runtime_observation_sha256,
    simulation,
):
    prepared = tuple(PreparedOwnedJob.model_validate_json(p.model_dump_json()) for p in prepared)
    bounds = OwnedBounds.model_validate(bounds)
    _verify_readiness(prepared, bounds, context, readiness_sha256, authorization_sha256, simulation)
    _verify_jobs(prepared, bounds, context)
    config, packets = _configuration(prepared, bounds, context, readiness_sha256)
    with _session_lock():
        store = RoleRunStore(output / "jobs.sqlite", config, packets)
        try:
            return _execute_once(
                store, prepared, bounds, context, readiness_sha256, runtime_observation_sha256
            )
        finally:
            store.close()


def _configuration(prepared, bounds, context, readiness_sha):
    packets = [p.job.model_dump(mode="json") for p in prepared]
    config = {
        "contract": bounds.contract,
        "bounds": bounds.model_dump(mode="json"),
        "readiness_sha256": readiness_sha,
        "code_hashes": code_identity(),
        "backend_plan": context.client.plan.model_dump(mode="json"),
        "max_output_tokens": bounds.per_call_output_tokens,
        "request_hashes": {p["window_id"]: fingerprint(p) for p in packets},
    }
    return config, packets


def _execute_once(store, prepared, bounds, context, readiness_sha, runtime_sha):
    jobs = {p.job.window_id: p.job for p in prepared}
    _recover_owned(store, jobs, bounds, context)
    _guard_saved(store)
    packet = store.next_pending()
    if packet is not None:
        job = jobs[packet["window_id"]]
        _verify_runtime(context, readiness_sha, job.window_id, runtime_sha)
        if _capacity(store, job, bounds, context.clock()):
            guarded = OwnedLocalClient(
                context.client.plan,
                context.client.spool_dir,
                before_send=lambda: _verify_runtime(
                    context, readiness_sha, job.window_id, runtime_sha
                ),
            )
            _attempt_owned(store, job, bounds, replace(context, client=guarded), runtime_sha)
    return {
        **store.summary(),
        "usage": store.budget_summary(),
        "results": store.results(),
        "historical_status": "unreviewed_proposals_not_verified_print",
        "dispatch_policy": "at_most_one_request; fresh_operator_evidence_required_for_next",
    }


def _recover_owned(store, jobs, bounds, context):
    _import_transport_spools(store, jobs, bounds, context)
    for saved in store.saved_responses():
        job = jobs[saved["window_id"]]
        observed = read_observation(store.path.parent, saved["attempt_id"], job, saved["response"])
        status, validation = _validate_live(
            saved["response"], job, observed, bounds, saved["elapsed_seconds"]
        )
        runtime_sha = _read_runtime(
            store.path.parent, saved["attempt_id"], job.window_id, store.config["readiness_sha256"]
        )
        store.finish(
            saved["attempt_id"],
            {
                **saved["response"],
                **validation,
                "elapsed_seconds": saved["elapsed_seconds"],
                "runtime_observation_sha256": runtime_sha,
            },
            status,
        )
        context.checkpoint("after_terminal")


def _import_transport_spools(store, jobs, bounds, context):
    saved = {r["window_id"]: r for r in store.saved_responses()}
    for job in jobs.values():
        _import_one_spool(store, job, bounds, context, saved)


def _import_one_spool(store, job, bounds, context, saved):
    try:
        attempt = store.inflight_id(job.window_id)
    except ValueError:
        return
    observation_path = store.path.parent / f"owned-stop-{attempt}.json"
    if observation_path.exists():
        return
    if not context.client.spool_dir.exists():
        return
    recovered = read_spool(
        context.client.spool_dir,
        job.body_sha256,
        context.client.plan.model_name,
        context.client.plan.model_digest,
    )
    if recovered is None:
        return
    prior = saved.get(job.window_id)
    _import_recovered(store, attempt, job, recovered, bounds, prior)


def _import_recovered(store, attempt, job, recovered, bounds, prior):
    from congressional_globe.productive_ocr_local import LocalTransportReceipt

    receipt = LocalTransportReceipt.model_validate_json(
        (Path(recovered.spool_directory) / "receipt.json").read_bytes()
    )
    elapsed = recovered.elapsed_seconds
    if prior is not None:
        if prior["response"] != recovered.response:
            raise ValueError("transport spool differs from immutable saved raw reply")
        elapsed = prior["elapsed_seconds"]
    store.record_response(attempt, recovered.response, elapsed)
    observed = StopObservation(
        attempt_id=attempt,
        window_id=job.window_id,
        body_sha256=job.body_sha256,
        response_sha256=fingerprint(recovered.response),
        state=recovered.stop_observation,
        cancellation_requested=False,
        within_deadline=receipt.ended_at_epoch <= bounds.started_at_epoch + bounds.max_wall_seconds,
    )
    write_observation(store.path.parent, observed)


def _attempt_owned(store, job, bounds, context, runtime_sha):
    context.checkpoint("before_claim")
    attempt = store.start(job.window_id, job.model_dump(mode="json"))
    context.checkpoint("after_claim")
    _write_runtime(store.path.parent, attempt, runtime_sha, context.registry)
    started = context.monotonic()
    try:
        response, owned = _owned_response(job, bounds, context)
    except Exception as error:
        _finish_failure(store, attempt, error, context.monotonic() - started, runtime_sha)
        return
    context.checkpoint("after_transport_spool")
    elapsed = context.monotonic() - started
    store.record_response(attempt, response, elapsed)
    context.checkpoint("after_raw_before_observation")
    deadline = bounds.started_at_epoch + bounds.max_wall_seconds
    observed = observe_returned(attempt, job, response, owned, deadline, context.clock)
    write_observation(store.path.parent, observed)
    context.checkpoint("after_raw")
    status, validation = _validate_live(response, job, observed, bounds, elapsed)
    result = {
        **response,
        **validation,
        "elapsed_seconds": elapsed,
        "runtime_observation_sha256": runtime_sha,
    }
    store.finish(attempt, result, status)
    context.checkpoint("after_terminal")


def _finish_failure(store, attempt, error, elapsed, runtime_sha):
    store.finish(
        attempt,
        {
            "error_type": type(error).__name__,
            "runtime_observation_sha256": runtime_sha,
            "usage": None,
            "owned_stop_observation": getattr(error, "owned_stop_observation", "unknown"),
            "elapsed_seconds": elapsed,
            "outcome": "unknown owned request; no automatic retry",
        },
        "unresolved",
    )


def _validate_live(response, job, observed, bounds, elapsed):
    status, validation = _validate_observed(response, job, observed)
    issue = _usage_issue(response.get("usage"), job, bounds, elapsed)
    if issue:
        status = "unresolved" if status == "unresolved" else "invalid"
        validation = {**validation, "fit_or_budget_error": issue}
    body = json.loads(job.body_utf8)
    export = _export_response(response, job, body, elapsed)
    return status, {**validation, "host_export": export.model_dump(mode="json")}


def _export_response(response, job, body, elapsed):
    payload = job.host["payload"]
    if response.get("status") != "completed":
        return _export_transport(response, job, elapsed)
    return export_reply(
        job.host,
        job.body_utf8,
        response.get("output_text", ""),
        payload["model_digest"],
        sha256_bytes(canonical_json(body["format"])),
        response.get("usage"),
        elapsed,
    )


def _export_transport(response, job, elapsed):
    if response.get("raw_response_base64") is not None:
        entity = base64.b64decode(response["raw_response_base64"], validate=True)
    else:
        entity = response["raw_response"].encode("utf-8")
    metadata = response["owned_local"]
    return export_transport_failure(
        job.host,
        job.body_utf8,
        entity,
        metadata["raw_http_sha256"],
        job.host["payload"]["model_digest"],
        response.get("finish_reason") or "provider transport error",
        response.get("usage"),
        elapsed,
    )


def _runtime_support(registry, proof):
    keys = (
        proof.process_evidence_sha256,
        proof.queue_evidence_sha256,
        proof.log_evidence_sha256,
        proof.model_metadata_sha256,
    )
    support = {key: _registered(registry, key) for key in keys}
    if any(len(data) > 4 * 1024 * 1024 for data in support.values()):
        raise ValueError("runtime observation support exceeds bounded metadata size")
    return {key: base64.b64encode(data).decode("ascii") for key, data in support.items()}


def _write_runtime(directory, attempt, digest, registry):
    raw = _registered(registry, digest)
    proof = RuntimeObservation.model_validate_json(raw)
    record = {
        "evidence_sha256": digest,
        "evidence_base64": base64.b64encode(raw).decode("ascii"),
        "support_base64": _runtime_support(registry, proof),
    }
    with (directory / f"runtime-{attempt}.json").open("x") as stream:
        json.dump({"sha256": fingerprint(record), "record": record}, stream)
        stream.flush()
        os.fsync(stream.fileno())


def _read_runtime(directory, attempt, window_id, readiness_sha):
    wrapped = json.loads((directory / f"runtime-{attempt}.json").read_text())
    record = wrapped["record"]
    if fingerprint(record) != wrapped["sha256"]:
        raise ValueError("runtime observation checkpoint hash mismatch")
    raw = base64.b64decode(record["evidence_base64"], validate=True)
    if sha256_bytes(raw) != record["evidence_sha256"]:
        raise ValueError("runtime observation original bytes changed")
    proof = RuntimeObservation.model_validate_json(raw)
    if (proof.window_id, proof.readiness_sha256) != (window_id, readiness_sha):
        raise ValueError("runtime checkpoint belongs to a different unit or readiness")
    _verify_runtime_support(record["support_base64"], proof)
    return record["evidence_sha256"]


def _verify_runtime_support(support, proof):
    expected = {
        proof.process_evidence_sha256,
        proof.queue_evidence_sha256,
        proof.log_evidence_sha256,
        proof.model_metadata_sha256,
    }
    if set(support) != expected:
        raise ValueError("runtime supporting evidence coverage differs")
    for digest, encoded in support.items():
        if sha256_bytes(base64.b64decode(encoded, validate=True)) != digest:
            raise ValueError("runtime supporting evidence bytes changed")


def _usage_issue(usage, job, bounds, elapsed) -> str | None:
    if elapsed > bounds.timeout_seconds:
        return "observed request exceeded frozen per-request time"
    if not isinstance(usage, dict):
        return "provider usage is unknown"
    if type(usage.get("input_tokens")) is not int or usage["input_tokens"] != job.input_tokens:
        return "actual input tokens differ from exact verified fit"
    return _output_usage_issue(usage.get("output_tokens"), bounds)


def _output_usage_issue(output, bounds):
    if type(output) is not int or not 1 <= output <= bounds.per_call_output_tokens:
        return "actual output tokens missing or exceed frozen cap"
    return None
