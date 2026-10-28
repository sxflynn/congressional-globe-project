"""Typed, source-bound T69 host export for valid and invalid provider replies."""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Literal

from pydantic import Field

from congressional_globe.bracket_cues import Contract
from congressional_globe.productive_ocr_host import canonical_json, project_provider, sha256_bytes
from congressional_globe.productive_ocr_projection import source_layers_identity
from congressional_globe.productive_ocr_reply import Reply, validate_reply

MAX_RAW_ENTITY_BYTES = 32 * 1024 * 1024


class Position(Contract):
    paragraph_alias: str = Field(pattern=r"^P([1-9]|[12][0-9]|3[0-2])$")
    source_id: str = Field(min_length=1)
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_start: int = Field(ge=0)
    raw_end: int = Field(ge=1)
    raw_quote: str = Field(min_length=1)
    method: Literal["unique_exact_raw_quote", "declared_whole_paragraph"]
    layer: Literal["raw", "static", "saved_proposal"]
    layer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    layer_start: int | None = Field(ge=0)
    layer_end: int | None = Field(ge=1)
    image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    finding_id: str | None


class DerivedMapping(Contract):
    raw_start: int = Field(ge=0)
    raw_end: int = Field(ge=0)
    derived_start: int = Field(ge=0)
    derived_end: int = Field(ge=0)
    kind: Literal["unchanged", "replacement"]


class DerivedProposal(Contract):
    paragraph_alias: str = Field(pattern=r"^P([1-9]|[12][0-9]|3[0-2])$")
    source_id: str = Field(min_length=1)
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mapping: list[DerivedMapping] = Field(max_length=256)
    state: Literal["unreviewed_model_proposal"] = "unreviewed_model_proposal"


class HostExport(Contract):
    contract: Literal["source-bound-productive-ocr-repair-v2"] = (
        "source-bound-productive-ocr-repair-v2"
    )
    host_packet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_reply_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    host_binding_version: Literal["ocr-productive-repair-binding-v2"] = (
        "ocr-productive-repair-binding-v2"
    )
    role: Literal["productive_repair_and_self_check", "audit_saved_proposal"]
    unit_id: str = Field(min_length=1)
    outcome: Literal[
        "valid_findings", "valid_no_finding", "valid_incomplete", "valid_unresolved", "invalid"
    ]
    rejection_reason: str | None = Field(min_length=1)
    provider_reply: Reply | None
    bindings: list[Position] = Field(max_length=128)
    derived_proposals: list[DerivedProposal] = Field(max_length=32)
    acceptance_state: Literal["unreviewed_ai_evidence"] = "unreviewed_ai_evidence"
    image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    diagnostics_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_layers_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_reply_text: str
    provider_usage_json: str | None
    elapsed_seconds: float | None = Field(ge=0, allow_inf_nan=False)


class TransportFailureExport(Contract):
    contract: Literal["source-bound-productive-ocr-transport-failure-v1"] = (
        "source-bound-productive-ocr-transport-failure-v1"
    )
    host_packet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_http_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_entity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_entity_base64: str = Field(max_length=44_739_244)
    model_name: str = Field(min_length=1)
    model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    host_binding_version: Literal["ocr-productive-repair-binding-v2"] = (
        "ocr-productive-repair-binding-v2"
    )
    role: Literal["productive_repair_and_self_check", "audit_saved_proposal"]
    unit_id: str = Field(min_length=1)
    outcome: Literal["invalid_provider_encoding_or_transport"] = (
        "invalid_provider_encoding_or_transport"
    )
    failure_reason: str = Field(min_length=1, max_length=1000)
    model_reply_text: None = None
    model_reply_sha256: None = None
    acceptance_state: Literal["unreviewed_ai_evidence"] = "unreviewed_ai_evidence"
    image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    diagnostics_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_layers_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_usage_json: str | None
    elapsed_seconds: float | None = Field(ge=0, allow_inf_nan=False)


