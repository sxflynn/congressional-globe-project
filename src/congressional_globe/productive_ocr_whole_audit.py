"""Versioned whole-string schema patterns; original lean host semantics unchanged."""

import json

from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
from congressional_globe.productive_ocr_lean_audit import export_bound_reply, load_lean_inputs

NONBLANK = r"^\s*\S[\s\S]*$"
READING = r"^(\s*\S[\s\S]*)?$"


def load_whole_inputs(repository):
    host, original, registry = load_lean_inputs(repository)
    body = json.loads(original.body_utf8)
    definitions = body["format"]["$defs"]
    concern = definitions["LeanConcern"]["properties"]
    concern["quote"]["pattern"] = NONBLANK
    concern["reason"]["pattern"] = NONBLANK
    concern["reading"]["anyOf"][0]["pattern"] = READING
    definitions["LeanTarget"]["properties"]["reason"]["anyOf"][0]["pattern"] = NONBLANK
    wire = canonical_json(body).decode()
    projection = original.model_copy(
        update=dict(
            body_utf8=wire,
            body_sha256=sha256_bytes(wire.encode()),
            schema_sha256=sha256_bytes(canonical_json(body["format"])),
        )
    )
    return host, projection, registry


def export_whole_reply(repository, packet, response, _elapsed):
    host, projection, _registry = load_whole_inputs(repository)
    if packet != {"window_id": "D1W", "host": host, "body_utf8": projection.body_utf8}:
        raise ValueError("whole-string export does not bind the exact actual request")
    return export_bound_reply(host, projection, response)
