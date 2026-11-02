"""Guard the sole schema-pattern change, host parity and separately spent slots."""

import copy
import json
import re
import runpy
from pathlib import Path

import pytest

from congressional_globe import productive_ocr_lean_audit as lean
from congressional_globe import productive_ocr_measurement as measurement
from congressional_globe import productive_ocr_measurement_scoped as scoped
from congressional_globe import productive_ocr_whole_audit as whole
from congressional_globe.productive_ocr_measurement_inputs import load_scoped_inputs

HELPERS = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_lean_audit.py")))


def _spec():
    return HELPERS["_spec"]().model_copy(
        update=dict(
            contract=scoped.WHOLE_PROFILES[0],
            approval_sha256=scoped.WHOLE_APPROVAL_SHA,
            body_sha256=scoped.WHOLE_BODY_SHA,
        )
    )


def test_only_four_patterns_change_with_identical_source_and_unchanged_host():
    old_host, old, _ = lean.load_lean_inputs(Path("."))
    host, projection, _ = whole.load_whole_inputs(Path("."))
    assert host == old_host
    before, after = json.loads(old.body_utf8), json.loads(projection.body_utf8)
    expected = copy.deepcopy(before)
    concern = expected["format"]["$defs"]["LeanConcern"]["properties"]
    concern["quote"]["pattern"] = whole.NONBLANK
    concern["reason"]["pattern"] = whole.NONBLANK
    concern["reading"]["anyOf"][0]["pattern"] = whole.READING
    expected["format"]["$defs"]["LeanTarget"]["properties"]["reason"]["anyOf"][0]["pattern"] = (
        whole.NONBLANK
    )
    assert after == expected
    assert projection.body_sha256 == scoped.WHOLE_BODY_SHA != scoped.LEAN_BODY_SHA
    assert projection.prompt_sha256 == old.prompt_sha256
    assert projection.schema_sha256 != old.schema_sha256


@pytest.mark.parametrize(
    "text", ["CCCXI", " source quote ", "line\nbreak\n", "café", "\u00a0x\u00a0", "\ufeff"]
)
def test_whole_patterns_allow_multichar_newline_unicode_and_match_host(text):
    assert re.search(whole.NONBLANK, text)
    assert re.fullmatch(whole.NONBLANK, text)
    assert re.fullmatch(whole.READING, text)
    value = lean.LeanConcern(layer="raw", quote=text, reading=None, reason=text)
    assert value.quote == text


@pytest.mark.parametrize("text", ["", " ", "\t\n", "\u00a0", "\u2003\n"])
def test_empty_and_whitespace_rejected_except_exact_empty_deletion(text):
    assert not re.search(whole.NONBLANK, text)
    assert bool(re.fullmatch(whole.READING, text)) == (text == "")
    with pytest.raises(ValueError):
        lean.LeanConcern(layer="raw", quote=text, reading=None, reason="Reason")
    if text:
        with pytest.raises(ValueError):
            lean.LeanConcern(layer="raw", quote="text", reading=text, reason="Reason")
    else:
        assert (
            lean.LeanConcern(layer="raw", quote="text", reading=text, reason="Reason").reading == ""
        )


def test_actual_loader_authority_budget_and_old_slot_separation():
    spec = _spec()
    measurement._verify_approval(Path("."), spec)
    assert load_scoped_inputs(Path("."), spec)[1].body_sha256 == scoped.WHOLE_BODY_SHA
    assert scoped.window(spec) == "D1W"
    slots = {scoped.package(spec.model_copy(update={"contract": p})) for p in scoped.WHOLE_PROFILES}
    assert len(slots) == 3 and all(p.parent != scoped.LEAN_PACKAGE for p in slots)
    assert measurement._timeout_seconds(spec) == 300
    assert measurement._prep_seconds(spec) == 90
    with pytest.raises(ValueError):
        measurement._verify_approval(
            Path("."), spec.model_copy(update={"body_sha256": scoped.LEAN_BODY_SHA})
        )


def test_new_wire_export_validates_source_and_refuses_forged_actual_provenance(monkeypatch):
    host, projection, _ = whole.load_whole_inputs(Path("."))
    packet = dict(window_id="D1W", host=host, body_utf8=projection.body_utf8)
    monkeypatch.setattr(measurement, "REPOSITORY", Path("."))
    result = measurement._export(packet, {"output_text": "{"}, 1)
    assert result["outcome"] == "invalid"
    assert result["actual_provider_request_sha256"] == scoped.WHOLE_BODY_SHA
    reply = HELPERS["_reply"]()
    reply["targets"][3]["concerns"] = [HELPERS["_concern"]()]
    result = measurement._export(packet, {"output_text": json.dumps(reply)}, 1)
    assert result["outcome"]["proposal_status"] == "findings"
    packet["body_utf8"] = lean.load_lean_inputs(Path("."))[1].body_utf8
    with pytest.raises(ValueError, match="exact actual request"):
        measurement._export(packet, {}, 1)


def test_new_profile_preserves_safe_length_observation_and_receipt_integrity(tmp_path, monkeypatch):
    monkeypatch.setitem(
        HELPERS["test_previous_slot_guard_only_relaxes_length_for_new_lean_profiles"].__globals__,
        "_spec",
        _spec,
    )
    HELPERS["test_previous_slot_guard_only_relaxes_length_for_new_lean_profiles"](
        tmp_path, monkeypatch, True
    )
