"""Exact original saved-failure audits; no model calls."""

import json
import runpy
from pathlib import Path

import pytest

from congressional_globe import productive_ocr_measurement as measurement
from congressional_globe import productive_ocr_measurement_scoped as scoped
from congressional_globe.productive_ocr_measurement_inputs import load_audit_inputs
from congressional_globe.productive_ocr_runner import code_identity, fingerprint

HELPERS = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_measurement.py")))


def _spec(unit, number=1):
    return HELPERS["_spec"]().model_copy(
        update=dict(
            contract=getattr(scoped, f"{unit}_PROFILES")[number - 1],
            approval_sha256=getattr(scoped, f"{unit}_APPROVAL_SHA"),
            body_sha256=getattr(scoped, f"{unit}_BODY_SHA"),
            code_sha256=fingerprint(code_identity()),
        )
    )


@pytest.mark.parametrize("unit,count", [("D1", 4), ("D2", 9)])
def test_audit_preserves_all_original_targets_proposal_and_image(unit, count):
    host, projection, registry = load_audit_inputs(Path("."), unit)
    payload = host["payload"]
    original = json.loads(
        Path(f"artifacts/study-input-assembly-20261029-01/{unit}/host.json").read_text()
    )["payload"]
    assert projection.body_sha256 == getattr(scoped, f"{unit}_BODY_SHA")
    assert payload["code_sha256"] == fingerprint(code_identity())
    assert payload["role"] == "audit_saved_proposal"
    assert len(payload["paragraphs"]) == count
    for field in ("paragraphs", "image", "saved_proposal", "diagnostics", "prompt_sha256"):
        assert payload[field] == original[field]
    saved = payload["saved_proposal"]
    assert saved["prior_raw_reply_sha256"] in registry.files
    assert saved["prior_request_sha256"] in registry.files
    assert json.loads(projection.body_utf8)["options"]["num_predict"] == 1500


@pytest.mark.parametrize("unit", ["D1", "D2"])
def test_audit_profiles_authority_window_and_slots_are_disjoint(unit):
    spec = _spec(unit)
    measurement._verify_approval(Path("."), spec)
    assert scoped.window(spec) == unit
    mine = {measurement._package(_spec(unit, i)) for i in (1, 2, 3)}
    other = "D2" if unit == "D1" else "D1"
    theirs = {measurement._package(_spec(other, i)) for i in (1, 2, 3)}
    assert len(mine) == 3 and not mine.intersection(theirs)
    for foreign in (scoped.BODY_SHA, scoped.S1_BODY_SHA, scoped.S2_BODY_SHA):
        with pytest.raises(ValueError, match="scope differs"):
            measurement._verify_approval(
                Path("."), spec.model_copy(update={"body_sha256": foreign})
            )


@pytest.mark.parametrize("unit", ["D1", "D2"])
def test_audit_group_refuses_other_case_contract(tmp_path, monkeypatch, unit):
    monkeypatch.setattr(scoped, f"{unit}_PACKAGE", Path(unit))
    spec = _spec(unit)
    root = tmp_path / unit
    root.mkdir()
    group = dict(
        contract="productive-ocr-s2-scoped-group-v1",
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
    group["contract"] = f"productive-ocr-{unit.lower()}-scoped-group-v1"
    (root / "group.json").write_text(json.dumps(group))
    assert scoped.verify_group(tmp_path, spec, {})
