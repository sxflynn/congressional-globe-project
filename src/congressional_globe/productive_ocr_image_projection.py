"""Actual diagnostic media explicitly separated from its trusted original context."""

import base64
import io
from typing import Literal

from PIL import Image
from pydantic import Field, model_validator

from congressional_globe.bracket_cues import Contract
from congressional_globe.productive_ocr_compact import _parse
from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
from congressional_globe.productive_ocr_projection import RequestProjection
from congressional_globe.scan_models import Sha256


class PixelBox(Contract):
    left: int = Field(ge=0, strict=True)
    top: int = Field(ge=0, strict=True)
    right: int = Field(gt=0, strict=True)
    bottom: int = Field(gt=0, strict=True)

    @model_validator(mode="after")
    def nonempty(self):
        if self.left >= self.right or self.top >= self.bottom:
            raise ValueError("selected pixel rectangle must be nonempty")
        return self


class ActualDiagnosticMedia(Contract):
    image_sha256: Sha256
    mime_type: Literal["image/jpeg", "image/png"]
    width: int = Field(gt=0, le=8192, strict=True)
    height: int = Field(gt=0, le=8192, strict=True)
    image_alias: Literal["I1"]
    paragraph_alias: Literal["P8"]
    selected_region: PixelBox

    @model_validator(mode="after")
    def within_image(self):
        if self.selected_region.right > self.width or self.selected_region.bottom > self.height:
            raise ValueError("selected region exceeds actual image dimensions")
        return self


def _media(body):
    try:
        message = body["messages"][1]
        scope = _parse(message["content"])
        if len(message["images"]) != 1:
            raise ValueError("image diagnostic requires exactly one actual image")
        raw = base64.b64decode(message["images"][0], validate=True)
        with Image.open(io.BytesIO(raw)) as image:
            if image.size != (scope["image_width"], scope["image_height"]):
                raise ValueError("actual image dimensions differ from request scope")
            mime = {"JPEG": "image/jpeg", "PNG": "image/png"}[image.format or ""]
        return ActualDiagnosticMedia.model_validate(
            dict(
                image_sha256=sha256_bytes(raw),
                mime_type=mime,
                width=scope["image_width"],
                height=scope["image_height"],
                image_alias=scope["image_alias"],
                paragraph_alias=scope["paragraph_alias"],
                selected_region=scope["target_rectangle"],
            )
        ).model_dump(mode="json")
    except (KeyError, TypeError, IndexError, OSError) as error:
        raise ValueError("invalid actual image diagnostic media/scope") from error


def _wire_fields(context, wire):
    body = _parse(wire)
    try:
        if body["model"] != context.model_name:
            raise ValueError("diagnostic model differs from trusted source context")
        return dict(
            body_utf8=wire,
            body_sha256=sha256_bytes(wire.encode()),
            schema_sha256=sha256_bytes(canonical_json(body["format"])),
            prompt_sha256=sha256_bytes(body["messages"][0]["content"].encode()),
            model_name=body["model"],
            model_digest=context.model_digest,
            actual_media=_media(body),
        )
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise ValueError("invalid diagnostic wire metadata") from error


class ImageDiagnosticProjection(Contract):
    contract: Literal["productive-ocr-image-diagnostic-projection-v1"] = (
        "productive-ocr-image-diagnostic-projection-v1"
    )
    source_context: RequestProjection
    body_utf8: str = Field(min_length=1, max_length=2 * 1024 * 1024)
    body_sha256: Sha256
    schema_sha256: Sha256
    prompt_sha256: Sha256
    model_name: str = Field(min_length=1)
    model_digest: Sha256
    actual_media: ActualDiagnosticMedia

    @model_validator(mode="after")
    def actual_wire_matches_metadata(self):
        actual = self.model_dump(mode="json", exclude={"contract", "source_context"})
        if actual != _wire_fields(self.source_context, self.body_utf8):
            raise ValueError("diagnostic actual-media/request metadata mismatch")
        return self


def make_image_projection(context: RequestProjection, wire: str) -> ImageDiagnosticProjection:
    return ImageDiagnosticProjection(source_context=context, **_wire_fields(context, wire))


def validate_image_projection(raw, context, expected_body_sha256):
    """Caller independently pins original context and exact authorized wire bytes."""
    projection = ImageDiagnosticProjection.model_validate_json(raw)
    if projection.source_context != context or projection.body_sha256 != expected_body_sha256:
        raise ValueError("image diagnostic differs from independently pinned context/body")
    return projection
