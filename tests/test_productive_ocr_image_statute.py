"""Image-only scope, uncertainty and actual-wire provenance without accuracy claims."""

import copy
import json
import runpy
from functools import partial
from pathlib import Path

import pytest

from congressional_globe import productive_ocr_image_statute as image
from congressional_globe import productive_ocr_measurement as measurement
from congressional_globe import productive_ocr_measurement_scoped as scoped
from congressional_globe.productive_ocr_measurement_inputs import (
    load_audit_inputs,
    load_scoped_inputs,
)

HELPERS = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_lean_audit.py")))


def _spec():
    return HELPERS["_spec"]().model_copy(
        update=dict(
            contract=scoped.IMAGE_PROFILES[0],
            approval_sha256=scoped.IMAGE_APPROVAL_SHA,
            body_sha256=scoped.IMAGE_BODY_SHA,
        )
    )


def _reply(**changes):
    return (
        dict(
            contract="ocr-image-statute-reply-v1",
            unit_id="D2P8",
            paragraph_alias="P8",
            coverage="complete",
            reading="Fictional software fixture.",
            reason=None,
        )
        | changes
    )


@pytest.fixture(scope="module")
def inputs():
    return image.load_image_inputs(Path("."))


def test_image_only_wire_retains_source_image_and_options_but_sends_no_ocr(inputs):
    host, projection, _ = inputs
    old_host, old, _ = load_audit_inputs(Path("."), "D2")
    assert host == old_host
    before, after = json.loads(old.body_utf8), json.loads(projection.body_utf8)
    image._same_request_metadata(before, after)
    user = json.loads(after["messages"][1]["content"])
    assert set(user) == {
        "unit_id",
        "paragraph_alias",
        "image_alias",
        "image_width",
        "image_height",
        "target_rectangle",
        "coordinate_system",
    }
    assert user["target_rectangle"] == dict(left=20, top=457, right=522, bottom=584)
    assert (user["image_width"], user["image_height"]) == (1600, 876)
    messages = json.dumps([m["content"] for m in after["messages"]])
    assert "it further enacted" not in messages and "that act" not in messages
    assert "saved_proposal" not in user and "targets" not in user
    assert projection.body_sha256 == scoped.IMAGE_BODY_SHA
    assert len(image._targets(host, "audit_saved_proposal")) == 9


def _altered_scope(repo, unit, original, field):
    host, projection, registry = original(repo, unit)
    host = copy.deepcopy(host)
    if field == "region":
        binding = next(
            b for b in host["payload"]["image"]["bindings"] if b["paragraph_alias"] == "P8"
        )
        binding["crop_region"]["top"] += 1
    else:
        image._targets(host, "audit_saved_proposal")["P8"]["raw"]["sha256"] = "0" * 64
    return host, projection, registry


@pytest.mark.parametrize("field", ["region", "source"])
def test_original_target_scope_cannot_shift(monkeypatch, field):
    loader = partial(_altered_scope, original=image.load_audit_inputs, field=field)
    monkeypatch.setattr(image, "load_audit_inputs", loader)
    with pytest.raises(ValueError, match="registered scope"):
        image.load_image_inputs(Path("."))


@pytest.mark.parametrize(
    "changes",
    [
        dict(reading=None),
        dict(reason="not null"),
        dict(reading=" \n"),
        dict(coverage="partial"),
        dict(coverage="unreadable", reason="Cannot read"),
        dict(paragraph_alias="P7"),
        dict(unit_id="D2"),
        dict(extra=True),
    ],
)
def test_invalid_shape_uncertainty_or_foreign_target_rejected(changes):
    with pytest.raises(ValueError):
        image.ImageStatuteReply.model_validate(_reply(**changes))


@pytest.mark.parametrize(
    "changes",
    [
        dict(coverage="partial", reason="Incomplete crop", reading="Visible fixture fragment."),
        dict(coverage="partial", reason="Uncertain", reading=None),
        dict(coverage="unreadable", reason="Cannot read", reading=None),
    ],
)
def test_partial_unreadable_results_remain_explicit_unresolved(inputs, changes):
    packet = dict(window_id="D2I", host=inputs[0], body_utf8=inputs[1].body_utf8)
    result = image.export_image_reply(
        Path("."), packet, {"output_text": json.dumps(_reply(**changes))}, 1
    )
    assert result["outcome"]["proposal_status"] == "unresolved"
    assert "accuracy" in result["validation_scope"]


def test_actual_profile_loader_export_and_foreign_wire_guard(inputs, monkeypatch):
    spec = _spec()
    measurement._verify_approval(Path("."), spec)
    assert scoped.window(spec) == "D2I"
    assert load_scoped_inputs(Path("."), spec)[1].body_sha256 == scoped.IMAGE_BODY_SHA
    assert measurement._timeout_seconds(spec) == 300 and measurement._prep_seconds(spec) == 90
    assert (
        len(
            {scoped.package(spec.model_copy(update={"contract": p})) for p in scoped.IMAGE_PROFILES}
        )
        == 3
    )
    assert scoped.package(spec).parent != scoped.APPENDIX_PACKAGE
    monkeypatch.setattr(measurement, "REPOSITORY", Path("."))
    packet = dict(window_id="D2I", host=inputs[0], body_utf8=inputs[1].body_utf8)
    result = measurement._export(packet, {"output_text": json.dumps(_reply())}, 1)
    assert result["outcome"]["proposal_status"] == "transcription"
    assert result["selected_raw_sha256"] == image.SOURCE_SHA
    assert result["actual_provider_request_sha256"] == scoped.IMAGE_BODY_SHA
    assert "unverified AI claims" in result["validation_scope"]
    assert result["selected_source_id"].endswith("par_000741_000007")
    assert measurement._export(packet, {"output_text": "{"}, 1)["outcome"] == "invalid"
    packet["body_utf8"] = load_audit_inputs(Path("."), "D2")[1].body_utf8
    with pytest.raises(ValueError):
        measurement._export(packet, {}, 1)


def test_duplicate_json_keys_rejected(inputs):
    packet = dict(window_id="D2I", host=inputs[0], body_utf8=inputs[1].body_utf8)
    assert (
        image.export_image_reply(
            Path("."), packet, {"output_text": '{"coverage":"complete","coverage":"partial"}'}, 1
        )["outcome"]
        == "invalid"
    )


def test_safe_length_continuation_retains_receipt_and_resource_checks(tmp_path, monkeypatch):
    monkeypatch.setitem(
        HELPERS["test_previous_slot_guard_only_relaxes_length_for_new_lean_profiles"].__globals__,
        "_spec",
        _spec,
    )
    HELPERS["test_previous_slot_guard_only_relaxes_length_for_new_lean_profiles"](
        tmp_path, monkeypatch, True
    )
