"""Independently pinned actual-media metadata; historical source context is distinct."""

import json
from pathlib import Path

import pytest

from congressional_globe import productive_ocr_image_projection as types
from congressional_globe import productive_ocr_measurement_scoped as scoped
from congressional_globe.productive_ocr_host import canonical_json
from congressional_globe.productive_ocr_image_statute import load_image_inputs
from congressional_globe.productive_ocr_projection import RequestProjection
from congressional_globe.productive_ocr_region_statute import CROP_SHA, load_region_inputs


@pytest.fixture(scope="module", params=["full", "crop"])
def projection(request):
    return (load_image_inputs if request.param == "full" else load_region_inputs)(Path("."))[1]


def _validate(raw, projection):
    return types.validate_image_projection(
        json.dumps(raw), projection.source_context, projection.body_sha256
    )


def test_actual_media_is_descriptive_of_actual_body_and_original_context_stays_complete(projection):
    parsed = json.loads(projection.body_utf8)
    scope = json.loads(parsed["messages"][1]["content"])
    assert projection.actual_media.width == scope["image_width"]
    assert projection.actual_media.height == scope["image_height"]
    assert projection.actual_media.selected_region.model_dump() == scope["target_rectangle"]
    assert projection.actual_media.paragraph_alias == "P8"
    assert len(json.loads(projection.source_context.image_bindings_json)) == 9
    assert projection.source_context.body_sha256 == scoped.D2_BODY_SHA
    assert projection.body_sha256 in {scoped.IMAGE_BODY_SHA, scoped.REGION_BODY_SHA}
    assert _validate(projection.model_dump(mode="json"), projection) == projection
    assert not hasattr(projection, "image_sha256")
    with pytest.raises(ValueError):
        RequestProjection.model_validate(projection.model_dump(mode="json"))


@pytest.mark.parametrize("field", ["body_sha256", "prompt_sha256", "schema_sha256", "model_digest"])
def test_changed_actual_identity_rejected(projection, field):
    raw = projection.model_dump(mode="json")
    raw[field] = "0" * 64
    with pytest.raises(ValueError):
        _validate(raw, projection)


@pytest.mark.parametrize(
    "field", ["image_sha256", "width", "height", "paragraph_alias", "mime_type"]
)
def test_actual_media_fields_cannot_describe_parent_or_another_target(projection, field):
    raw = projection.model_dump(mode="json")
    changes = dict(
        image_sha256="0" * 64, width=1, height=1, paragraph_alias="P7", mime_type="image/gif"
    )
    raw["actual_media"][field] = changes[field]
    with pytest.raises(ValueError):
        _validate(raw, projection)


@pytest.mark.parametrize("field", ["left", "right", "top", "bottom"])
def test_wrong_actual_region_refused_even_if_still_within_image(projection, field):
    raw = projection.model_dump(mode="json")
    raw["actual_media"]["selected_region"][field] += 1
    with pytest.raises(ValueError):
        _validate(raw, projection)


def test_original_context_must_match_independently_held_reference(projection):
    raw = projection.model_dump(mode="json")
    raw["source_context"]["diagnostics_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="independently pinned"):
        _validate(raw, projection)


def test_coherently_changed_body_requires_new_independently_pinned_request(projection):
    body = json.loads(projection.body_utf8)
    body["messages"][0]["content"] += " Changed instruction."
    wire = canonical_json(body).decode()
    changed = types.make_image_projection(projection.source_context, wire)
    with pytest.raises(ValueError, match="independently pinned"):
        types.validate_image_projection(
            changed.model_dump_json(), projection.source_context, projection.body_sha256
        )


def test_crop_parent_hashes_and_regions_are_unambiguous():
    projection = load_region_inputs(Path("."))[1]
    assert projection.actual_media.image_sha256 == CROP_SHA
    assert projection.source_context.image_sha256 != CROP_SHA
    assert (projection.actual_media.width, projection.actual_media.height) == (502, 127)
    assert projection.actual_media.selected_region.model_dump() == dict(
        left=0, top=0, right=502, bottom=127
    )


@pytest.mark.parametrize("mutation", ["extra_image", "scope_width", "bad_image", "foreign_alias"])
def test_invalid_wire_media_refused_before_any_export(mutation):
    projection = load_region_inputs(Path("."))[1]
    body = json.loads(projection.body_utf8)
    message = body["messages"][1]
    scope = json.loads(message["content"])
    if mutation == "extra_image":
        message["images"].append(message["images"][0])
    elif mutation == "scope_width":
        scope["image_width"] += 1
    elif mutation == "bad_image":
        message["images"] = ["not-base64"]
    else:
        scope["paragraph_alias"] = "P7"
    message["content"] = canonical_json(scope).decode()
    with pytest.raises(ValueError):
        types.make_image_projection(projection.source_context, canonical_json(body).decode())


def test_all_six_historical_requests_get_new_metadata_without_changing_body_or_results():
    root = Path("artifacts/image-projection-reconciliation-20261102-01")
    for case, original, expected in [
        ("D2I", scoped.IMAGE_PACKAGE, scoped.IMAGE_BODY_SHA),
        ("D2R", scoped.REGION_PACKAGE, scoped.REGION_BODY_SHA),
    ]:
        for number in (1, 2, 3):
            p = root / f"{case}-repeat-{number}-projection.json"
            assert p.exists()
            record = types.ImageDiagnosticProjection.model_validate_json(p.read_text())
            assert record.body_sha256 == expected
            assert (
                record.body_utf8.encode()
                == (original / f"repeat-{number}/request.json").read_bytes()
            )
            assert (
                record.source_context.host_packet_sha256
                == json.loads((original / f"repeat-{number}/host.json").read_text())[
                    "packet_sha256"
                ]
            )
