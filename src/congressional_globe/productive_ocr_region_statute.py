"""Lossless extraction of an already registered source region for a fixed diagnostic."""

import base64
import copy
import io
import json

from PIL import Image

from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
from congressional_globe.productive_ocr_image_statute import (
    REGION,
    export_bound_image_reply,
    load_image_inputs,
    provider_image_bytes,
)
from congressional_globe.productive_ocr_lean_audit import _same_request_metadata

CROP_SHA = "544897eaf03eb007da7020ee12d7240f2ae377fbc699ed1c18a7716705463ce1"
SIZE = (502, 127)


def crop_bytes(parent):
    """Copy only registered pixels; no resizing, interpolation or generative changes."""
    with Image.open(io.BytesIO(parent)) as source:
        if source.size != (1600, 876):
            raise ValueError("registered parent dimensions changed")
        bounds = (REGION["left"], REGION["top"], REGION["right"], REGION["bottom"])
        with source.crop(bounds) as crop:
            stream = io.BytesIO()
            crop.save(stream, format="PNG")
    return stream.getvalue()


def load_region_inputs(repository):
    host, original, registry = load_image_inputs(repository)
    parent = provider_image_bytes(original)
    if sha256_bytes(parent) != host["payload"]["image"]["sha256"]:
        raise ValueError("actual parent image differs from registered source")
    crop = crop_bytes(parent)
    if sha256_bytes(crop) != CROP_SHA:
        raise ValueError("pixel-exact region PNG differs from frozen diagnostic")
    before = json.loads(original.body_utf8)
    body = copy.deepcopy(before)
    body["messages"][1]["images"] = [base64.b64encode(crop).decode()]
    user = json.loads(body["messages"][1]["content"])
    user.update(
        image_width=SIZE[0],
        image_height=SIZE[1],
        target_rectangle=dict(left=0, top=0, right=SIZE[0], bottom=SIZE[1]),
    )
    body["messages"][1]["content"] = canonical_json(user).decode()
    normalized = copy.deepcopy(body)
    normalized["messages"][1]["images"] = before["messages"][1]["images"]
    _same_request_metadata(before, normalized)
    wire = canonical_json(body).decode()
    return (
        host,
        original.model_copy(update=dict(body_utf8=wire, body_sha256=sha256_bytes(wire.encode()))),
        registry,
    )


def export_region_reply(repository, packet, response, _elapsed):
    host, projection, _registry = load_region_inputs(repository)
    if packet != {"window_id": "D2R", "host": host, "body_utf8": projection.body_utf8}:
        raise ValueError("region export does not bind exact target and actual request")
    result = export_bound_image_reply(host, projection, response)
    result["image_derivation"] = dict(
        operation="lossless decoded-pixel crop; no resize/retouch",
        parent_image_sha256=host["payload"]["image"]["sha256"],
        original_region=REGION,
        size=list(SIZE),
        actual_png_sha256=CROP_SHA,
        source_scope="Same original P8text; full-image coordinate experiment preserved separately.",
        backend_transform="unknown; model may resize derived input internally",
    )
    return result
