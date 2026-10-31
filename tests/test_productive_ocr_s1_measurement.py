"""Original S1 routing and fixed repeat identities; no provider calls."""

import json
import runpy
import time
from pathlib import Path

import pytest

from congressional_globe import productive_ocr_measurement as measurement
from congressional_globe import productive_ocr_measurement_scoped as scoped
from congressional_globe.productive_ocr_measurement_inputs import load_s1_scoped_inputs
from congressional_globe.productive_ocr_runner import code_identity, fingerprint

HELPERS = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_measurement.py")))


def _spec(number=1):
    return HELPERS["_spec"]().model_copy(
        update=dict(
            contract=scoped.S1_PROFILES[number - 1],
            approval_sha256=scoped.S1_APPROVAL_SHA,
            body_sha256=scoped.S1_BODY_SHA,
            code_sha256=fingerprint(code_identity()),
        )
    )


def test_s1_exact_request_preserves_feedback_numbers_and_source_boundaries():
    host, projection, registry = load_s1_scoped_inputs(Path("."))
    assert projection.body_sha256 == scoped.S1_BODY_SHA
    assert host["payload"]["code_sha256"] == fingerprint(code_identity())
    assert host["payload"]["unit_id"] == "S1"
    assert host["payload"]["image"]["bindings"][0]["crop_region"] == dict(
        left=64, top=64, right=964, bottom=741
    )
    context = host["payload"]["image"]["scope"]["visible_context"][0]
    assert context["text"] == "Suppose we refuse to pass this proposition"
    assert context["parent_visibility"] == "partial"
    prompt = registry.files[host["payload"]["prompt_sha256"]].decode()
    assert "loyal" in prompt and "substantially similar" in prompt
    signals = host["payload"]["diagnostics"]["signals"]
    numbers = {s["raw_quote"] for s in signals if s["category"] == "number"}
    assert {"two", "three", "one"} <= numbers


def test_s1_profiles_have_separate_authority_window_and_slots():
    assert scoped.window(_spec()) == "S1"
    measurement._verify_approval(Path("."), _spec())
    slots = {measurement._package(_spec(i)) for i in (1, 2, 3)}
    assert len(slots) == 3
    assert not slots.intersection({scoped.PACKAGE / f"repeat-{i}" for i in (1, 2, 3)})


@pytest.mark.parametrize(
    "body", [measurement.BODY_SHA, measurement.CONFORMANCE_BODY_SHA, scoped.BODY_SHA]
)
def test_s1_profile_rejects_historical_s5_body(body):
    with pytest.raises(ValueError, match="scope differs"):
        measurement._verify_approval(Path("."), _spec().model_copy(update={"body_sha256": body}))


def test_s1_group_cannot_adopt_s5_group_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(scoped, "S1_PACKAGE", Path("s1"))
    spec = _spec()
    root = tmp_path / "s1"
    root.mkdir()
    group = dict(
        contract="productive-ocr-s5-scoped-group-v1",
        approval_sha256=scoped.S1_APPROVAL_SHA,
        body_sha256=scoped.S1_BODY_SHA,
        code_sha256=spec.code_sha256,
        started_at_epoch=spec.started_at_epoch,
        deadline_epoch=spec.started_at_epoch + 1800,
        calls=3,
    )
    (root / "group.json").write_text(json.dumps(group))
    with pytest.raises(ValueError, match="another sample"):
        scoped.verify_group(tmp_path, spec, {})
    group["contract"] = "productive-ocr-s1-scoped-group-v1"
    (root / "group.json").write_text(json.dumps(group))
    assert scoped.verify_group(tmp_path, spec, {})


def test_s1_runtime_observation_rejects_s5_window(tmp_path, monkeypatch):
    spec = _spec()
    proof = dict(
        contract="productive-ocr-live-runtime-observation-v1",
        readiness_sha256=fingerprint(spec.model_dump(mode="json")),
        window_id="S5",
        checked_at_epoch=time.time(),
        process_evidence_sha256="a" * 64,
        queue_evidence_sha256="b" * 64,
        log_evidence_sha256="c" * 64,
        model_metadata_sha256="d" * 64,
        competing_requests=0,
    )
    (tmp_path / "runtime.json").write_text(json.dumps(proof))
    monkeypatch.setattr(measurement, "_verify_runtime_files", lambda *_: None)
    with pytest.raises(ValueError, match="does not bind"):
        measurement._verify_runtime(tmp_path, spec)


def test_s1_receipt_recovery_uses_s1_window_without_new_send(tmp_path, monkeypatch):
    from types import SimpleNamespace

    client = HELPERS["_FakeClient"]
    client.calls, client.fail = 0, False
    spec = HELPERS["_enable_synthetic_execute"](tmp_path, monkeypatch, client)
    monkeypatch.setattr(scoped, "S1_PACKAGE", Path("s1"))
    monkeypatch.setattr(scoped, "verify_group", lambda *_: "e" * 64)
    spec = spec.model_copy(
        update=dict(contract=scoped.S1_PROFILES[0], body_sha256=scoped.S1_BODY_SHA)
    )
    projection = SimpleNamespace(body_sha256=scoped.S1_BODY_SHA, body_utf8="{}")
    monkeypatch.setattr(measurement, "_load_inputs", lambda *_: ({}, projection, None))

    def checkpoint(name):
        if name == "after_raw":
            raise RuntimeError("synthetic interrupted S1")

    with pytest.raises(RuntimeError, match="interrupted S1"):
        measurement.execute(tmp_path, spec, checkpoint)
    saved = SimpleNamespace(
        response=HELPERS["_FakeCall"]().result(120), elapsed_seconds=0.1, stop_observation="stopped"
    )
    monkeypatch.setattr(measurement, "_verify_recovery_authority", lambda *_: None)
    monkeypatch.setattr(measurement, "read_spool", lambda *_: saved)
    assert measurement.recover(tmp_path, spec)["measurement_status"] == "valid"
    assert measurement.recover(tmp_path, spec)["dispatch"] == "disabled during recovery"
    assert client.calls == 1