def _image_hash(payload: dict) -> str:
    image = payload["image"]
    return image["sha256"] if image is not None else sha256_bytes(canonical_json(None))


def _source_hash(payload: dict) -> str:
    return source_layers_identity(payload)


def _layer_hash(row: dict, layer: str, payload: dict) -> str:
    if layer == "raw":
        return row["raw"]["sha256"]
    if layer == "static":
        return row["static"]["sha256"]
    saved = payload["saved_proposal"]
    item = next(p for p in saved["paragraphs"] if p["paragraph_alias"] == row["alias"])
    return item["sha256"]


def _finding_bindings(mapped: dict, reply: Reply, payload: dict) -> list[Position]:
    targets = {row["alias"]: row for row in payload["paragraphs"] if row["role"] == "target"}
    findings = {item.finding_id: item for item in reply.findings}
    positions = []
    for entry in mapped["source_mapped_findings"]:
        finding = findings[entry["finding"]["finding_id"]]
        alias = finding.anchor.paragraph_alias
        row = targets[alias]
        start, end = entry["raw_support"]
        layer_start, layer_end = entry["layer_span"]
        positions.append(
            Position(
                paragraph_alias=alias,
                source_id=row["source_id"],
                raw_sha256=row["raw"]["sha256"],
                raw_start=start,
                raw_end=end,
                raw_quote=row["raw"]["text"][start:end],
                method="unique_exact_raw_quote"
                if finding.anchor.scope == "quote"
                else "declared_whole_paragraph",
                layer=finding.affected_layer,
                layer_sha256=_layer_hash(row, finding.affected_layer, payload),
                layer_start=layer_start if finding.affected_quote is not None else None,
                layer_end=layer_end if finding.affected_quote is not None else None,
                image_sha256=_image_hash(payload),
                finding_id=finding.finding_id,
            )
        )
    return positions


def _patch_bindings(mapped: dict, payload: dict) -> list[Position]:
    targets = {row["alias"]: row for row in payload["paragraphs"] if row["role"] == "target"}
    image_hash = _image_hash(payload)
    positions = []
    for alias, reading in mapped["proposed_readings"].items():
        row = targets[alias]
        for patch in reading.get("patches", []):
            start, end = patch["start"], patch["end"]
            positions.append(
                Position(
                    paragraph_alias=alias,
                    source_id=row["source_id"],
                    raw_sha256=row["raw"]["sha256"],
                    raw_start=start,
                    raw_end=end,
                    raw_quote=row["raw"]["text"][start:end],
                    method="unique_exact_raw_quote",
                    layer="raw",
                    layer_sha256=row["raw"]["sha256"],
                    layer_start=start,
                    layer_end=end,
                    image_sha256=image_hash,
                    finding_id=patch["finding_id"],
                )
            )
    return positions


def _derived(mapped: dict, payload: dict) -> list[DerivedProposal]:
    targets = {row["alias"]: row for row in payload["paragraphs"] if row["role"] == "target"}
    return [
        _derived_one(alias, result, targets[alias])
        for alias, result in mapped["proposed_readings"].items()
        if result
    ]


def _derived_one(alias: str, result: dict, row: dict) -> DerivedProposal:
    mapping = [
        DerivedMapping(
            raw_start=item["raw_start"],
            raw_end=item["raw_end"],
            derived_start=item["derived_start"],
            derived_end=item["derived_end"],
            kind="unchanged" if item["mapping"] == "exact_copy" else "replacement",
        )
        for item in result["support_map"]
    ]
    return DerivedProposal(
        paragraph_alias=alias,
        source_id=row["source_id"],
        raw_sha256=row["raw"]["sha256"],
        text=result["text"],
        sha256=result["sha256"],
        mapping=mapping,
    )


def _usage_text(value: str | dict | None) -> str | None:
    if value is None or isinstance(value, str):
        return value
    return canonical_json(value).decode("utf-8")


