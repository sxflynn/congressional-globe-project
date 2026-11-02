"""Fixed compact experiment keeps actual wire and validation-context identities distinct."""

import json
from pathlib import Path

import pytest

from congressional_globe import productive_ocr_compact_measurement as compact
from congressional_globe.productive_ocr_compact import decode_provider
from congressional_globe.productive_ocr_measurement_inputs import load_audit_inputs


def test_compact_request_retains_original_evidence_schema_image_and_options():
    host, wire, _registry = compact.load_compact_inputs(Path("."))
    original_host, original, _registry = load_audit_inputs(Path("."), "D1")
    assert host == original_host
    before, after = json.loads(original.body_utf8), json.loads(wire.body_utf8)
    decoded = decode_provider(
        after["messages"][1]["content"],
        before["messages"][1]["content"],
        compact.ORIGINAL_PROVIDER_SHA,
    )
    assert decoded == before["messages"][1]["content"]
    for field in ("format", "model", "options", "stream", "think"):
        assert before[field] == after[field]
    assert before["messages"][1]["images"] == after["messages"][1]["images"]
    assert after["messages"][0]["content"].startswith(before["messages"][0]["content"])
    assert wire.body_sha256 == compact.BODY_SHA != original.body_sha256


def _export_packet():
    host, wire, _registry = compact.load_compact_inputs(Path("."))
    return {"window_id": "D1C", "host": host, "body_utf8": wire.body_utf8}


def test_compact_export_explicitly_distinguishes_actual_request_from_shape_context():
    packet = _export_packet()
    response = {"output_text": "{}", "usage": {"input_tokens": 1, "output_tokens": 1}}
    result = compact.export_compact_reply(Path("."), packet, response, 1.0)
    assert result["outcome"] == "invalid"
    assert result["actual_provider_request_sha256"] == compact.BODY_SHA
    original = result["original_shape_validation"]
    assert original["provider_request_sha256"] == result["original_validation_request_sha256"]
    assert original["provider_request_sha256"] != result["actual_provider_request_sha256"]
    assert original["raw_reply_text"] == "{}"
    assert "not sent" in result["validation_scope"]


@pytest.mark.parametrize("field", ["body_utf8", "window_id", "host"])
def test_compact_export_refuses_foreign_wire_window_or_host(field):
    packet = _export_packet()
    packet[field] = {} if field == "host" else "changed"
    with pytest.raises(ValueError, match="fixed actual request"):
        compact.export_compact_reply(Path("."), packet, {}, 1.0)


def test_compact_authority_slots_and_group_cannot_adopt_original_audit(tmp_path, monkeypatch):
    import runpy

    from congressional_globe import productive_ocr_measurement as measurement
    from congressional_globe import productive_ocr_measurement_scoped as scoped
    from congressional_globe.productive_ocr_runner import code_identity, fingerprint

    helpers = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_measurement.py")))
    spec = helpers["_spec"]().model_copy(
        update=dict(
            contract=scoped.COMPACT_PROFILES[0],
            approval_sha256=scoped.COMPACT_APPROVAL_SHA,
            body_sha256=scoped.COMPACT_BODY_SHA,
            code_sha256=fingerprint(code_identity()),
        )
    )
    measurement._verify_approval(Path("."), spec)
    assert scoped.window(spec) == "D1C"
    slots = {
        scoped.package(spec.model_copy(update={"contract": p})) for p in scoped.COMPACT_PROFILES
    }
    assert len(slots) == 3
    with pytest.raises(ValueError, match="scope differs"):
        measurement._verify_approval(
            Path("."), spec.model_copy(update={"body_sha256": scoped.D1_BODY_SHA})
        )
    monkeypatch.setattr(scoped, "COMPACT_PACKAGE", Path("compact"))
    root = tmp_path / "compact"
    root.mkdir()
    group = dict(
        contract="productive-ocr-d1-scoped-group-v1",
        approval_sha256=spec.approval_sha256,
        body_sha256=spec.body_sha256,
        code_sha256=spec.code_sha256,
        started_at_epoch=spec.started_at_epoch,
        deadline_epoch=spec.started_at_epoch + 1800,
        calls=3,
    )
    (root / "group.json").write_text(json.dumps(group))
    with pytest.raises(ValueError, match="another sample"):
        scoped.verify_group(tmp_path, spec, {})
    group["contract"] = "productive-ocr-d1c-scoped-group-v1"
    (root / "group.json").write_text(json.dumps(group))
    assert scoped.verify_group(tmp_path, spec, {})


def test_compact_raw_receipt_recovery_uses_distinct_window_without_another_send(
    tmp_path, monkeypatch
):
    import runpy
    from types import SimpleNamespace

    from congressional_globe import productive_ocr_measurement as measurement
    from congressional_globe import productive_ocr_measurement_scoped as scoped

    helpers = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_measurement.py")))
    client = helpers["_FakeClient"]
    client.calls, client.fail = 0, False
    spec = helpers["_enable_synthetic_execute"](tmp_path, monkeypatch, client)
    monkeypatch.setattr(scoped, "COMPACT_PACKAGE", Path("compact"))
    monkeypatch.setattr(scoped, "verify_group", lambda *_: "e" * 64)
    spec = spec.model_copy(
        update=dict(contract=scoped.COMPACT_PROFILES[0], body_sha256=compact.BODY_SHA)
    )
    projection = SimpleNamespace(body_sha256=compact.BODY_SHA, body_utf8="{}")
    monkeypatch.setattr(measurement, "_load_inputs", lambda *_: ({}, projection, None))

    def checkpoint(name):
        if name == "after_raw":
            raise RuntimeError("synthetic interrupted compact audit")

    with pytest.raises(RuntimeError, match="interrupted compact"):
        measurement.execute(tmp_path, spec, checkpoint)
    saved = SimpleNamespace(
        response=helpers["_FakeCall"]().result(120), elapsed_seconds=0.1, stop_observation="stopped"
    )
    monkeypatch.setattr(measurement, "_verify_recovery_authority", lambda *_: None)
    monkeypatch.setattr(measurement, "read_spool", lambda *_: saved)
    assert measurement.recover(tmp_path, spec)["measurement_status"] == "valid"
    assert measurement.recover(tmp_path, spec)["dispatch"] == "disabled during recovery"
    assert client.calls == 1
