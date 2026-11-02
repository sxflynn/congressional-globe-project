"""Fixed D1 diagnostic: lossless wire encoding, explicitly separate validation context."""

import json
from pathlib import Path

from congressional_globe.productive_ocr_compact import decode_provider, encode_provider
from congressional_globe.productive_ocr_export import export_reply
from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
from congressional_globe.productive_ocr_measurement_inputs import load_audit_inputs

ORIGINAL_PROVIDER_SHA = "52f30008deefa6289e9ff60fe6eddc3d6dfcce29ae38da4c6313c5619bc45ea2"
COMPACT_PROVIDER_SHA = "19381c10b916fe38edd28fca1940ff13151af131fe17b9a65688e3fd3fd7457e"
PROMPT_SHA = "e68852e6044c39cdf0bd453496fa24e132e83d83212bdd273bc7f03a8f684939"
BODY_SHA = "ef80f5feb637e041fc1f24a5f4947d533b4a91fa9fdadda3e14a82fc67ded3f4"


def _wire_request(repository, original):
    body = json.loads(original.body_utf8)
    original_user = body["messages"][1]["content"]
    compact = encode_provider(original_user, ORIGINAL_PROVIDER_SHA)
    if sha256_bytes(compact.encode()) != COMPACT_PROVIDER_SHA:
        raise ValueError("compact provider differs from the fixed lossless D1 proposal")
    if decode_provider(compact, original_user, ORIGINAL_PROVIDER_SHA) != original_user:
        raise ValueError("compact audit failed exact independent-original restoration")
    prompt = (
        repository / "artifacts/study-capacity-screen-20261029-01/D1/proposed-prompt-v3.txt"
    ).read_text()
    if sha256_bytes(prompt.encode()) != PROMPT_SHA:
        raise ValueError("compact decoding prompt changed")
    body["messages"][0]["content"] = prompt
    body["messages"][1]["content"] = compact
    return canonical_json(body).decode()


def load_compact_inputs(repository: Path):
    """Rebuild the original host first; only the fixed measurement uses these wire bytes."""
    host, original, registry = load_audit_inputs(repository, "D1")
    wire = _wire_request(repository, original)
    if sha256_bytes(wire.encode()) != BODY_SHA:
        raise ValueError("compact audit wire request changed")
    projection = original.model_copy(
        update=dict(body_utf8=wire, body_sha256=BODY_SHA, prompt_sha256=PROMPT_SHA)
    )
    return host, projection, registry


def export_compact_reply(repository, packet, response, elapsed):
    """Keep actual wire identity separate from original-shape semantic validation."""
    host, compact, _registry = load_compact_inputs(repository)
    if packet != {"window_id": "D1C", "host": host, "body_utf8": compact.body_utf8}:
        raise ValueError("compact export does not bind the fixed actual request")
    _same_host, original, _registry = load_audit_inputs(repository, "D1")
    validated = export_reply(
        host,
        original.body_utf8,
        response.get("output_text", ""),
        host["payload"]["model_digest"],
        host["payload"]["response_schema_sha256"],
        response.get("usage"),
        elapsed,
    ).model_dump(mode="json")
    return {
        "outcome": validated["outcome"],
        "actual_provider_request_sha256": compact.body_sha256,
        "original_validation_request_sha256": original.body_sha256,
        "original_provider_sha256": ORIGINAL_PROVIDER_SHA,
        "compact_provider_sha256": COMPACT_PROVIDER_SHA,
        "roundtrip": "exact independently held original restored before dispatch/export",
        "validation_scope": "original-shape source/reply checks; original request was not sent",
        "original_shape_validation": validated,
        "acceptance": "unreviewed_ai_evidence; no production adoption or native fit",
    }
