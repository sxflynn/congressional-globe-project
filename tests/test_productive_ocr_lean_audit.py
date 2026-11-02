"""All-target lean audit source fidelity boundaries and safe planned repetitions."""

import copy
import json
import re
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

from congressional_globe import productive_ocr_lean_audit as lean
from congressional_globe import productive_ocr_measurement as measurement
from congressional_globe import productive_ocr_measurement_scoped as scoped
from congressional_globe.productive_ocr_host import canonical_json
from congressional_globe.productive_ocr_measurement_inputs import load_audit_inputs

HELPERS = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_long_audit.py")))


@pytest.fixture(scope="module")
def inputs():
    return lean.load_lean_inputs(Path("."))


def _reply():
    return dict(
        contract=lean.REPLY_CONTRACT,
        unit_id="D1",
        targets=[
            dict(paragraph_alias=f"P{i}", coverage="complete", reason=None, concerns=[])
            for i in range(1, 5)
        ],
    )


def _concern(layer="saved_proposal", quote="CCCXLI", reading="CCCXI"):
    return dict(
        layer=layer, quote=quote, reading=reading, reason="Authored source-check fixture only."
    )


def test_real_wire_preserves_every_source_field_image_option_and_no_answer_leak(inputs):
    host, projection, _registry = inputs
    _old_host, original, _reg = load_audit_inputs(Path("."), "D1")
    actual = json.loads(projection.body_utf8)
    user = json.loads(actual["messages"][1]["content"])
    user["reply_contract"] = "ocr-productive-repair-reply-v2"
    restored = lean.decode_provider(
        canonical_json(user).decode(),
        json.loads(original.body_utf8)["messages"][1]["content"],
        lean.ORIGINAL_PROVIDER_SHA,
    )
    assert restored == json.loads(original.body_utf8)["messages"][1]["content"]
    assert len(host["payload"]["paragraphs"]) == 4
    assert projection.body_sha256 == scoped.LEAN_BODY_SHA
    assert actual["options"] == {"num_predict": 1500}
    assert (
        actual["messages"][1]["images"] == json.loads(original.body_utf8)["messages"][1]["images"]
    )
    assert not re.search(r"\bCCCXI\b", " ".join(m["content"] for m in actual["messages"]))
    assert actual["format"]["properties"]["targets"]["minItems"] == 4
    assert "not counts of words" in actual["messages"][0]["content"]


def test_saved_quote_maps_to_original_source_without_applying_a_repair(inputs):
    host, _projection, _registry = inputs
    reply = _reply()
    reply["targets"][3]["concerns"] = [_concern()]
    result = lean.validate_reply(json.dumps(reply), host)
    binding = result["source_bindings"]["P4"][0]
    assert result["proposal_status"] == "findings"
    assert binding["raw_support"] == "Chap. CCCXL — An Act to remove tte Office"
    assert binding["reading"] == "CCCXI"
    assert binding["source_id"].endswith("par_001060_000028")
    assert "patches" not in result and "derived_proposals" not in result


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r["targets"].pop(),
        lambda r: r["targets"].__setitem__(3, r["targets"][0]),
        lambda r: r["targets"][3].__setitem__("paragraph_alias", "P5"),
        lambda r: r.__setitem__("unit_id", "D2"),
        lambda r: r.__setitem__("patches", []),
    ],
    ids=["missing", "duplicate", "foreign", "unit", "extra"],
)
def test_bad_scope_is_rejected(inputs, mutate):
    reply = _reply()
    mutate(reply)
    with pytest.raises(ValueError):
        lean.validate_reply(json.dumps(reply), inputs[0])


def test_duplicate_json_is_rejected(inputs):
    raw = json.dumps(_reply()).replace('"unit_id": "D1"', '"unit_id": "D1", "unit_id": "D1"')
    with pytest.raises(ValueError):
        lean.validate_reply(raw, inputs[0])


@pytest.mark.parametrize("quote", ["not in the original", "2"])
def test_missing_or_ambiguous_source_quotes_are_refused(inputs, quote):
    reply = _reply()
    reply["targets"][3]["concerns"] = [_concern(quote=quote)]
    with pytest.raises(ValueError, match="exactly once"):
        lean.validate_reply(json.dumps(reply), inputs[0])


@pytest.mark.parametrize(
    "mode", ["null_complete", "partial_no_reason", "noop", "duplicate", "blank"]
)
def test_uncertainty_and_concern_coherence(inputs, mode):
    reply = _reply()
    record = reply["targets"][3]
    concern = _concern()
    record["concerns"] = [concern]
    if mode == "null_complete":
        concern["reading"] = None
    elif mode == "partial_no_reason":
        record["coverage"] = "partial"
    elif mode == "noop":
        concern["reading"] = concern["quote"]
    elif mode == "duplicate":
        record["concerns"].append(copy.deepcopy(concern))
    else:
        concern["reason"] = " "
    with pytest.raises(ValueError):
        lean.validate_reply(json.dumps(reply), inputs[0])


