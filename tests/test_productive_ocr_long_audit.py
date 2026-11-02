"""Only the named diagnostic can use300seconds; legacy plans remain bounded120."""

import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from congressional_globe import productive_ocr_measurement as measurement
from congressional_globe import productive_ocr_measurement_scoped as scoped
from congressional_globe.productive_ocr_local import OwnedLocalPlan
from congressional_globe.productive_ocr_long_audit import LongerAuditPlan, validate_diagnostic_plan

HELPERS = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_measurement.py")))


def _long_spec():
    base = HELPERS["_spec"]()
    plan = base.plan.model_dump(mode="json")
    plan.update(diagnostic_contract="productive-ocr-d1-longer-plan-v1", request_timeout_seconds=300)
    data = base.model_dump(mode="json")
    data.update(
        contract=scoped.LONG_PROFILES[0],
        approval_sha256=scoped.LONG_APPROVAL_SHA,
        body_sha256=scoped.LONG_BODY_SHA,
        plan=plan,
    )
    return measurement.MeasurementSpec.model_validate_json(json.dumps(data))


def test_closed_longer_plan_preserves_legacy_limit_and_roundtrips():
    spec = _long_spec()
    assert type(spec.plan) is LongerAuditPlan
    assert validate_diagnostic_plan(spec.plan).request_timeout_seconds == 300
    assert (
        type(measurement.MeasurementSpec.model_validate_json(spec.model_dump_json()).plan)
        is LongerAuditPlan
    )
    with pytest.raises(ValidationError):
        OwnedLocalPlan.model_validate_json(spec.plan.model_dump_json())
    data = spec.plan.model_dump(mode="json")
    data.pop("diagnostic_contract")
    with pytest.raises(ValidationError):
        OwnedLocalPlan.model_validate_json(json.dumps(data))
    data["diagnostic_contract"] = "productive-ocr-d1-longer-plan-v1"
    data["request_timeout_seconds"] = 301
    with pytest.raises(ValidationError):
        LongerAuditPlan.model_validate_json(json.dumps(data))


def test_longer_profile_authority_window_slots_and_fixed_budget():
    spec = _long_spec()
    measurement._verify_approval(Path("."), spec)
    assert scoped.window(spec) == "D1L"
    assert measurement._timeout_seconds(spec) == 300
    assert measurement._prep_seconds(spec) == 90
    slots = {scoped.package(spec.model_copy(update={"contract": p})) for p in scoped.LONG_PROFILES}
    assert len(slots) == 3
    assert scoped.package(spec).parent != scoped.COMPACT_PACKAGE
    legacy = HELPERS["_spec"]()
    assert measurement._timeout_seconds(legacy) == 120
    assert measurement._prep_seconds(legacy) == 300


def test_receive_uses_selected_timeout_and_preserves_positive_stop(monkeypatch):
    seen = []

    class Call:
        def result(self, timeout):
            seen.append(timeout)
            return {"status": "completed"}

        def observe(self):
            return "stopped"

    store = SimpleNamespace(record_response=lambda *_: None)
    monkeypatch.setattr(measurement, "_finish_response", lambda *args: args[-1])
    assert (
        measurement._receive(Path("."), {}, store, 1, Call(), 0, lambda _: None, 300) == "stopped"
    )
    assert seen == [300]


@pytest.mark.parametrize("long_profile,long_plan", [(False, True), (True, False)])
def test_backend_refuses_cross_adoption_of_lifecycle_bound(monkeypatch, long_profile, long_plan):
    monkeypatch.setattr(measurement, "MODEL_NAME", "fake:latest")
    monkeypatch.setattr(measurement, "MODEL_DIGEST", "b" * 64)
    monkeypatch.setattr(measurement, "EXECUTABLE_SHA", "a" * 64)
    spec = _long_spec() if long_profile else HELPERS["_spec"]()
    plan = _long_spec().plan if long_plan else HELPERS["_spec"]().plan
    exe = "/Applications/Ollama.app/Contents/Resources/ollama"
    plan = plan.model_copy(update={"executable": exe, "argv": (exe, "serve")})
    with pytest.raises(ValueError, match="fixed diagnostic time bound"):
        measurement._verify_backend(spec.model_copy(update={"plan": plan}))


def test_failure_observation_keeps_only_bounded_cause_type_names():
    cause = TimeoutError("do not include arbitrary cause contents")
    middle = RuntimeError("HTTP failed")
    middle.__cause__ = cause
    top = RuntimeError("request failed")
    top.__cause__ = middle
    assert measurement._error_cause_types(top) == ["RuntimeError", "RuntimeError", "TimeoutError"]


def test_long_profile_reconstructs_compact_d1_not_legacy_s5():
    spec = _long_spec()
    host, projection, _registry = measurement._load_inputs(Path("."), spec)
    assert host["payload"]["unit_id"] == "D1"
    assert projection.body_sha256 == scoped.LONG_BODY_SHA
    assert projection.body_sha256 == scoped.COMPACT_BODY_SHA != scoped.BODY_SHA
    assert scoped.window(spec) == "D1L"


def test_long_raw_receipt_recovery_retains_window_without_another_send(tmp_path, monkeypatch):
    class Call:
        def result(self, timeout):
            assert timeout == 300
            return {
                "status": "completed",
                "finish_reason": "stop",
                "output_text": "ok",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }

        def observe(self):
            return "stopped"

    class Client:
        calls = 0

        def __init__(self, *_args, **_kwargs):
            pass

        def start(self, _body):
            type(self).calls += 1
            return Call()

    spec = HELPERS["_enable_synthetic_execute"](tmp_path, monkeypatch, Client)
    monkeypatch.setattr(scoped, "LONG_PACKAGE", Path("long"))
    monkeypatch.setattr(scoped, "verify_group", lambda *_: "e" * 64)
    spec = spec.model_copy(
        update=dict(
            contract=scoped.LONG_PROFILES[0],
            body_sha256=scoped.LONG_BODY_SHA,
            plan=_long_spec().plan,
        )
    )
    projection = SimpleNamespace(body_sha256=scoped.LONG_BODY_SHA, body_utf8="{}")
    monkeypatch.setattr(measurement, "_load_inputs", lambda *_: ({}, projection, None))

    def checkpoint(name):
        if name == "after_raw":
            raise RuntimeError("synthetic interrupted longer audit")

    with pytest.raises(RuntimeError, match="interrupted longer"):
        measurement.execute(tmp_path, spec, checkpoint)
    saved = SimpleNamespace(
        response=Call().result(300), elapsed_seconds=0.1, stop_observation="stopped"
    )
    monkeypatch.setattr(measurement, "_verify_recovery_authority", lambda *_: None)
    monkeypatch.setattr(measurement, "read_spool", lambda *_: saved)
    assert measurement.recover(tmp_path, spec)["measurement_status"] == "valid"
    assert measurement.recover(tmp_path, spec)["dispatch"] == "disabled during recovery"
    assert Client.calls == 1
