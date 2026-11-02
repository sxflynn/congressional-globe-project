"""Exact appendix source obligations and prospective measurement boundaries."""

import copy
import json
import runpy
from pathlib import Path

import pytest

from congressional_globe import productive_ocr_appendix_audit as appendix
from congressional_globe import productive_ocr_lean_audit as lean
from congressional_globe import productive_ocr_measurement as measurement
from congressional_globe import productive_ocr_measurement_scoped as scoped
from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
from congressional_globe.productive_ocr_measurement_inputs import (
    load_audit_inputs,
    load_scoped_inputs,
)

HELPERS = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_lean_audit.py")))


def _spec():
    return HELPERS["_spec"]().model_copy(
        update=dict(
            contract=scoped.APPENDIX_PROFILES[0],
            approval_sha256=scoped.APPENDIX_APPROVAL_SHA,
            body_sha256=scoped.APPENDIX_BODY_SHA,
        )
    )


@pytest.fixture(scope="module")
def inputs():
    return appendix.load_appendix_inputs(Path("."))


def _reply():
    return dict(
        contract=lean.REPLY_CONTRACT,
        unit_id="D2",
        targets=[
            dict(paragraph_alias=f"P{i}", coverage="complete", reason=None, concerns=[])
            for i in range(1, 10)
        ],
    )


def test_all_original_nine_targets_roundtrip_without_new_evidence_or_option_changes(inputs):
    host, projection, _ = inputs
    original_host, original, _ = load_audit_inputs(Path("."), "D2")
    assert host == original_host
    before, after = json.loads(original.body_utf8), json.loads(projection.body_utf8)
    source = before["messages"][1]["content"]
    compact = json.loads(after["messages"][1]["content"])
    assert compact.pop("reply_contract") == lean.REPLY_CONTRACT
    compact["reply_contract"] = "ocr-productive-repair-reply-v2"
    assert (
        appendix.decode_provider(
            canonical_json(compact).decode(), source, appendix.ORIGINAL_PROVIDER_SHA
        )
        == source
    )
    assert sha256_bytes(source.encode()) == appendix.ORIGINAL_PROVIDER_SHA
    lean._same_request_metadata(before, after)
    assert after["format"]["properties"]["targets"]["minItems"] == 9
    assert after["format"]["properties"]["targets"]["maxItems"] == 9
    assert after["messages"][0]["content"].startswith(lean.PROMPT)
    assert projection.body_sha256 == scoped.APPENDIX_BODY_SHA
    assert projection.body_sha256 != scoped.D2_BODY_SHA


def test_repetition_restoration_binds_saved_and_raw_source_without_accepting_history(inputs):
    reply = _reply()
    reply["targets"][6]["concerns"] = [
        dict(
            layer="saved_proposal",
            quote="I must admit that act is quite full.",
            reading="I must admit that that act is quite full.",
            reason="Authored test of source-bound repetition restoration.",
        )
    ]
    result = lean.validate_reply(json.dumps(reply), inputs[0])
    binding = result["source_bindings"]["P7"][0]
    assert binding["raw_support"].endswith("I must admit that that act is quite full.")
    raw = lean._targets(inputs[0], "audit_saved_proposal")["P7"]["raw"]["text"]
    assert raw[binding["raw_start"] : binding["raw_end"]] == binding["raw_support"]
    # A frozen older multi-change patch can conservatively widen inverse support.
    assert binding["quote"] == "I must admit that act is quite full."
    assert result["proposal_status"] == "findings"
    assert "unverified" in binding["quality"]


@pytest.mark.parametrize("mutation", ["drop", "duplicate", "foreign_unit"])
def test_original_target_scope_rejected(inputs, mutation):
    reply = _reply()
    if mutation == "drop":
        reply["targets"].pop()
    elif mutation == "duplicate":
        reply["targets"][8] = copy.deepcopy(reply["targets"][0])
    else:
        reply["unit_id"] = "D1"
    with pytest.raises(ValueError):
        lean.validate_reply(json.dumps(reply), inputs[0])


@pytest.mark.parametrize("quote", ["not a source quote", "July 17, 18G2"])
def test_foreign_quote_and_wrong_layer_claims_rejected(inputs, quote):
    reply = _reply()
    reply["targets"][6]["concerns"] = [
        dict(
            layer="saved_proposal",
            quote=quote,
            reading="July 17, 1862",
            reason="Authored invalid test.",
        )
    ]
    with pytest.raises(ValueError):
        lean.validate_reply(json.dumps(reply), inputs[0])


@pytest.mark.parametrize("field", ["reply_contract", "unit_id"])
def test_compact_source_metadata_cannot_be_silently_changed(inputs, field):
    body = json.loads(inputs[1].body_utf8)
    user = json.loads(body["messages"][1]["content"])
    original = copy.deepcopy(user)
    original["reply_contract"] = "ocr-productive-repair-reply-v2"
    user[field] = "changed"
    body["messages"][1]["content"] = json.dumps(user)
    with pytest.raises(ValueError):
        appendix._verify_compact_source(body, json.dumps(original))


def test_foreign_original_and_changed_decoder_are_refused(monkeypatch):
    real_loader = appendix.load_audit_inputs
    monkeypatch.setattr(appendix, "load_audit_inputs", lambda repo, _unit: real_loader(repo, "D1"))
    with pytest.raises(ValueError):
        appendix.load_appendix_inputs(Path("."))
    monkeypatch.setattr(appendix, "load_audit_inputs", real_loader)
    monkeypatch.setattr(appendix, "PROMPT_SHA", "0" * 64)
    with pytest.raises(ValueError, match="decoding prompt"):
        appendix.load_appendix_inputs(Path("."))


def test_exact_actual_dispatch_export_authority_and_separate_slots(inputs, monkeypatch):
    spec = _spec()
    measurement._verify_approval(Path("."), spec)
    assert load_scoped_inputs(Path("."), spec)[1].body_sha256 == scoped.APPENDIX_BODY_SHA
    assert scoped.window(spec) == "D2W"
    assert measurement._timeout_seconds(spec) == 300 and measurement._prep_seconds(spec) == 90
    assert (
        len(
            {
                scoped.package(spec.model_copy(update={"contract": p}))
                for p in scoped.APPENDIX_PROFILES
            }
        )
        == 3
    )
    assert scoped.package(spec).parent not in {scoped.WHOLE_PACKAGE, scoped.D2_PACKAGE}
    monkeypatch.setattr(measurement, "REPOSITORY", Path("."))
    packet = dict(window_id="D2W", host=inputs[0], body_utf8=inputs[1].body_utf8)
    result = measurement._export(packet, {"output_text": json.dumps(_reply())}, 1)
    assert result["outcome"]["proposal_status"] == "no_finding"
    assert result["actual_provider_request_sha256"] == scoped.APPENDIX_BODY_SHA
    assert result["response_schema_sha256"] == inputs[1].schema_sha256
    packet["window_id"] = "D1W"
    with pytest.raises(ValueError):
        measurement._export(packet, {}, 1)


def test_safe_length_continuation_retains_exact_previous_receipt_guard(tmp_path, monkeypatch):
    monkeypatch.setitem(
        HELPERS["test_previous_slot_guard_only_relaxes_length_for_new_lean_profiles"].__globals__,
        "_spec",
        _spec,
    )
    HELPERS["test_previous_slot_guard_only_relaxes_length_for_new_lean_profiles"](
        tmp_path, monkeypatch, True
    )