def test_partial_is_preserved_and_complete_no_finding_is_only_a_claim(inputs):
    reply = _reply()
    assert lean.validate_reply(json.dumps(reply), inputs[0])["proposal_status"] == "no_finding"
    record = reply["targets"][3]
    record.update(
        coverage="partial", reason="Cannot read this character.", concerns=[_concern(reading=None)]
    )
    assert lean.validate_reply(json.dumps(reply), inputs[0])["proposal_status"] == "unresolved"


def test_export_binds_actual_wire_and_preserves_invalid_reply(inputs):
    host, projection, _registry = inputs
    packet = dict(window_id="D1A", host=host, body_utf8=projection.body_utf8)
    result = lean.export_lean_reply(Path("."), packet, {"output_text": "{"}, 1)
    assert result["outcome"] == "invalid"
    assert result["raw_reply_text"] == "{"
    assert result["actual_provider_request_sha256"] == scoped.LEAN_BODY_SHA
    packet["window_id"] = "D1L"
    with pytest.raises(ValueError, match="exact actual request"):
        lean.export_lean_reply(Path("."), packet, {}, 1)


def _observed(**updates):
    result = dict(
        status="completed",
        finish_reason="length",
        owned_stop_observation="stopped",
        usage=dict(input_tokens=100, output_tokens=1500),
    )
    result.update(updates)
    return result


def test_only_prospective_guard_allows_safe_known_truncation():
    with pytest.raises(ValueError, match="incomplete"):
        scoped._verify_previous_result(_observed())
    scoped._verify_previous_result(_observed(), allow_length=True)
    scoped._verify_previous_result(
        _observed(finish_reason="stop", measurement_status="invalid"), allow_length=True
    )


@pytest.mark.parametrize(
    "updates",
    [
        dict(usage=None),
        dict(owned_stop_observation="unknown"),
        dict(status="failed"),
        dict(usage=dict(input_tokens=100, output_tokens=1501)),
    ],
)
def test_safe_repeat_flag_does_not_override_usage_stop_or_caps(updates):
    with pytest.raises(ValueError):
        scoped._verify_previous_result(_observed(**updates), allow_length=True)


def _spec():
    return HELPERS["_long_spec"]().model_copy(
        update=dict(
            contract=scoped.LEAN_PROFILES[0],
            approval_sha256=scoped.LEAN_APPROVAL_SHA,
            body_sha256=scoped.LEAN_BODY_SHA,
        )
    )


def test_lean_authority_window_separate_slots_and_lifecycle():
    spec = _spec()
    measurement._verify_approval(Path("."), spec)
    assert scoped.window(spec) == "D1A"
    slots = {scoped.package(spec.model_copy(update={"contract": p})) for p in scoped.LEAN_PROFILES}
    assert len(slots) == 3 and scoped.package(spec).parent != scoped.LONG_PACKAGE
    assert measurement._timeout_seconds(spec) == 300 and measurement._prep_seconds(spec) == 90


@pytest.mark.parametrize(
    "field", ["model", "options", "images", "source", "reply_contract", "extra"]
)
def test_wire_proof_refuses_evidence_and_unrelated_metadata_tampering(inputs, field):
    from congressional_globe.productive_ocr_compact_measurement import load_compact_inputs

    _host, before_projection, _reg = load_compact_inputs(Path("."))
    _host, source, _reg = load_audit_inputs(Path("."), "D1")
    original_provider = json.loads(source.body_utf8)["messages"][1]["content"]
    actual = json.loads(inputs[1].body_utf8)
    user = json.loads(actual["messages"][1]["content"])
    actions = {
        "model": lambda: actual.__setitem__("model", "other:model"),
        "options": lambda: actual.__setitem__("options", {"num_predict": 1501}),
        "images": lambda: actual["messages"][1].__setitem__("images", []),
        "source": lambda: user["paragraphs"][0].__setitem__("raw_text", "changed"),
        "reply_contract": lambda: user.__setitem__("reply_contract", "changed"),
        "extra": lambda: actual.__setitem__("keep_alive", -1),
    }
    actions[field]()
    actual["messages"][1]["content"] = canonical_json(user).decode()
    with pytest.raises(ValueError):
        lean._verify_source_preservation(
            before_projection.body_utf8, json.dumps(actual), original_provider
        )


