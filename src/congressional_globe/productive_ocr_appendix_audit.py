"""All nine original appendix targets in a lossless, lean whole-string audit."""

import copy
import json

from congressional_globe.productive_ocr_compact import decode_provider, encode_provider
from congressional_globe.productive_ocr_compact_measurement import PROMPT_SHA
from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
from congressional_globe.productive_ocr_lean_audit import (
    PROMPT,
    REPLY_CONTRACT,
    _same_request_metadata,
    export_bound_reply,
    reply_schema,
)
from congressional_globe.productive_ocr_measurement_inputs import load_audit_inputs
from congressional_globe.productive_ocr_whole_audit import apply_whole_patterns

ORIGINAL_PROVIDER_SHA = "4f228541a09792ed3ad1e16d1f850feb82bb3caff10cfb6e8f23998d9f8bdf0b"


def load_appendix_inputs(repository):
    host, original, registry = load_audit_inputs(repository, "D2")
    before = json.loads(original.body_utf8)
    provider = before["messages"][1]["content"]
    compact = encode_provider(provider, ORIGINAL_PROVIDER_SHA)
    if decode_provider(compact, provider, ORIGINAL_PROVIDER_SHA) != provider:
        raise ValueError("appendix source fails exact original restoration")
    prompt_path = "artifacts/study-capacity-screen-20261029-01/D2/proposed-prompt-v3.txt"
    decoding = (repository / prompt_path).read_text()
    if sha256_bytes(decoding.encode()) != PROMPT_SHA:
        raise ValueError("appendix decoding prompt changed")
    body = copy.deepcopy(before)
    user = json.loads(compact)
    user["reply_contract"] = REPLY_CONTRACT
    body["messages"][1]["content"] = canonical_json(user).decode()
    body["messages"][0]["content"] = (
        PROMPT + "\nInput v3 proposal:" + decoding.split("\nInput v3 proposal:", 1)[1]
    )
    body["format"] = reply_schema(host)
    apply_whole_patterns(body["format"])
    _same_request_metadata(before, body)
    _verify_compact_source(body, compact)
    wire = canonical_json(body).decode()
    projection = original.model_copy(
        update=dict(
            body_utf8=wire,
            body_sha256=sha256_bytes(wire.encode()),
            prompt_sha256=sha256_bytes(body["messages"][0]["content"].encode()),
            schema_sha256=sha256_bytes(canonical_json(body["format"])),
        )
    )
    return host, projection, registry


def _verify_compact_source(body, original_compact):
    user = json.loads(body["messages"][1]["content"])
    if user["reply_contract"] != REPLY_CONTRACT:
        raise ValueError("appendix reply contract changed")
    user["reply_contract"] = "ocr-productive-repair-reply-v2"
    if user != json.loads(original_compact):
        raise ValueError("appendix lean projection changed compact source content")


def export_appendix_reply(repository, packet, response, _elapsed):
    host, projection, _registry = load_appendix_inputs(repository)
    if packet != {"window_id": "D2W", "host": host, "body_utf8": projection.body_utf8}:
        raise ValueError("appendix export does not bind the exact actual request")
    return export_bound_reply(host, projection, response)
