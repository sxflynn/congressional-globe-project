"""One-slot measurement authorization and recovery use synthetic transports only."""

from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from congressional_globe import productive_ocr_measurement as measurement
from congressional_globe.productive_ocr_live import RuntimeObservation
from congressional_globe.productive_ocr_local import OwnedLocalPlan
from congressional_globe.productive_ocr_runner import fingerprint


def _spec(now: float | None = None) -> measurement.MeasurementSpec:
    started = now or time.time()
    plan = OwnedLocalPlan(
        executable="/tmp/fake-ollama",
        executable_sha256="a" * 64,
        argv=("/tmp/fake-ollama", "serve"),
        port=54321,
        model_store="/tmp/fake-models",
        model_manifest="/tmp/fake-models/fake/latest",
        model_name="fake:latest",
        model_digest="b" * 64,
        session_deadline_epoch=started + 600,
    )
    return measurement.MeasurementSpec(
        contract="productive-ocr-s5-measurement-v1",
        approval_sha256=measurement.APPROVAL_SHA,
        body_sha256=measurement.BODY_SHA,
        code_sha256="c" * 64,
        started_at_epoch=started,
        plan=plan,
    )


def test_mutated_or_missing_approval_is_denied(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(measurement, "REPOSITORY", tmp_path)
    approval = tmp_path / measurement.PACKAGE / "approval.json"
    approval.parent.mkdir(parents=True)
    approval.write_bytes(b"changed approval")
    with pytest.raises(ValueError, match="approval is absent or changed"):
        measurement._verify_spec(tmp_path, _spec())


def test_spec_mutation_and_stale_preparation_are_denied(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(measurement, "REPOSITORY", tmp_path)
    approval = tmp_path / measurement.PACKAGE / "approval.json"
    approval.parent.mkdir(parents=True)
    approval.write_bytes(b"approved")
    monkeypatch.setattr(measurement, "APPROVAL_SHA", measurement.sha256_bytes(b"approved"))
    with pytest.raises(ValueError, match="scope differs"):
        measurement._verify_spec(tmp_path, _spec().model_copy(update={"body_sha256": "d" * 64}))
    with pytest.raises(TimeoutError, match="preparation exceeded"):
        measurement._verify_session_time(_spec(time.time() - 301))
    spec = _spec()
    directory = tmp_path / "runtime"
    directory.mkdir()
    proof = RuntimeObservation(
        contract="productive-ocr-live-runtime-observation-v1",
        readiness_sha256=fingerprint(spec.model_dump(mode="json")),
        window_id="S5",
        checked_at_epoch=time.time() - 31,
        process_evidence_sha256="a" * 64,
        queue_evidence_sha256="b" * 64,
        log_evidence_sha256="c" * 64,
        model_metadata_sha256="d" * 64,
        competing_requests=0,
    )
    (directory / "runtime.json").write_text(proof.model_dump_json())
    with pytest.raises(ValueError, match="runtime observation is stale"):
        measurement._verify_runtime(directory, spec)


def _enable_synthetic_execute(
    tmp_path: Path, monkeypatch, client_type
) -> measurement.MeasurementSpec:
    monkeypatch.setattr(measurement, "REPOSITORY", tmp_path)
    monkeypatch.setattr(measurement, "PACKAGE", Path("synthetic-measurement"))
    monkeypatch.setattr(measurement, "_verify_spec", lambda *_: None)
    monkeypatch.setattr(measurement, "_verify_runtime", lambda *_: None)
    monkeypatch.setattr(measurement, "_verify_session_time", lambda *_: None)
    monkeypatch.setattr(measurement, "_session_lock", nullcontext)
    monkeypatch.setattr(measurement, "OwnedLocalClient", client_type)
    host = {"payload": {"model_digest": "b" * 64, "response_schema_sha256": "e" * 64}}
    projection = SimpleNamespace(
        body_sha256=measurement.BODY_SHA, body_utf8='{"model":"fake:latest"}'
    )
    monkeypatch.setattr(measurement, "load_s5_inputs", lambda _: (host, projection, object()))
    monkeypatch.setattr(measurement, "_export", lambda *_: {"outcome": "valid"})
    return _spec()


class _FakeCall:
    def result(self, timeout: float) -> dict:
        assert timeout == 120
        return {"status": "completed", "finish_reason": "stop", "output_text": "ok", "usage": None}

    @staticmethod
    def observe() -> str:
        return "stopped"


class _FakeClient:
    calls = 0
    fail = False

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def start(self, _body: bytes) -> _FakeCall:
        type(self).calls += 1
        if type(self).fail:
            raise RuntimeError("synthetic dispatch failure")
        return _FakeCall()


def test_failure_spends_the_only_slot_and_second_dispatch_is_refused(tmp_path, monkeypatch) -> None:
    _FakeClient.calls, _FakeClient.fail = 0, True
    spec = _enable_synthetic_execute(tmp_path, monkeypatch, _FakeClient)
    first = measurement.execute(tmp_path, spec)
    assert first["error_type"] == "RuntimeError"
    assert _FakeClient.calls == 1
    assert (tmp_path / "synthetic-measurement/spent-slot.json").is_file()
    with pytest.raises(FileExistsError):
        measurement.execute(tmp_path, spec)
    assert _FakeClient.calls == 1


def _crash_measurement(tmp_path, monkeypatch, crash_point):
    _FakeClient.calls, _FakeClient.fail = 0, False
    spec = _enable_synthetic_execute(tmp_path, monkeypatch, _FakeClient)
    recorded = {}
    original_record = measurement.RoleRunStore.record_response

    def capture_response(store, attempt, response, elapsed):
        original_record(store, attempt, response, elapsed)
        recorded.update(response=response, elapsed_seconds=elapsed)

    monkeypatch.setattr(measurement.RoleRunStore, "record_response", capture_response)
    if crash_point == "after_claim":
        monkeypatch.setattr(measurement, "read_spool", lambda *_: None)
    else:
        monkeypatch.setattr(
            measurement,
            "read_spool",
            lambda *_: SimpleNamespace(**recorded, stop_observation="stopped"),
        )

    def crash(point: str) -> None:
        if point == crash_point:
            raise RuntimeError("synthetic interruption")

    with pytest.raises(RuntimeError, match="synthetic interruption"):
        measurement.execute(tmp_path, spec, checkpoint=crash)
    return recorded


def test_recovery_after_claim_never_dispatches(tmp_path, monkeypatch) -> None:
    _crash_measurement(tmp_path, monkeypatch, "after_claim")
    assert _FakeClient.calls == 0
    monkeypatch.setattr(measurement, "_verify_recovery_authority", lambda *_: None)
    with pytest.raises(ValueError, match="no complete receipt"):
        measurement.recover(tmp_path)


def test_recovery_after_raw_never_dispatches_again(tmp_path, monkeypatch) -> None:
    _crash_measurement(tmp_path, monkeypatch, "after_raw")
    assert _FakeClient.calls == 1
    monkeypatch.setattr(measurement, "_verify_recovery_authority", lambda *_: None)
    result = measurement.recover(tmp_path)
    assert (
        result.get("dispatch") == "disabled during recovery"
        or result.get("measurement_status") == "valid"
    )
    assert measurement.recover(tmp_path).get("dispatch") == "disabled during recovery"


def test_frozen_slot_mutation_is_rejected_before_synthetic_recovery(tmp_path, monkeypatch) -> None:
    _FakeClient.calls, _FakeClient.fail = 0, False
    spec = _enable_synthetic_execute(tmp_path, monkeypatch, _FakeClient)

    def crash(_point: str) -> None:
        raise RuntimeError("synthetic interruption")

    with pytest.raises(RuntimeError, match="synthetic interruption"):
        measurement.execute(tmp_path, spec, checkpoint=crash)
    frozen_path = tmp_path / "synthetic-measurement/run/frozen.json"
    frozen = json.loads(frozen_path.read_bytes())
    frozen["config"]["spec"]["body_sha256"] = "f" * 64
    frozen_path.write_text(json.dumps(frozen))
    with pytest.raises(ValueError, match="differs from the fixed spent slot"):
        measurement.recover(tmp_path)


MEASUREMENT_WORKER = r"""
import json,os,runpy,signal,sys,time
from pathlib import Path
from types import SimpleNamespace
from congressional_globe import productive_ocr_measurement as m
from congressional_globe.productive_ocr_measurement import MeasurementSpec
base=Path(sys.argv[1]);mode=sys.argv[2]
live=runpy.run_path(str(Path.cwd()/'tests/test_productive_ocr_live.py'))
prepared,registry,bounds,client,approval,ready=live['_job'](base)
m.REPOSITORY=base;m.PACKAGE=Path('synthetic-measurement')
m._verify_spec=lambda *_:None;m._verify_runtime=lambda *_:None;m._verify_session_time=lambda *_:None
m._verify_recovery_authority=lambda *_:None
m.load_s5_inputs=lambda _: (
    prepared.job.host,
    SimpleNamespace(
        body_sha256=prepared.job.body_sha256,
        body_utf8=prepared.job.body_utf8,
    ),
    registry,
)
spec=MeasurementSpec(
    contract='productive-ocr-s5-measurement-v1',
    approval_sha256=m.APPROVAL_SHA,
    body_sha256=prepared.job.body_sha256,
    code_sha256='c'*64,
    started_at_epoch=time.time(),
    plan=client.plan,
)
if mode=='crash':
    def checkpoint(name):
        if name=='after_raw':os.kill(os.getpid(),signal.SIGKILL)
    m.execute(base,spec,checkpoint=checkpoint)
elif mode=='recover':
    result=m.recover(base)
    try:m.execute(base,spec)
    except FileExistsError:blocked=True
    else:blocked=False
    print(json.dumps({'result':result,'second_dispatch_blocked':blocked}))
"""


def _measurement_worker(tmp_path: Path, mode: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", MEASUREMENT_WORKER, str(tmp_path), mode],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_fresh_process_recovers_real_fake_http_spool_without_second_post(tmp_path: Path) -> None:
    crashed = _measurement_worker(tmp_path, "crash")
    assert crashed.returncode == -signal.SIGKILL, crashed.stderr
    recovered = _measurement_worker(tmp_path, "recover")
    assert recovered.returncode == 0, recovered.stderr
    result = json.loads(recovered.stdout)
    assert result["result"]["measurement_status"] == "valid"
    assert result["second_dispatch_blocked"]
    logs = list((tmp_path / "synthetic-measurement/run/spool").glob("*/home/requests.log"))
    assert len(logs) == 1
    assert logs[0].read_text().splitlines().count("POST") == 1