@pytest.mark.parametrize("prospective", [True, False])
def test_previous_slot_guard_only_relaxes_length_for_new_lean_profiles(
    tmp_path, monkeypatch, prospective
):
    spec = _spec() if prospective else HELPERS["_long_spec"]()
    directory = tmp_path / "repeat-1"
    run = directory / "run"
    run.mkdir(parents=True)
    group_sha = "e" * 64
    packet = dict(window_id=scoped.window(spec), host={}, body_utf8="{}")
    saved = dict(spec=spec.model_dump(mode="json"), group_sha256=group_sha, max_output_tokens=1500)
    (directory / "spent-slot.json").write_text(json.dumps(saved))
    (run / "frozen.json").write_text(json.dumps(dict(config=saved, packet=packet)))
    result = _observed(output_text="partial")
    (run / "result.json").write_text(json.dumps(result))
    response = {k: result[k] for k in ("status", "finish_reason", "output_text", "usage")}
    receipt = SimpleNamespace(
        stop_observation="stopped", receipt_sha256="f" * 64, response=response
    )
    monkeypatch.setattr(scoped, "read_spool", lambda *_: receipt)
    _assert_previous_guard(directory, spec, group_sha, packet, prospective)
    response["output_text"] = "changed"
    with pytest.raises(ValueError):
        scoped._verify_previous(directory, spec, spec.contract, group_sha, packet)


def _assert_previous_guard(directory, spec, group_sha, packet, prospective):
    if prospective:
        assert (
            scoped._verify_previous(directory, spec, spec.contract, group_sha, packet) == "f" * 64
        )
    else:
        with pytest.raises(ValueError, match="incomplete"):
            scoped._verify_previous(directory, spec, spec.contract, group_sha, packet)


def test_lean_raw_receipt_recovery_cannot_count_as_a_second_observation(tmp_path, monkeypatch):
    helpers = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_measurement.py")))

    class Call:
        def result(self, timeout):
            assert timeout == 300
            return dict(
                status="completed",
                finish_reason="length",
                output_text="{",
                usage=dict(input_tokens=100, output_tokens=1500),
            )

        def observe(self):
            return "stopped"

    class Client:
        calls = 0

        def __init__(self, *_args, **_kwargs):
            pass

        def start(self, _body):
            type(self).calls += 1
            return Call()

    spec = helpers["_enable_synthetic_execute"](tmp_path, monkeypatch, Client)
    monkeypatch.setattr(scoped, "LEAN_PACKAGE", Path("lean"))
    monkeypatch.setattr(scoped, "verify_group", lambda *_: "e" * 64)
    spec = spec.model_copy(
        update=dict(
            contract=scoped.LEAN_PROFILES[0], body_sha256=scoped.LEAN_BODY_SHA, plan=_spec().plan
        )
    )
    projection = SimpleNamespace(body_sha256=scoped.LEAN_BODY_SHA, body_utf8="{}")
    monkeypatch.setattr(measurement, "_load_inputs", lambda *_: ({}, projection, None))

    def checkpoint(name):
        if name == "after_raw":
            raise RuntimeError("synthetic interrupted lean audit")

    with pytest.raises(RuntimeError, match="interrupted lean"):
        measurement.execute(tmp_path, spec, checkpoint)
    saved = SimpleNamespace(
        response=Call().result(300), elapsed_seconds=0.1, stop_observation="stopped"
    )
    monkeypatch.setattr(measurement, "_verify_recovery_authority", lambda *_: None)
    monkeypatch.setattr(measurement, "read_spool", lambda *_: saved)
    assert measurement.recover(tmp_path, spec)["measurement_status"] == "invalid"
    assert measurement.recover(tmp_path, spec)["dispatch"] == "disabled during recovery"
    assert Client.calls == 1


@pytest.mark.parametrize("field", ["reading", "reason", "target_reason"])
def test_whitespace_does_not_resolve_or_explain_a_concern(inputs, field):
    reply = _reply()
    record = reply["targets"][3]
    concern = _concern()
    record["concerns"] = [concern]
    if field == "target_reason":
        record.update(coverage="partial", reason=" ")
    else:
        concern[field] = " "
    with pytest.raises(ValueError):
        lean.validate_reply(json.dumps(reply), inputs[0])


def test_empty_reading_is_an_explicit_unreviewed_deletion_not_unknown(inputs):
    reply = _reply()
    reply["targets"][3]["concerns"] = [_concern(reading="")]
    result = lean.validate_reply(json.dumps(reply), inputs[0])
    assert result["source_bindings"]["P4"][0]["reading"] == ""
    assert result["proposal_status"] == "findings"
    assert "explicitly proposes deleting" in lean.PROMPT
