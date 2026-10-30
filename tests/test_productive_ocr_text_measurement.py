"""The newly approved S5 text attempt gets one separate slot, not a v1 retry."""

import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

from congressional_globe import productive_ocr_measurement as measurement
from congressional_globe.productive_ocr_host import canonical_json
from congressional_globe.productive_ocr_local import _job_deadline
from congressional_globe.productive_ocr_measurement_inputs import load_s5_text_inputs
from congressional_globe.productive_ocr_runner import code_identity, fingerprint

HELPERS = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_measurement.py")))


def _text_spec():
    return HELPERS["_spec"]().model_copy(
        update=dict(
            contract="productive-ocr-s5-text-measurement-v2",
            approval_sha256=measurement.TEXT_APPROVAL_SHA,
            body_sha256=measurement.TEXT_BODY_SHA,
        )
    )


def test_new_exact_approval_cannot_borrow_old_slot_or_mutate_request():
    spec = _text_spec()
    measurement._verify_approval(Path("."), spec)
    assert measurement._package(spec) != measurement.PACKAGE
    with pytest.raises(ValueError, match="scope differs"):
        measurement._verify_approval(
            Path("."), spec.model_copy(update={"body_sha256": measurement.BODY_SHA})
        )
    with pytest.raises(ValueError, match="scope differs"):
        measurement._verify_approval(
            Path("."), spec.model_copy(update={"approval_sha256": measurement.APPROVAL_SHA})
        )


def test_revised_real_inputs_replay_exact_approved_body_and_current_code():
    host, projection, _registry = load_s5_text_inputs(Path("."))
    assert projection.body_sha256 == measurement.TEXT_BODY_SHA
    assert host["payload"]["code_sha256"] == fingerprint(code_identity())
    body = json.loads(projection.body_utf8)
    assert body["options"] == {"num_predict": 1500}
    assert body["model"] == "qwen3.8:27b-mlx"
    assert (
        json.loads(body["messages"][1]["content"])["reply_contract"]
        == "ocr-productive-repair-text-reply-v3"
    )
    assert canonical_json(body) == Path(measurement.TEXT_PACKAGE / "request.json").read_bytes()


def test_shared_execution_deadline_includes_startup_and_respects_session():
    spec = _text_spec()
    assert _job_deadline(spec.plan, spec.started_at_epoch, 1000.0) == 1120.0
    bounded = spec.plan.model_copy(update={"session_deadline_epoch": spec.started_at_epoch + 70})
    assert _job_deadline(bounded, spec.started_at_epoch, 1000.0) == 1070.0


def _synthetic_text(tmp_path, monkeypatch):
    spec = HELPERS["_enable_synthetic_execute"](tmp_path, monkeypatch, HELPERS["_FakeClient"])
    monkeypatch.setattr(measurement, "TEXT_PACKAGE", Path("new-text-measurement"))
    host = {"payload": {"model_digest": "b" * 64, "response_schema_sha256": "e" * 64}}
    projection = SimpleNamespace(
        body_sha256=measurement.TEXT_BODY_SHA, body_utf8='{"model":"fake:latest"}'
    )
    monkeypatch.setattr(measurement, "_load_inputs", lambda *_: (host, projection, object()))
    return spec.model_copy(
        update=dict(
            contract="productive-ocr-s5-text-measurement-v2",
            approval_sha256=measurement.TEXT_APPROVAL_SHA,
            body_sha256=measurement.TEXT_BODY_SHA,
        )
    )


def test_new_slot_is_spent_even_when_start_fails_and_old_slot_untouched(tmp_path, monkeypatch):
    client = HELPERS["_FakeClient"]
    client.calls, client.fail = 0, True
    spec = _synthetic_text(tmp_path, monkeypatch)
    old = tmp_path / measurement.PACKAGE / "spent-slot.json"
    old.parent.mkdir(parents=True)
    old.write_text('"old immutable attempt"')
    result = measurement.execute(tmp_path, spec)
    assert result["error_type"] == "RuntimeError"
    with pytest.raises(FileExistsError):
        measurement.execute(tmp_path, spec)
    assert client.calls == 1
    assert old.read_text() == '"old immutable attempt"'
    assert (tmp_path / measurement.TEXT_PACKAGE / "spent-slot.json").is_file()


def test_new_recovery_imports_saved_reply_without_second_call(tmp_path, monkeypatch):
    client = HELPERS["_FakeClient"]
    client.calls, client.fail = 0, False
    spec = _synthetic_text(tmp_path, monkeypatch)

    def checkpoint(name):
        if name == "after_raw":
            raise RuntimeError("synthetic interruption")

    with pytest.raises(RuntimeError, match="interruption"):
        measurement.execute(tmp_path, spec, checkpoint)
    monkeypatch.setattr(measurement, "_verify_recovery_authority", lambda *_: None)
    saved = SimpleNamespace(
        response=HELPERS["_FakeCall"]().result(120), elapsed_seconds=0.1, stop_observation="stopped"
    )
    # Preserve the exact stored raw reply; the synthetic helper has no real spool.
    monkeypatch.setattr(measurement, "read_spool", lambda *_: saved)
    calls = client.calls
    with pytest.raises(ValueError, match="selected recovery"):
        measurement.recover(tmp_path, spec.model_copy(update={"code_sha256": "d" * 64}))
    result = measurement.recover(tmp_path, spec)
    assert result["measurement_status"] == "valid"
    assert client.calls == calls
    assert measurement.recover(tmp_path, spec)["dispatch"] == "disabled during recovery"


@pytest.mark.parametrize(
    "outcome,expected",
    [
        ({"proposal_status": "findings"}, "valid"),
        ({"proposal_status": "unresolved"}, "unresolved"),
        ("invalid", "invalid"),
    ],
)
def test_live_text_outcomes_preserve_withholding_and_rejection(outcome, expected):
    response = dict(status="completed", finish_reason="stop", usage={"output_tokens": 20})
    assert measurement._result_status(response, {"outcome": outcome}, "stopped") == expected
