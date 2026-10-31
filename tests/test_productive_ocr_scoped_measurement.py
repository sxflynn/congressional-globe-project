"""Source identity and bounded repeat group; no real model calls."""

import hashlib
import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

from congressional_globe import productive_ocr_measurement as measurement
from congressional_globe import productive_ocr_measurement_scoped as scoped
from congressional_globe.productive_ocr_measurement_inputs import load_s5_scoped_inputs
from congressional_globe.productive_ocr_runner import code_identity, fingerprint

HELPERS = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_measurement.py")))


def _spec(number=1):
    return HELPERS["_spec"]().model_copy(
        update=dict(
            contract=scoped.PROFILES[number - 1],
            approval_sha256=scoped.APPROVAL_SHA,
            body_sha256=scoped.BODY_SHA,
            code_sha256=fingerprint(code_identity()),
        )
    )


def test_exact_scoped_wire_body_and_three_distinct_fixed_slots():
    host, projection, _registry = load_s5_scoped_inputs(Path("."))
    assert projection.body_sha256 == scoped.BODY_SHA
    assert host["payload"]["code_sha256"] == fingerprint(code_identity())
    assert len({measurement._package(_spec(i)) for i in (1, 2, 3)}) == 3
    measurement._verify_approval(Path("."), _spec())
    assert len(json.loads(projection.body_utf8)["messages"]) == 2


def _group(tmp_path, monkeypatch, number=1):
    monkeypatch.setattr(scoped, "PACKAGE", Path("group"))
    spec = _spec(number)
    root = tmp_path / scoped.PACKAGE
    root.mkdir()
    group = dict(
        contract="productive-ocr-s5-scoped-group-v1",
        approval_sha256=scoped.APPROVAL_SHA,
        body_sha256=scoped.BODY_SHA,
        code_sha256=spec.code_sha256,
        started_at_epoch=spec.started_at_epoch,
        deadline_epoch=spec.started_at_epoch + 1800,
        calls=3,
    )
    (root / "group.json").write_text(json.dumps(group))
    return spec, root, group


@pytest.mark.parametrize(
    "field,value", [("body_sha256", "a" * 64), ("calls", 4), ("deadline_epoch", 1)]
)
def test_changed_group_scope_or_budget_refused(tmp_path, monkeypatch, field, value):
    spec, root, group = _group(tmp_path, monkeypatch)
    group[field] = value
    (root / "group.json").write_text(json.dumps(group))
    with pytest.raises(ValueError):
        scoped.verify_group(tmp_path, spec, {"synthetic": "packet"})


def test_group_expiry_and_late_session_refused(tmp_path, monkeypatch):
    spec, _root, group = _group(tmp_path, monkeypatch)
    scoped.verify_group(tmp_path, spec, {"synthetic": "packet"})
    late = spec.model_copy(update={"started_at_epoch": group["deadline_epoch"] - 599})
    with pytest.raises(ValueError, match="outside group"):
        scoped.verify_group(tmp_path, late, {"synthetic": "packet"})
    monkeypatch.setattr(scoped.time, "time", lambda: group["deadline_epoch"] + 1)
    with pytest.raises(TimeoutError, match="deadline"):
        scoped.verify_group(tmp_path, spec, {"synthetic": "packet"})


def _previous(root, spec, result, number=1):
    directory = root / f"repeat-{number}"
    (directory / "run").mkdir(parents=True)
    prior = spec.model_dump(mode="json")
    prior["contract"] = scoped.PROFILES[number - 1]
    config = dict(
        spec=prior,
        max_output_tokens=1500,
        group_sha256=hashlib.sha256((root / "group.json").read_bytes()).hexdigest(),
    )
    (directory / "spent-slot.json").write_text(json.dumps(config))
    (directory / "run/frozen.json").write_text(
        json.dumps(dict(config=config, packet={"synthetic": "packet"}))
    )
    (directory / "run/result.json").write_text(json.dumps(result))
    return directory


def _result():
    return dict(
        status="completed",
        finish_reason="stop",
        output_text="synthetic invalid reply",
        usage=dict(input_tokens=10, output_tokens=5),
        owned_stop_observation="stopped",
        measurement_status="invalid",
    )


