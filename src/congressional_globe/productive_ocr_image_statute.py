"""Explicit one-paragraph image-only diagnostic, separate from full appendix audits."""

import base64
import copy
import json
from typing import Literal

from pydantic import Field, model_validator

from congressional_globe.bracket_cues import Contract
from congressional_globe.productive_ocr_compact import _parse
from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
from congressional_globe.productive_ocr_image_projection import make_image_projection
from congressional_globe.productive_ocr_lean_audit import _same_request_metadata, _targets
from congressional_globe.productive_ocr_measurement_inputs import load_audit_inputs
from congressional_globe.productive_ocr_whole_audit import NONBLANK

SOURCE_SHA = "b4f4cd8ccce9ffb5f813c7435c7ff3cff6b6056c74c42378c418b40a9e01821b"
REGION = dict(left=20, top=457, right=522, bottom=584)
PROMPT = (
    "Transcribe only the indented quoted statute paragraph in the left column, "
    "inside the supplied target rectangle of image I1. No OCR or older transcription "
    "is supplied. Inspect every word, name, number, repetition and punctuation mark. "
    "Return the complete paragraph, including its quotation marks, in reading. "
    "Join only clear word wraps at printed line ends; preserve genuine hyphens. "
    "Do not add text from neighboring paragraphs or columns. Do not silently repair "
    "unusual printed words or repetitions for fluency. Use the declared JSON. "
    "For complete coverage, reading contains the full paragraph and reason is null. "
    "For partial coverage, reading may contain visible text or null, and reason explains "
    "the limitation. For unreadable coverage, reading is null and reason explains why. "
    "Never claim complete coverage when part of the paragraph is unreadable. "
    "This is unreviewed image-only evidence, not accepted historical text."
)


class ImageStatuteReply(Contract):
    contract: Literal["ocr-image-statute-reply-v1"]
    unit_id: Literal["D2P8"]
    paragraph_alias: Literal["P8"]
    coverage: Literal["complete", "partial", "unreadable"]
    reading: str | None = Field(min_length=1, max_length=6000, pattern=NONBLANK)
    reason: str | None = Field(min_length=1, max_length=240, pattern=NONBLANK)

    @model_validator(mode="after")
    def coherent(self):
        if (self.reason is None) != (self.coverage == "complete"):
            raise ValueError("complete needs null reason; incomplete needs nonblank reason")
        missing = {"complete": False, "unreadable": True}.get(self.coverage)
        if missing is not None and (self.reading is None) != missing:
            raise ValueError("reading availability contradicts coverage")
        return self


def load_image_inputs(repository):
    host, original, registry = load_audit_inputs(repository, "D2")
    bindings = host["payload"]["image"]["bindings"]
    binding = [b for b in bindings if b["paragraph_alias"] == "P8"]
    target = _targets(host, "audit_saved_proposal")["P8"]
    expected = dict(
        paragraph_alias="P8", raw_sha256=SOURCE_SHA, raw_start=0, raw_end=356, crop_region=REGION
    )
    if binding != [expected] or target["raw"]["sha256"] != SOURCE_SHA:
        raise ValueError("image-only paragraph differs from original registered scope")
    before = json.loads(original.body_utf8)
    body = copy.deepcopy(before)
    body["messages"][0]["content"] = PROMPT
    body["messages"][1]["content"] = canonical_json(
        dict(
            unit_id="D2P8",
            paragraph_alias="P8",
            image_alias="I1",
            image_width=1600,
            image_height=876,
            target_rectangle=REGION,
            coordinate_system=(
                "pixels in the supplied image; left/top inclusive, right/bottom exclusive"
            ),
        )
    ).decode()
    body["format"] = ImageStatuteReply.model_json_schema()
    _same_request_metadata(before, body)
    wire = canonical_json(body).decode()
    return host, make_image_projection(original, wire), registry


def export_image_reply(repository, packet, response, _elapsed):
    host, projection, _registry = load_image_inputs(repository)
    if packet != {"window_id": "D2I", "host": host, "body_utf8": projection.body_utf8}:
        raise ValueError("image-only export does not bind exact target and actual request")
    return export_bound_image_reply(host, projection, response)


def provider_image_bytes(projection):
    body = json.loads(projection.body_utf8)
    return base64.b64decode(body["messages"][1]["images"][0], validate=True)


def export_bound_image_reply(host, projection, response):
    raw = response.get("output_text", "")
    try:
        reply = ImageStatuteReply.model_validate(_parse(raw))
    except (ValueError, KeyError, TypeError) as error:
        outcome, rejection = "invalid", str(error)[:1000]
    else:
        status = "transcription" if reply.coverage == "complete" else "unresolved"
        outcome, rejection = (
            dict(proposal_status=status, provider_reply=reply.model_dump(mode="json")),
            None,
        )
    return dict(
        outcome=outcome,
        rejection_reason=rejection,
        actual_provider_request_sha256=projection.body_sha256,
        response_schema_sha256=projection.schema_sha256,
        source_context_host_sha256=host["packet_sha256"],
        selected_source_id=_targets(host, "audit_saved_proposal")["P8"]["source_id"],
        selected_raw_sha256=SOURCE_SHA,
        selected_image_region=REGION,
        image_sha256=host["payload"]["image"]["sha256"],
        actual_provider_image_sha256=sha256_bytes(provider_image_bytes(projection)),
        actual_media=projection.actual_media.model_dump(mode="json"),
        projection_contract=projection.contract,
        source_context_projection_sha256=sha256_bytes(
            canonical_json(projection.source_context.model_dump(mode="json"))
        ),
        raw_reply_sha256=sha256_bytes(raw.encode()),
        raw_reply_text=raw,
        validation_scope=(
            "Reply shape/uncertainty and original target/request identity only; "
            "image transcription accuracy and complete coverage remain unverified AI claims."
        ),
        acceptance="unreviewed_ai_evidence; no repair/production/native-fit acceptance",
    )