def _valid_outcome(
    reply: Reply,
) -> Literal["valid_findings", "valid_no_finding", "valid_incomplete", "valid_unresolved"]:
    return {
        "findings": "valid_findings",
        "no_finding": "valid_no_finding",
        "incomplete": "valid_incomplete",
        "unresolved": "valid_unresolved",
    }[reply.status]


def _verify_request_body(host: dict, request_text: str, schema_hash: str) -> None:
    try:
        body = json.loads(request_text)
        payload = host["payload"]
        _check_body_shape(body)
        if canonical_json(body).decode("utf-8") != request_text:
            raise ValueError("provider request body is not canonical UTF-8 JSON")
        _check_request_content(body, payload, host, schema_hash)
        _check_request_flags(body)
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("provider request body is incomplete or malformed") from exc


def _check_request_content(body: dict, payload: dict, host: dict, schema_hash: str) -> None:
    if sha256_bytes(canonical_json(body["format"])) != schema_hash:
        raise ValueError("provider request format does not match response schema hash")
    messages = body["messages"]
    prompt_sha = hashlib.sha256(messages[0]["content"].encode("utf-8")).hexdigest()
    if prompt_sha != payload["prompt_sha256"]:
        raise ValueError("provider request prompt differs from host")
    if messages[1]["content"] != canonical_json(project_provider(host)).decode("utf-8"):
        raise ValueError("provider request projection differs from host")
    _check_request_image(messages[1], payload)


def _check_request_image(user_message: dict, payload: dict) -> None:
    image = payload["image"]
    images = user_message["images"]
    if image is None or len(images) != 1:
        raise ValueError("provider request must bind exactly one registered image")
    if sha256_bytes(base64.b64decode(images[0], validate=True)) != image["sha256"]:
        raise ValueError("provider request image differs from frozen host image")


def _check_body_shape(body: dict) -> None:
    if set(body) != {"model", "stream", "think", "messages", "format", "options"}:
        raise ValueError("provider request has foreign or missing fields")
    _check_message_shape(body["messages"])


def _check_message_shape(messages: list) -> None:
    if len(messages) != 2 or set(messages[0]) != {"role", "content"}:
        raise ValueError("provider request must have exact system and user messages")
    if messages[0]["role"] != "system" or messages[1]["role"] != "user":
        raise ValueError("provider request message roles are invalid")
    if set(messages[1]) != {"role", "content", "images"}:
        raise ValueError("provider user message has foreign or missing fields")


def _check_request_flags(body: dict) -> None:
    if body.get("stream") is not False or body.get("think") is not False:
        raise ValueError("provider request flags differ from frozen request contract")
    options = body.get("options", {})
    if set(options) != {"num_predict"} or not 1 <= options["num_predict"] <= 1500:
        raise ValueError("provider output ceiling outside frozen bounds")


def _parse_export_reply(
    host: dict,
    request_text: str,
    raw_reply_text: str,
    model_digest: str,
    response_schema_sha256: str,
) -> tuple[Reply | None, dict | None, str | None]:
    payload = host["payload"]
    try:
        _check_export_identities(payload, model_digest, response_schema_sha256)
        _verify_request_body(host, request_text, response_schema_sha256)
        mapped = validate_reply(raw_reply_text, host)
        return Reply.model_validate_json(raw_reply_text), mapped, None
    except (ValueError, KeyError, TypeError) as exc:
        return None, None, str(exc)[:1000] or "reply validation failed"


def _check_export_identities(payload: dict, model_digest: str, schema_sha256: str) -> None:
    if model_digest != payload["model_digest"]:
        raise ValueError("export model digest differs from frozen host")
    if schema_sha256 != payload["response_schema_sha256"]:
        raise ValueError("export schema hash differs from frozen host")


def _export_bindings(
    reply: Reply | None, mapped: dict | None, payload: dict, error: str | None
) -> tuple[list[Position], list[DerivedProposal]]:
    if error is not None:
        return [], []
    assert reply is not None and mapped is not None
    return (
        _finding_bindings(mapped, reply, payload) + _patch_bindings(mapped, payload),
        _derived(mapped, payload),
    )


