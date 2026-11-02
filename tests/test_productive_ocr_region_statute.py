"""Exact source pixels, isolated input delta and actual crop/source provenance."""

import copy
import io
import json
import runpy
from pathlib import Path

import pytest
from PIL import Image

from congressional_globe import productive_ocr_image_statute as image
from congressional_globe import productive_ocr_measurement as measurement
from congressional_globe import productive_ocr_measurement_scoped as scoped
from congressional_globe import productive_ocr_region_statute as region
from congressional_globe.productive_ocr_measurement_inputs import load_scoped_inputs

HELPERS = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_lean_audit.py")))


def _spec():
    return HELPERS["_spec"]().model_copy(
        update=dict(
            contract=scoped.REGION_PROFILES[0],
            approval_sha256=scoped.REGION_APPROVAL_SHA,
            body_sha256=scoped.REGION_BODY_SHA,
        )
    )


def _reference_pixels(parent):
    return bytes(
        channel
        for y in range(457, 584)
        for x in range(20, 522)
        for channel in parent.getpixel((x, y))
    )


def test_every_derived_pixel_matches_parent_at_independently_indexed_coordinates():
    host, original, _ = image.load_image_inputs(Path("."))
    parent_bytes = image.provider_image_bytes(original)
    payload = region.crop_bytes(parent_bytes)
    with Image.open(io.BytesIO(parent_bytes)) as parent, Image.open(io.BytesIO(payload)) as crop:
        assert parent.mode == crop.mode == "RGB"
        assert crop.size == (502, 127)
        assert crop.tobytes() == _reference_pixels(parent)
    assert region.sha256_bytes(payload) == region.CROP_SHA
    assert payload == (scoped.REGION_PACKAGE / "crop.png").read_bytes()
    assert region.sha256_bytes(parent_bytes) == host["payload"]["image"]["sha256"]
    assert original.body_sha256 == scoped.IMAGE_BODY_SHA


def test_only_image_dimensions_and_rectangle_change_with_same_prompt_schema_source():
    old_host, old, _ = image.load_image_inputs(Path("."))
    host, projection, _ = region.load_region_inputs(Path("."))
    assert host == old_host
    before, after = json.loads(old.body_utf8), json.loads(projection.body_utf8)
    user = json.loads(after["messages"][1]["content"])
    assert user["target_rectangle"] == dict(left=0, top=0, right=502, bottom=127)
    assert (user["image_width"], user["image_height"]) == (502, 127)
    normalized = copy.deepcopy(after)
    normalized["messages"][1]["images"] = before["messages"][1]["images"]
    normalized["messages"][1]["content"] = before["messages"][1]["content"]
    assert normalized == before
    assert (
        projection.prompt_sha256 == old.prompt_sha256
        and projection.schema_sha256 == old.schema_sha256
    )
    assert projection.body_sha256 == scoped.REGION_BODY_SHA != scoped.IMAGE_BODY_SHA
    assert region.sha256_bytes(image.provider_image_bytes(projection)) == region.CROP_SHA


def test_tampered_crop_hash_refused(monkeypatch):
    monkeypatch.setattr(region, "CROP_SHA", "0" * 64)
    with pytest.raises(ValueError, match="frozen diagnostic"):
        region.load_region_inputs(Path("."))


def test_parent_identity_refused_before_derivation(monkeypatch):
    original = region.load_image_inputs

    def altered(repo):
        host, projection, registry = original(repo)
        host = copy.deepcopy(host)
        host["payload"]["image"]["sha256"] = "0" * 64
        return host, projection, registry

    monkeypatch.setattr(region, "load_image_inputs", altered)
    with pytest.raises(ValueError, match="registered source"):
        region.load_region_inputs(Path("."))


def test_unregistered_dimensions_refused():
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1)).save(buffer, format="PNG")
    with pytest.raises(ValueError, match="dimensions"):
        region.crop_bytes(buffer.getvalue())


def test_profile_source_export_binds_parent_crop_actual_wire_and_original_region(monkeypatch):
    spec = _spec()
    measurement._verify_approval(Path("."), spec)
    host, projection, _ = load_scoped_inputs(Path("."), spec)
    assert scoped.window(spec) == "D2R"
    assert projection.body_sha256 == scoped.REGION_BODY_SHA
    assert measurement._timeout_seconds(spec) == 300 and measurement._prep_seconds(spec) == 90
    assert (
        len(
            {
                scoped.package(spec.model_copy(update={"contract": p}))
                for p in scoped.REGION_PROFILES
            }
        )
        == 3
    )
    assert scoped.package(spec).parent != scoped.IMAGE_PACKAGE
    monkeypatch.setattr(measurement, "REPOSITORY", Path("."))
    packet = dict(window_id="D2R", host=host, body_utf8=projection.body_utf8)
    reply = dict(
        contract="ocr-image-statute-reply-v1",
        unit_id="D2P8",
        paragraph_alias="P8",
        coverage="complete",
        reading="Fictional test fixture.",
        reason=None,
    )
    result = measurement._export(packet, {"output_text": json.dumps(reply)}, 1)
    assert result["actual_provider_image_sha256"] == region.CROP_SHA != result["image_sha256"]
    assert result["actual_provider_request_sha256"] == scoped.REGION_BODY_SHA
    assert result["selected_image_region"] == image.REGION
    assert result["image_derivation"]["parent_image_sha256"] == host["payload"]["image"]["sha256"]
    assert result["image_derivation"]["size"] == [502, 127]
    assert "unverified AI claims" in result["validation_scope"]
    packet["body_utf8"] = image.load_image_inputs(Path("."))[1].body_utf8
    with pytest.raises(ValueError):
        measurement._export(packet, {}, 1)


def test_safe_length_observation_still_bound_to_receipt_and_budget(tmp_path, monkeypatch):
    monkeypatch.setitem(
        HELPERS["test_previous_slot_guard_only_relaxes_length_for_new_lean_profiles"].__globals__,
        "_spec",
        _spec,
    )
    HELPERS["test_previous_slot_guard_only_relaxes_length_for_new_lean_profiles"](
        tmp_path, monkeypatch, True
    )
