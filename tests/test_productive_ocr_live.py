"""Synthetic full pipeline over an actual owned fake HTTP server, never a model."""

import json
import runpy
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from congressional_globe.productive_ocr_fit import prepare_owned_job
from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
from congressional_globe.productive_ocr_live import (
    OwnedBounds,
    OwnedReadiness,
    ReadyJob,
    RuntimeObservation,
    execute_simulated_once,
)
from congressional_globe.productive_ocr_local import OwnedLocalClient, OwnedLocalPlan
from congressional_globe.productive_ocr_projection import compile_request_projection
from congressional_globe.productive_ocr_runner import RunnerContext, code_identity, fingerprint

BASE = Path(__file__).parent
PROJECTION = runpy.run_path(str(BASE / "test_productive_ocr_projection.py"))
LOCAL = runpy.run_path(str(BASE / "test_productive_ocr_local.py"))


def _pin(registry, value):
    raw = canonical_json(value)
    digest = sha256_bytes(raw)
    registry.files[digest] = raw
    return digest


def _plan(tmp_path, host, bounds):
    saved = tmp_path / "backend-plan.json"
    if saved.exists():
        return OwnedLocalPlan.model_validate_json(saved.read_bytes())
    plan, _ = LOCAL["_fixture"](tmp_path, request_timeout=8)
    source = Path(plan.executable)
    text = source.read_text().replace(
        '"content": "fixture"', '"content": ' + repr(PROJECTION["_valid_reply"](host))
    )
    source.write_text(text.replace('"prompt_eval_count": 3', '"prompt_eval_count": 6'))
    plan = OwnedLocalPlan.model_validate(
        {
            **plan.model_dump(),
            "executable_sha256": sha256_bytes(source.read_bytes()),
            "session_deadline_epoch": bounds.started_at_epoch + bounds.max_wall_seconds,
        }
    )
    saved.write_text(plan.model_dump_json())
    return plan


def _job(tmp_path, started=None):
    host, registry, prompt, _, _ = PROJECTION["_host_and_projection"]()
    bounds = OwnedBounds(
        started_at_epoch=started or time.time(),
        max_wall_seconds=120.0,
        max_request_seconds=16.0,
        timeout_seconds=8.0,
        max_calls=1,
        max_input_tokens=6,
        max_output_tokens=1500,
        per_call_output_tokens=1500,
    )
    plan = _plan(tmp_path, host, bounds)
    payload = host["payload"]
    payload["bounds_sha256"] = _pin(registry, bounds.model_dump(mode="json"))
    payload["code_sha256"] = _pin(registry, code_identity())
    payload["model_digest"] = plan.model_digest
    registry.files[plan.model_digest] = Path(plan.model_manifest).read_bytes()
    host["packet_sha256"] = sha256_bytes(canonical_json(payload))
    projection, _ = compile_request_projection(host, registry, prompt, plan.model_name)
    fit, _ = PROJECTION["_offline_fit_bundle"](projection, registry)
    prepared = prepare_owned_job(projection, host, registry, fit)
    registry.files[prepared.job.token_fit_sha256] = prepared.token_fit_record_json.encode()
    registry.files[prepared.full_fit_sha256] = prepared.full_fit_record_json.encode()
    approval = _pin(registry, {"scope": "Synthetic owned HTTP fixture only; not human approval"})
    client = OwnedLocalClient(plan, tmp_path / "spool")
    ready = OwnedReadiness(
        contract="productive-ocr-owned-readiness-v1",
        authorization_sha256=approval,
        execution_profile="synthetic_http_fixture",
        bounds_sha256=fingerprint(bounds.model_dump(mode="json")),
        code_sha256=fingerprint(code_identity()),
        backend_plan_sha256=fingerprint(plan.model_dump(mode="json")),
        jobs=(
            ReadyJob(
                window_id=prepared.job.window_id,
                job_sha256=fingerprint(prepared.job.model_dump(mode="json")),
                body_sha256=prepared.job.body_sha256,
                full_fit_sha256=prepared.full_fit_sha256,
            ),
        ),
    )
    readiness = _pin(registry, ready.model_dump(mode="json"))
    return prepared, registry, bounds, client, approval, readiness


def _runtime(registry, readiness, unit, checked=None):
    support = [
        _pin(registry, {"synthetic_evidence": name})
        for name in ["process", "queue", "log", "model"]
    ]
    proof = RuntimeObservation(
        contract="productive-ocr-live-runtime-observation-v1",
        readiness_sha256=readiness,
        window_id=unit,
        checked_at_epoch=checked or time.time(),
        process_evidence_sha256=support[0],
        queue_evidence_sha256=support[1],
        log_evidence_sha256=support[2],
        model_metadata_sha256=support[3],
        competing_requests=0,
    )
    return _pin(registry, proof.model_dump(mode="json"))


