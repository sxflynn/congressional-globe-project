"""Per-request productive OCR schema and exact multimodal request projection."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from typing import Literal

from pydantic import Field

from congressional_globe.bracket_cues import Contract
from congressional_globe.productive_ocr_host import (
    EvidenceRegistry,
    canonical_json,
    project_provider,
    sha256_bytes,
    validate_host,
)
from congressional_globe.productive_ocr_reply import Reply


class SchemaArtifact(Contract):
    contract: Literal[
        "productive-ocr-reply-schema-v1",
        "productive-ocr-reply-schema-v2",
        "productive-ocr-reply-schema-v3",
    ] = "productive-ocr-reply-schema-v1"
    unit_id: str = Field(min_length=1)
    role: Literal["productive_repair_and_self_check", "audit_saved_proposal"]
    target_aliases: tuple[str, ...] = Field(min_length=1, max_length=32)
    schema_text: str = Field(min_length=1)
    schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RequestProjection(Contract):
    contract: Literal["productive-ocr-request-projection-v1"] = (
        "productive-ocr-request-projection-v1"
    )
    host_packet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    body_utf8: str = Field(min_length=1, max_length=24 * 1024 * 1024)
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_name: str = Field(min_length=1)
    model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_layers_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    image_bindings_json: str = Field(min_length=2)
    image_bindings_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    diagnostics_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    saved_proposal_sha256: str | None = Field(pattern=r"^[0-9a-f]{64}$")


def _canonical_text(value: object) -> str:
    return canonical_json(value).decode("utf-8")


def _set_alias_enum(schema: dict, aliases: list[str]) -> None:
    definitions = schema["$defs"]
    for name in ("Inspection", "Anchor", "Patch", "TargetReading", "SelfCheck"):
        definitions[name]["properties"]["paragraph_alias"]["enum"] = aliases
    definitions["Finding"]["properties"]["anchor"]["$ref"] = "#/$defs/Anchor"


def _specialize_audit(schema: dict, role: str) -> None:
    if role != "audit_saved_proposal":
        return
    for key in ("target_readings", "patches"):
        schema["properties"][key]["maxItems"] = 0


def derive_reply_schema(host_payload: dict, *, conformance_v2: bool = False) -> SchemaArtifact:
    """Derive a frozen, per-unit schema without mutating the generic Reply schema."""
    payload = host_payload.get("payload", host_payload)
    targets = [
        paragraph["alias"] for paragraph in payload["paragraphs"] if paragraph["role"] == "target"
    ]
    aliases = tuple(targets)
    if not aliases or len(set(aliases)) != len(aliases):
        raise ValueError("schema needs unique declared target aliases")
    if payload.get("contract") == "ocr-productive-repair-host-input-v3":
        return _text_schema(payload, aliases, conformance_v2)
    schema = copy.deepcopy(Reply.model_json_schema())
    schema["properties"]["unit_id"] = {"const": payload["unit_id"]}
    schema["properties"]["role"] = {"const": payload["role"]}
    _set_alias_enum(schema, list(aliases))
    _specialize_audit(schema, payload["role"])
    _apply_conformance(schema, conformance_v2)
    schema_text = _canonical_text(schema)
    return SchemaArtifact(
        contract="productive-ocr-reply-schema-v2"
        if conformance_v2
        else "productive-ocr-reply-schema-v1",
        unit_id=payload["unit_id"],
        role=payload["role"],
        target_aliases=aliases,
        schema_text=schema_text,
        schema_sha256=sha256_bytes(schema_text.encode("utf-8")),
    )


def _text_schema(payload, aliases, conformance_v2):
    from congressional_globe.productive_ocr_text_reply import text_reply_schema

    if conformance_v2:
        raise ValueError("v2 conformance cannot select v3 mode")
    text = text_reply_schema(payload)
    return SchemaArtifact(
        contract="productive-ocr-reply-schema-v3",
        unit_id=payload["unit_id"],
        role=payload["role"],
        target_aliases=aliases,
        schema_text=text,
        schema_sha256=sha256_bytes(text.encode()),
    )


def source_layers_identity(payload: dict) -> str:
    saved = payload["saved_proposal"]
    saved_rows = (
        {}
        if saved is None
        else {
            item["paragraph_alias"]: {
                "sha256": item["sha256"],
                "raw_edits": item["raw_edits"],
            }
            for item in saved["paragraphs"]
        }
    )
    layers = [
        {
            "alias": row["alias"],
            "role": row["role"],
            "source_id": row["source_id"],
            "part_number": row["part_number"],
            "scan_leaf": row["scan_leaf"],
            "raw_sha256": row["raw"]["sha256"],
            "static_sha256": row["static"]["sha256"],
            "static_edits": row["static"]["edits"],
            "static_rule_sha256": row["static"]["rule_sha256"],
            "static_lexicon_sha256": row["static"]["lexicon_sha256"],
            "saved_proposal": saved_rows.get(row["alias"]),
        }
        for row in payload["paragraphs"]
    ]
    return sha256_bytes(canonical_json(layers))


def _input_identities(payload: dict) -> tuple[str, str, str | None]:
    diagnostics = sha256_bytes(canonical_json(payload["diagnostics"]))
    saved = payload["saved_proposal"]
    saved_hash = None if saved is None else sha256_bytes(canonical_json(saved))
    return source_layers_identity(payload), diagnostics, saved_hash


def compile_request_projection(
    host_envelope: dict,
    registry: EvidenceRegistry,
    prompt_text: str,
    model_name: str,
    output_tokens: int = 1500,
    *,
    conformance_v2: bool = False,
) -> tuple[RequestProjection, SchemaArtifact]:
    """Validate and freeze exact body bytes; fit evidence is a separate mandatory gate."""
    if not 1 <= output_tokens <= 1500:
        raise ValueError("output ceiling must be within the frozen 1500-token limit")
    host = validate_host(host_envelope, registry)
    payload = host["payload"]
    schema = derive_reply_schema(host, conformance_v2=conformance_v2)
    if payload["response_schema_sha256"] != schema.schema_sha256:
        raise ValueError("host packet does not bind the derived per-request reply schema")
    if hashlib.sha256(prompt_text.encode("utf-8")).hexdigest() != payload["prompt_sha256"]:
        raise ValueError("exact prompt bytes disagree with frozen host hash")
    image = payload["image"]
    image_bytes = registry.image_bytes[image["sha256"]]
    provider_projection = project_provider(host)
    body = {
        "model": model_name,
        "stream": False,
        "think": False,
        "messages": [
            {"role": "system", "content": prompt_text},
            {
                "role": "user",
                "content": _canonical_text(provider_projection),
                "images": [base64.b64encode(image_bytes).decode("ascii")],
            },
        ],
        "format": json.loads(schema.schema_text),
        "options": {"num_predict": output_tokens},
    }
    body_utf8 = _canonical_text(body)
    source_hash, diagnostics_hash, saved_hash = _input_identities(payload)
    ordered_regions = [
        *provider_projection["target_regions"],
        *provider_projection["context_regions"],
    ]
    bindings_json = _canonical_text(ordered_regions)
    projection = RequestProjection(
        host_packet_sha256=host["packet_sha256"],
        body_utf8=body_utf8,
        body_sha256=sha256_bytes(body_utf8.encode("utf-8")),
        schema_sha256=schema.schema_sha256,
        prompt_sha256=payload["prompt_sha256"],
        model_name=model_name,
        model_digest=payload["model_digest"],
        image_sha256=image["sha256"],
        source_layers_sha256=source_hash,
        image_bindings_json=bindings_json,
        image_bindings_sha256=sha256_bytes(bindings_json.encode("utf-8")),
        diagnostics_sha256=diagnostics_hash,
        saved_proposal_sha256=saved_hash,
    )
    return projection, schema


def _apply_conformance(schema, enabled):
    if enabled:
        from congressional_globe.productive_ocr_conformance import specialize_conformance

        specialize_conformance(schema)
