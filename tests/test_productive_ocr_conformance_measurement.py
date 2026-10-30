"""The approved strict-schema S5 attempt has its own fixed slot and source binding."""

import json
import runpy
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from congressional_globe import productive_ocr_measurement as measurement
from congressional_globe.productive_ocr_measurement_inputs import load_s5_conformance_inputs
from congressional_globe.productive_ocr_routing import TEXT_PROMPT_V4
from congressional_globe.productive_ocr_runner import code_identity, fingerprint

HELPERS = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_measurement.py")))


def _spec():
    return HELPERS["_spec"]().model_copy(
        update=dict(
            contract="productive-ocr-s5-conformance-measurement-v3",
            approval_sha256=measurement.CONFORMANCE_APPROVAL_SHA,
            body_sha256=measurement.CONFORMANCE_BODY_SHA,
        )
    )


def test_exact_direct_chat_approval_has_distinct_profile_and_slot():
    spec = _spec()
    measurement._verify_approval(Path("."), spec)
    assert measurement._package(spec) not in [measurement.PACKAGE, measurement.TEXT_PACKAGE]
    assert measurement._prep_seconds(spec) == 270


@pytest.mark.parametrize("body", [measurement.BODY_SHA, measurement.TEXT_BODY_SHA])
def test_new_profile_cannot_use_either_historical_request(body):
    with pytest.raises(ValueError, match="scope differs"):
        measurement._verify_approval(Path("."), _spec().model_copy(update={"body_sha256": body}))


def test_real_strict_inputs_bind_exact_body_prompt_schema_source_and_current_code():
    host, projection, _registry = load_s5_conformance_inputs(Path("."))
    assert projection.body_sha256 == measurement.CONFORMANCE_BODY_SHA
    assert host["payload"]["code_sha256"] == fingerprint(code_identity())
    body = json.loads(projection.body_utf8)
    assert body["messages"][0]["content"] == TEXT_PROMPT_V4
    assert len(body["format"]["$defs"]["TextReading"]["oneOf"]) == 2
    assert body["options"] == {"num_predict": 1500}
    assert body["model"] == "qwen3.8:27b-mlx"


def _synthetic(tmp_path, monkeypatch):
    spec = HELPERS["_enable_synthetic_execute"](tmp_path, monkeypatch, HELPERS["_FakeClient"])
    monkeypatch.setattr(measurement, "CONFORMANCE_PACKAGE", Path("synthetic-conformance"))
    host = {"payload": {"model_digest": "b" * 64, "response_schema_sha256": "c" * 64}}
    projection = SimpleNamespace(
        body_sha256=measurement.CONFORMANCE_BODY_SHA, body_utf8='{"model":"fake:latest"}'
    )
    monkeypatch.setattr(measurement, "_load_inputs", lambda *_: (host, projection, object()))
    return spec.model_copy(
        update=dict(
            contract="productive-ocr-s5-conformance-measurement-v3",
            approval_sha256=measurement.CONFORMANCE_APPROVAL_SHA,
            body_sha256=measurement.CONFORMANCE_BODY_SHA,
        )
    )


def test_failed_start_spends_new_slot_without_touching_either_old_slot(tmp_path, monkeypatch):
    client = HELPERS["_FakeClient"]
    client.calls, client.fail = 0, True
    spec = _synthetic(tmp_path, monkeypatch)
    old = [
        tmp_path / measurement.PACKAGE / "spent-slot.json",
        tmp_path / measurement.TEXT_PACKAGE / "spent-slot.json",
    ]
    for path in old:
        path.parent.mkdir(parents=True)
        path.write_text("old immutable slot")
    result = measurement.execute(tmp_path, spec)
    assert result["error_type"] == "RuntimeError"
    with pytest.raises(FileExistsError):
        measurement.execute(tmp_path, spec)
    assert client.calls == 1
    assert [path.read_text() for path in old] == ["old immutable slot"] * 2


def test_receipt_recovery_does_not_repeat_strict_profile_send(tmp_path, monkeypatch):
    client = HELPERS["_FakeClient"]
    client.calls, client.fail = 0, False
    spec = _synthetic(tmp_path, monkeypatch)

    def checkpoint(name):
        if name == "after_raw":
            raise RuntimeError("synthetic interruption")

    with pytest.raises(RuntimeError, match="interruption"):
        measurement.execute(tmp_path, spec, checkpoint)
    saved = SimpleNamespace(
        response=HELPERS["_FakeCall"]().result(120), elapsed_seconds=0.1, stop_observation="stopped"
    )
    monkeypatch.setattr(measurement, "_verify_recovery_authority", lambda *_: None)
    monkeypatch.setattr(measurement, "read_spool", lambda *_: saved)
    assert measurement.recover(tmp_path, spec)["measurement_status"] == "valid"
    assert measurement.recover(tmp_path, spec)["dispatch"] == "disabled during recovery"
    assert client.calls == 1


@pytest.mark.parametrize("reason,valid", [(None, True), ("No further action required.", False)])
def test_strict_real_packet_export_preserves_actual_failure_and_expected_shape(reason, valid):
    host, projection, _registry = load_s5_conformance_inputs(Path("."))
    original = json.loads(
        Path("artifacts/s5-text-measurement-20261030-01/run/result.json").read_bytes()
    )
    reply = json.loads(original["output_text"])
    reply["readings"][0]["reason"] = reason
    exported = measurement._export(
        {"host": host, "body_utf8": projection.body_utf8}, {"output_text": json.dumps(reply)}, 0.1
    )
    assert (exported["outcome"] != "invalid") == valid


def test_conformance_preparation_expires_at_270_seconds():
    started = time.time() - 271
    spec = _spec().model_copy(update={"started_at_epoch": started})
    spec = spec.model_copy(
        update={"plan": spec.plan.model_copy(update={"session_deadline_epoch": started + 600})}
    )
    with pytest.raises(TimeoutError, match="preparation exceeded"):
        measurement._verify_session_time(spec)