def _execute(tmp_path, context_checkpoint=lambda _: None, started=None, stale=False):
    prepared, registry, bounds, client, approval, ready = _job(tmp_path, started)
    checked = time.time() - 31 if stale else time.time()
    runtime = _runtime(registry, ready, prepared.job.window_id, checked)
    context = RunnerContext(registry, client, checkpoint=context_checkpoint)
    return execute_simulated_once(
        tmp_path / "run", (prepared,), bounds, context, ready, approval, runtime
    )


def test_owned_pipeline_returns_source_bound_export_and_reuses_without_http(tmp_path):
    started = time.time()
    first = _execute(tmp_path, started=started)
    assert first["statuses"]["valid"] == 1
    assert (
        first["results"][0]["result"]["host_export"]["acceptance_state"] == "unreviewed_ai_evidence"
    )
    assert _execute(tmp_path, started=started) == first
    assert len(list((tmp_path / "spool").glob("*/request.bin"))) == 1


def test_stale_operator_evidence_refuses_before_transport(tmp_path):
    with pytest.raises(ValueError, match="stale"):
        _execute(tmp_path, stale=True)
    assert not list((tmp_path / "spool").glob("*/request.bin"))


def test_readiness_cannot_bind_a_different_approval(tmp_path):
    prepared, registry, bounds, client, _, ready = _job(tmp_path)
    other = _pin(registry, {"different": "fixture approval"})
    runtime = _runtime(registry, ready, prepared.job.window_id)
    with pytest.raises(ValueError, match="approval"):
        execute_simulated_once(
            tmp_path / "run",
            (prepared,),
            bounds,
            RunnerContext(registry, client),
            ready,
            other,
            runtime,
        )
    assert not list((tmp_path / "spool").glob("*/request.bin"))


def test_complete_multimodal_fit_cannot_be_replaced_with_partial_text_count(tmp_path):
    prepared, registry, bounds, client, approval, _ = _job(tmp_path)
    partial = _pin(registry, {"text_tokens_only": 12})
    wrong = prepared.model_copy(update={"full_fit_sha256": partial})
    ready = OwnedReadiness(
        contract="productive-ocr-owned-readiness-v1",
        authorization_sha256=approval,
        execution_profile="synthetic_http_fixture",
        bounds_sha256=fingerprint(bounds.model_dump(mode="json")),
        code_sha256=fingerprint(code_identity()),
        backend_plan_sha256=fingerprint(client.plan.model_dump(mode="json")),
        jobs=(
            ReadyJob(
                window_id=wrong.job.window_id,
                job_sha256=fingerprint(wrong.job.model_dump(mode="json")),
                body_sha256=wrong.job.body_sha256,
                full_fit_sha256=partial,
            ),
        ),
    )
    digest = _pin(registry, ready.model_dump(mode="json"))
    runtime = _runtime(registry, digest, wrong.job.window_id)
    with pytest.raises(ValueError, match="incomplete multimodal"):
        execute_simulated_once(
            tmp_path / "run",
            (wrong,),
            bounds,
            RunnerContext(registry, client),
            digest,
            approval,
            runtime,
        )
    assert not list((tmp_path / "spool").glob("*/request.bin"))


WORKER = r"""
import os,runpy,signal,sys
from pathlib import Path
h=runpy.run_path(sys.argv[1]);base=Path(sys.argv[2]);mode=sys.argv[3]
def checkpoint(name):
    if name==mode:os.kill(os.getpid(),signal.SIGKILL)
try:
    result=h['_execute'](base,checkpoint,started=float((base/'started.txt').read_text()))
    (base/'result.json').write_text(__import__('json').dumps(result))
except Exception as e:
    (base/'error.txt').write_text(type(e).__name__+': '+str(e));sys.exit(2)
"""


def _process(tmp_path, checkpoint):
    return subprocess.run(
        [sys.executable, "-c", WORKER, __file__, str(tmp_path), checkpoint],
        capture_output=True,
        text=True,
        timeout=25,
    )


@pytest.mark.parametrize(
    "checkpoint",
    ["after_transport_spool", "after_raw_before_observation", "after_raw", "after_terminal"],
)
def test_fresh_process_imports_completed_raw_spool_without_duplicate_sends(tmp_path, checkpoint):
    (tmp_path / "started.txt").write_text(str(time.time()))
    killed = _process(tmp_path, checkpoint)
    assert killed.returncode == -signal.SIGKILL, killed.stderr
    resumed = _process(tmp_path, "resume")
    assert resumed.returncode == 0, (
        resumed.stderr + (tmp_path / "error.txt").read_text()
        if (tmp_path / "error.txt").exists()
        else resumed.stderr
    )
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["statuses"]["valid"] == 1
    assert len(list((tmp_path / "spool").glob("*/request.bin"))) == 1


