"""Explicit missing/unrelated-image controls without forged source bindings."""

from __future__ import annotations

import copy
import json
from typing import Literal

from congressional_globe.reading_contracts import ReadingCandidate, ReadingReply
from congressional_globe.reading_requests import ImageInput, digest, materialize_record, wire_bytes

ControlKind = Literal["missing_image", "unrelated_image"]


def make_control(record: dict, kind: ControlKind, unrelated: dict | None = None) -> dict:
    materialize_record(record)
    result = copy.deepcopy(record)
    content = json.loads(result["messages_without_image_payloads"][1]["content"])
    images = _control_images(record, kind, unrelated)
    content["images"] = [dict(id=image["id"], sources=image["sources"]) for image in images]
    result["images"] = images
    result["messages_without_image_payloads"][1]["content"] = wire_bytes(content).decode()
    result["control_kind"] = kind
    body = _body(result)
    result["request_sha256"] = digest(body)
    result["request_bytes"] = len(body)
    materialize_record(result)
    return result


def _control_images(record, kind, unrelated):
    if kind == "missing_image":
        return []
    if kind != "unrelated_image" or unrelated is None:
        raise ValueError("unrelated-image control requires an explicit source record")
    materialize_record(unrelated)
    if unrelated["unit_id"] == record["unit_id"]:
        raise ValueError("control image must come from a different source unit")
    _check_unrelated_sources(record, unrelated)
    return copy.deepcopy(unrelated["images"])


def _check_unrelated_sources(record, unrelated):
    content = json.loads(record["messages_without_image_payloads"][1]["content"])
    targets = {p["source_id"] for p in content["target"]}
    sources = {s["source_id"] for image in unrelated["images"] for s in image["sources"]}
    if not sources or targets.intersection(sources):
        raise ValueError("unrelated control source spans overlap targets or are empty")


def _body(record):
    messages = copy.deepcopy(record["messages_without_image_payloads"])
    messages[1]["images"] = [ImageInput.model_validate(i).payload() for i in record["images"]]
    return wire_bytes(
        dict(
            model=record["model"],
            messages=messages,
            format=record["format"],
            stream=record["stream"],
            think=record["think"],
            options=record["options"],
        )
    )


def control_passes(unit: ReadingCandidate, reply: ReadingReply) -> bool:
    """Every unsupported target must remain uncertain, without a proposed change."""
    if reply.unit_id != unit.id or reply.status != "needs_review" or reply.patches:
        return False
    actual = sorted((span.source_id, span.start, span.end) for span in reply.uncertain)
    expected = sorted((p.source_id, 0, len(p.raw)) for p in unit.target)
    return actual == expected