def _export_outcome(
    reply: Reply | None, error: str | None
) -> Literal[
    "valid_findings", "valid_no_finding", "valid_incomplete", "valid_unresolved", "invalid"
]:
    if error is not None:
        return "invalid"
    if reply is None:
        raise ValueError("valid export is missing its parsed reply")
    return _valid_outcome(reply)


def export_reply(
    host: dict,
    provider_request_utf8: str,
    raw_reply_text: str,
    model_digest: str,
    response_schema_sha256: str,
    provider_usage_json: str | dict | None = None,
    elapsed_seconds: float | None = None,
) -> HostExport:
    """Validate and export raw-first provider evidence without implying acceptance."""
    payload = host["payload"]
    reply, mapped, error = _parse_export_reply(
        host, provider_request_utf8, raw_reply_text, model_digest, response_schema_sha256
    )
    bindings, derived = _export_bindings(reply, mapped, payload, error)
    outcome = _export_outcome(reply, error)
    return HostExport(
        host_packet_sha256=host["packet_sha256"],
        provider_request_sha256=hashlib.sha256(provider_request_utf8.encode("utf-8")).hexdigest(),
        raw_reply_sha256=hashlib.sha256(raw_reply_text.encode("utf-8")).hexdigest(),
        model_digest=model_digest,
        response_schema_sha256=response_schema_sha256,
        role=payload["role"],
        unit_id=payload["unit_id"],
        outcome=outcome,
        rejection_reason=error,
        provider_reply=reply,
        bindings=bindings,
        derived_proposals=derived,
        image_sha256=_image_hash(payload),
        diagnostics_sha256=sha256_bytes(canonical_json(payload["diagnostics"])),
        source_layers_sha256=_source_hash(payload),
        raw_reply_text=raw_reply_text,
        provider_usage_json=_usage_text(provider_usage_json),
        elapsed_seconds=elapsed_seconds,
    )


def export_transport_failure(
    host: dict,
    request_body_utf8: str,
    raw_entity_bytes: bytes,
    raw_http_sha256: str,
    model_digest: str,
    reason: str,
    usage_json: str | dict | None = None,
    elapsed_seconds: float | None = None,
) -> TransportFailureExport:
    """Preserve a non-text provider entity without inventing a reply string."""
    payload = host["payload"]
    if len(raw_entity_bytes) > MAX_RAW_ENTITY_BYTES:
        raise ValueError("raw provider response entity exceeds export ceiling")
    if model_digest != payload["model_digest"]:
        raise ValueError("transport failure model digest differs from frozen host")
    schema_hash = payload["response_schema_sha256"]
    if not reason or len(reason) > 1000:
        raise ValueError("transport failure reason must be nonempty and bounded")
    _verify_request_body(host, request_body_utf8, schema_hash)
    request = json.loads(request_body_utf8)
    return TransportFailureExport(
        host_packet_sha256=host["packet_sha256"],
        provider_request_sha256=hashlib.sha256(request_body_utf8.encode("utf-8")).hexdigest(),
        raw_http_sha256=raw_http_sha256,
        raw_entity_sha256=hashlib.sha256(raw_entity_bytes).hexdigest(),
        raw_entity_base64=base64.b64encode(raw_entity_bytes).decode("ascii"),
        model_name=request["model"],
        model_digest=model_digest,
        response_schema_sha256=schema_hash,
        role=payload["role"],
        unit_id=payload["unit_id"],
        failure_reason=reason,
        image_sha256=_image_hash(payload),
        diagnostics_sha256=sha256_bytes(canonical_json(payload["diagnostics"])),
        source_layers_sha256=_source_hash(payload),
        provider_usage_json=_usage_text(usage_json),
        elapsed_seconds=elapsed_seconds,
    )