def test_simulation_readiness_and_fake_approval_cannot_authorize_real_dispatch(tmp_path):
    from congressional_globe.productive_ocr_live import execute_owned_once

    prepared, registry, bounds, client, approval, ready = _job(tmp_path)
    runtime = _runtime(registry, ready, prepared.job.window_id)
    with pytest.raises(ValueError, match="recorded human approval"):
        execute_owned_once(
            tmp_path / "run",
            (prepared,),
            bounds,
            RunnerContext(registry, client),
            ready,
            approval,
            runtime,
        )
    assert not list((tmp_path / "spool").glob("*/request.bin"))


def test_recorded_approval_does_not_erase_t55_blockers_or_authorize_partial_chunk(tmp_path):
    from congressional_globe.productive_ocr_authority import APPROVAL_SHA256
    from congressional_globe.productive_ocr_live import execute_owned_once

    prepared, registry, bounds, client, _, ready = _job(tmp_path)
    raw = Path("artifacts/ocr-workflow-approval-20261028-01/approval.json").read_bytes()
    assert sha256_bytes(raw) == APPROVAL_SHA256
    registry.files[APPROVAL_SHA256] = raw
    changed = json.loads(registry.files[ready])
    changed.update(authorization_sha256=APPROVAL_SHA256, execution_profile="approved_first_chunk")
    ready = _pin(registry, changed)
    runtime = _runtime(registry, ready, prepared.job.window_id)
    with pytest.raises(ValueError, match="T55 has no recorded launch clearance"):
        execute_owned_once(
            tmp_path / "run",
            (prepared,),
            bounds,
            RunnerContext(registry, client),
            ready,
            APPROVAL_SHA256,
            runtime,
        )
    assert not list((tmp_path / "spool").glob("*/request.bin"))


def test_boolean_input_and_zero_output_usage_cannot_claim_success(tmp_path):
    from congressional_globe.productive_ocr_live import _usage_issue

    prepared, _, bounds, _, _, _ = _job(tmp_path)
    wrong = prepared.job.model_copy(update={"input_tokens": 1})
    assert _usage_issue({"input_tokens": True, "output_tokens": 2}, wrong, bounds, 0.5)
    assert _usage_issue({"input_tokens": 6, "output_tokens": 0}, prepared.job, bounds, 0.5)


def test_runtime_expiring_during_startup_blocks_post_and_stops_backend(tmp_path):
    prepared, registry, bounds, client, approval, ready = _job(tmp_path)
    runtime = _runtime(registry, ready, prepared.job.window_id)
    now = [time.time()]

    def checkpoint(name):
        if name == "after_claim":
            now[0] += 31

    context = RunnerContext(registry, client, clock=lambda: now[0], checkpoint=checkpoint)
    result = execute_simulated_once(
        tmp_path / "run", (prepared,), bounds, context, ready, approval, runtime
    )
    assert result["statuses"]["unresolved"] == 1
    assert not list((tmp_path / "spool").glob("*/response.http"))
    receipts = [json.loads(p.read_bytes()) for p in (tmp_path / "spool").glob("*/receipt.json")]
    assert len(receipts) == 1 and receipts[0]["stop_observation"] == "stopped"


def test_caller_registered_clearance_cannot_erase_blocked_t55(tmp_path):
    from congressional_globe.productive_ocr_authority import APPROVAL_SHA256
    from congressional_globe.productive_ocr_live import execute_owned_once

    prepared, registry, bounds, client, _, ready = _job(tmp_path)
    registry.files[APPROVAL_SHA256] = Path(
        "artifacts/ocr-workflow-approval-20261028-01/approval.json"
    ).read_bytes()
    invented = _pin(registry, {"claim": "all conditions resolved"})
    changed = json.loads(registry.files[ready])
    changed.update(
        authorization_sha256=APPROVAL_SHA256,
        execution_profile="approved_first_chunk",
        clearance_sha256=invented,
    )
    ready = _pin(registry, changed)
    runtime = _runtime(registry, ready, prepared.job.window_id)
    with pytest.raises(ValueError, match="no independently pinned ready clearance"):
        execute_owned_once(
            tmp_path / "run",
            (prepared,),
            bounds,
            RunnerContext(registry, client),
            ready,
            APPROVAL_SHA256,
            runtime,
        )
    assert not list((tmp_path / "spool").glob("*/request.bin"))


def test_incomplete_transport_cannot_export_valid_model_findings(tmp_path):
    from congressional_globe.productive_ocr_live import _export_response

    prepared, _, _, _, _, _ = _job(tmp_path)
    reply = PROJECTION["_valid_reply"](prepared.job.host)
    raw = json.dumps({"done": False, "message": {"content": reply}})
    response = {
        "status": "incomplete",
        "output_text": reply,
        "raw_response": raw,
        "owned_local": {"raw_http_sha256": sha256_bytes(raw.encode())},
    }
    exported = _export_response(response, prepared.job, json.loads(prepared.job.body_utf8), 0.5)
    assert exported.outcome == "invalid_provider_encoding_or_transport"
    assert exported.model_reply_text is None
    assert exported.raw_entity_sha256 == sha256_bytes(raw.encode())