@pytest.mark.parametrize(
    "change",
    [
        dict(owned_stop_observation="unknown"),
        dict(usage=None),
        dict(status="failed"),
        dict(finish_reason="length"),
        dict(usage=dict(input_tokens=1, output_tokens=1501)),
    ],
)
def test_unknown_stop_usage_or_transport_failure_blocks_next(tmp_path, monkeypatch, change):
    spec, root, _group_data = _group(tmp_path, monkeypatch, 2)
    result = {**_result(), **change}
    _previous(root, spec, result)
    with pytest.raises(ValueError):
        scoped.verify_group(tmp_path, spec, {"synthetic": "packet"})


def test_completed_semantic_failure_counts_but_changed_receipt_blocks_next(tmp_path, monkeypatch):
    spec, root, _group_data = _group(tmp_path, monkeypatch, 2)
    result = _result()
    _previous(root, spec, result)
    receipt = SimpleNamespace(
        stop_observation="stopped", response=result.copy(), receipt_sha256="a" * 64
    )
    monkeypatch.setattr(scoped, "read_spool", lambda *_: receipt)
    scoped.verify_group(tmp_path, spec, {"synthetic": "packet"})
    receipt.response["output_text"] = "different"
    with pytest.raises(ValueError, match="durable transport"):
        scoped.verify_group(tmp_path, spec, {"synthetic": "packet"})


def test_prior_slot_required_before_second_and_third(tmp_path, monkeypatch):
    spec, root, _group_data = _group(tmp_path, monkeypatch, 2)
    with pytest.raises(FileNotFoundError):
        scoped.verify_group(tmp_path, spec, {"synthetic": "packet"})
    _previous(root, spec, _result())
    monkeypatch.setattr(scoped, "read_spool", lambda *_: None)
    with pytest.raises(ValueError, match="positive stop receipt"):
        scoped.verify_group(tmp_path, spec, {"synthetic": "packet"})


def test_failed_start_spends_repeat_slot_without_retry(tmp_path, monkeypatch):
    client = HELPERS["_FakeClient"]
    client.calls, client.fail = 0, True
    original = HELPERS["_enable_synthetic_execute"](tmp_path, monkeypatch, client)
    monkeypatch.setattr(scoped, "PACKAGE", Path("group"))
    monkeypatch.setattr(scoped, "verify_group", lambda *_: None)
    spec = original.model_copy(
        update=dict(contract=scoped.PROFILES[0], body_sha256=scoped.BODY_SHA)
    )
    projection = SimpleNamespace(body_sha256=scoped.BODY_SHA, body_utf8="{}")
    monkeypatch.setattr(measurement, "_load_inputs", lambda *_: ({}, projection, None))
    assert measurement.execute(tmp_path, spec)["error_type"] == "RuntimeError"
    with pytest.raises(FileExistsError):
        measurement.execute(tmp_path, spec)
    assert client.calls == 1


def test_group_root_symlink_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(scoped, "PACKAGE", Path("link"))
    actual = tmp_path / "actual"
    actual.mkdir()
    (tmp_path / "link").symlink_to(actual, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinks"):
        scoped.verify_group(tmp_path, _spec(), {})


@pytest.mark.parametrize("change", ["profile", "frozen", "deadline"])
def test_copied_profile_frozen_packet_or_reset_deadline_refused(tmp_path, monkeypatch, change):
    spec, root, group = _group(tmp_path, monkeypatch, 2)
    directory = _previous(root, spec, _result())
    if change == "profile":
        p = directory / "spent-slot.json"
        saved = json.loads(p.read_text())
        saved["spec"]["contract"] = scoped.PROFILES[1]
        p.write_text(json.dumps(saved))
    if change == "frozen":
        (directory / "run/frozen.json").write_text("{}")
    if change == "deadline":
        group["started_at_epoch"] -= 1
        group["deadline_epoch"] -= 1
        (root / "group.json").write_text(json.dumps(group))
    with pytest.raises(ValueError):
        scoped.verify_group(tmp_path, spec, {"synthetic": "packet"})


def test_duplicate_receipts_do_not_count_as_two_observations(tmp_path, monkeypatch):
    spec, root, _group_data = _group(tmp_path, monkeypatch, 3)
    result = _result()
    _previous(root, spec, result, 1)
    _previous(root, spec, result, 2)
    receipt = SimpleNamespace(stop_observation="stopped", response=result, receipt_sha256="a" * 64)
    monkeypatch.setattr(scoped, "read_spool", lambda *_: receipt)
    with pytest.raises(ValueError, match="same transport receipt"):
        scoped.verify_group(tmp_path, spec, {"synthetic": "packet"})
