"""Strict offline validation and provider projection for productive OCR packets."""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import dataclass
from typing import Annotated, Any, Literal, NoReturn

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator

from congressional_globe.deterministic_models import ExactEdit, replay_with_map

HOST_CONTRACT = "ocr-productive-repair-host-input-v2"
PROVIDER_CONTRACT = "ocr-productive-repair-input-v2"
REPLY_CONTRACT = "ocr-productive-repair-reply-v2"


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def text_sha256(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


@dataclass(frozen=True)
class EvidenceRecord:
    """Hash-addressed registration record plus independently supplied evidence bytes."""

    record: dict[str, Any]
    evidence_bytes: bytes


@dataclass(frozen=True)
class EvidenceRegistry:
    """Trusted local records keyed by their declared SHA-256 identities."""

    image_bytes: dict[str, bytes]
    records: dict[str, EvidenceRecord]
    files: dict[str, bytes]


Sha256 = str


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class LegibilityEvidence(StrictModel):
    image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_item_identifier: str = Field(min_length=1)
    source_scan_leaf: int = Field(ge=0)
    status: Literal["checked"]
    scope: Literal["whole_registered_crop"]
    method: str = Field(min_length=1)
    notes: str = Field(min_length=1)


class Box(StrictModel):
    left: int = Field(ge=0)
    top: int = Field(ge=0)
    right: int = Field(ge=1)
    bottom: int = Field(ge=1)

    @model_validator(mode="after")
    def positive_area(self) -> Box:
        if self.left >= self.right or self.top >= self.bottom:
            raise ValueError("geometry must have positive area")
        return self


class Edit(StrictModel):
    edit_id: str = Field(min_length=1)
    raw_start: int = Field(ge=0)
    raw_end: int = Field(ge=1)
    expected: str = Field(min_length=1, pattern=r"\S")
    replacement: str
    reason: str = Field(min_length=1)


class Layer(StrictModel):
    text: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class StaticLayer(StrictModel):
    text: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    edits: list[Edit] = Field(max_length=128)
    rule_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    lexicon_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Paragraph(StrictModel):
    alias: str = Field(pattern=r"^P([1-9]|[12][0-9]|3[0-2])$")
    source_id: str = Field(pattern=r"^[^:\s]+:[0-9]+:[^:\s]+$", max_length=256)
    part_number: int = Field(ge=1, le=5)
    scan_leaf: int = Field(ge=0)
    role: Literal["target", "context"]
    raw: Layer
    static: StaticLayer


class Binding(StrictModel):
    paragraph_alias: str = Field(pattern=r"^P([1-9]|[12][0-9]|3[0-2])$")
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_start: int = Field(ge=0)
    raw_end: int = Field(ge=1)
    crop_region: Box


class ImageBinding(StrictModel):
    alias: Literal["I1"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mime: Literal["image/jpeg", "image/png"]
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    bindings: list[Binding] = Field(min_length=1, max_length=32)
    registration_status: Literal["verified", "unknown"]
    legibility_status: Literal["checked", "unknown"]
    source_item_identifier: str = Field(min_length=1)
    source_scan_leaf: int = Field(ge=0)
    hocr_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_map_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    binding_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    registration_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Signal(StrictModel):
    signal_id: str = Field(min_length=1)
    paragraph_alias: str = Field(pattern=r"^P([1-9]|[12][0-9]|3[0-2])$")
    raw_start: int = Field(ge=0)
    raw_end: int = Field(ge=1)
    raw_quote: str = Field(min_length=1, pattern=r"\S")
    category: Literal["word", "name_place", "number", "mixed", "split", "other"]
    flags: list[Annotated[str, Field(min_length=1)]] = Field(max_length=16)
    route_reason: str = Field(min_length=1)


class Diagnostics(StrictModel):
    status: Literal["not_run", "frozen"]
    detector_sha256: str | None = Field(pattern=r"^[0-9a-f]{64}$")
    configuration_sha256: str | None = Field(pattern=r"^[0-9a-f]{64}$")
    signals: list[Signal] = Field(max_length=128)
    negative_targets: list[Annotated[str, Field(pattern=r"^P([1-9]|[12][0-9]|3[0-2])$")]] = Field(
        max_length=32
    )


class ProposalParagraph(StrictModel):
    paragraph_alias: str = Field(pattern=r"^P([1-9]|[12][0-9]|3[0-2])$")
    text: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_edits: list[Edit] = Field(max_length=128)


class SavedProposal(StrictModel):
    record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prior_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prior_raw_reply_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    paragraphs: list[ProposalParagraph] = Field(min_length=1, max_length=32)
    review_state: Literal["unreviewed_model_proposal"]


class HostPayload(StrictModel):
    contract: Literal["ocr-productive-repair-host-input-v2"]
    role: Literal["productive_repair_and_self_check", "audit_saved_proposal"]
    unit_id: str = Field(min_length=1)
    paragraphs: list[Paragraph] = Field(min_length=1, max_length=32)
    image: ImageBinding | None
    diagnostics: Diagnostics
    saved_proposal: SavedProposal | None
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    sampling_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bounds_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class HostEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    packet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload: HostPayload

    @model_validator(mode="after")
    def packet_hash(self) -> HostEnvelope:
        if self.packet_sha256 != sha256_bytes(canonical_json(self.payload.model_dump(mode="json"))):
            raise ValueError("packet hash mismatch")
        return self


def _fail(message: str) -> NoReturn:
    raise ValueError(message)


def _shape(value: Any, required: set[str], label: str, optional: set[str] | None = None) -> None:
    if (
        not isinstance(value, dict)
        or not required <= value.keys()
        or value.keys() - required - (optional or set())
    ):
        _fail(f"invalid {label} fields")


def _hash(value: str, expected: str, label: str) -> None:
    if value != expected:
        _fail(f"{label} hash mismatch")


def _replay(raw: str, edits: list[dict[str, Any]], layer: str) -> str:
    bound = tuple(
        ExactEdit(
            start=e["raw_start"],
            end=e["raw_end"],
            raw_quote=e["expected"],
            replacement=e["replacement"],
            rule_id=e["edit_id"],
        )
        for e in edits
    )
    return replay_with_map(raw, bound)[0]


def _verify_image(
    image: dict[str, Any], paragraphs: dict[str, dict[str, Any]], registry: EvidenceRegistry
) -> None:
    data = registry.image_bytes.get(image["sha256"])
    if data is None or sha256_bytes(data) != image["sha256"] or len(data) > 16 * 1024 * 1024:
        _fail("missing, oversized, or hash-mismatched image bytes")
    width, height, mime = _image_metadata(data)
    if (width, height, mime) != (image["width"], image["height"], image["mime"]):
        _fail("image dimensions or MIME do not match bytes")
    if image["registration_status"] != "verified" or image["legibility_status"] != "checked":
        _fail("image registration and legibility must be verified")
    metadata = _verify_records(image, registry, width, height)
    _verify_target_geometry(image, paragraphs, metadata, width, height)


def _image_metadata(data: bytes) -> tuple[int, int, str | None]:
    try:
        with Image.open(io.BytesIO(data)) as opened:
            opened.verify()
        with Image.open(io.BytesIO(data)) as opened:
            width, height = opened.size
            mime = Image.MIME.get(opened.format or "")
    except Exception as exc:
        raise ValueError("invalid image bytes") from exc
    return width, height, mime


def _verify_records(
    image: dict[str, Any], registry: EvidenceRegistry, width: int, height: int
) -> dict[str, Any]:
    registration = registry.records.get(image["registration_evidence_sha256"])
    binding = registry.records.get(image["binding_manifest_sha256"])
    _verify_record_bytes(image, registry, registration, binding)
    if binding is None:
        _fail("binding record missing")
    if registration is None:
        _fail("registration record missing")
    _verify_legibility(image, registration, registry)
    _verify_record_identity(image, registration, binding, width, height)
    return binding.record


def _verify_legibility(
    image: dict[str, Any], registration: EvidenceRecord, registry: EvidenceRegistry
) -> None:
    proof_hash = registration.record.get("legibility_evidence_sha256")
    if not isinstance(proof_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", proof_hash):
        _fail("registration record lacks legibility evidence identity")
    _verify_legibility_file(image, registry, proof_hash)


def _verify_legibility_file(
    image: dict[str, Any], registry: EvidenceRegistry, proof_hash: str
) -> None:
    _require_file_hash(registry, proof_hash, "legibility evidence")
    try:
        proof = LegibilityEvidence.model_validate_json(registry.files[proof_hash])
    except Exception as exc:
        raise ValueError("invalid legibility evidence record") from exc
    expected = (
        image["sha256"],
        image["source_item_identifier"],
        image["source_scan_leaf"],
    )
    actual = (proof.image_sha256, proof.source_item_identifier, proof.source_scan_leaf)
    if actual != expected:
        _fail("legibility evidence source identity mismatch")


def _verify_record_bytes(
    image: dict[str, Any],
    registry: EvidenceRegistry,
    registration: EvidenceRecord | None,
    binding: EvidenceRecord | None,
) -> None:
    if binding is None or registration is None:
        _fail("registration or binding record missing")
    _verify_evidence_file(registry, image["binding_manifest_sha256"], binding, "binding")
    _verify_evidence_file(
        registry, image["registration_evidence_sha256"], registration, "registration"
    )
    _require_file_hash(registry, image["hocr_sha256"], "hOCR")
    _require_file_hash(registry, image["page_map_sha256"], "page map")


def _verify_evidence_file(
    registry: EvidenceRegistry, digest: str, evidence: EvidenceRecord, label: str
) -> None:
    _require_file_hash(registry, digest, label)
    if registry.files[digest] != evidence.evidence_bytes:
        _fail(f"{label} registry bytes disagree")
    try:
        if json.loads(evidence.evidence_bytes) != evidence.record:
            _fail(f"{label} record differs from its frozen file")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} evidence must be JSON") from exc


def _verify_record_identity(
    image: dict[str, Any],
    registration: EvidenceRecord | None,
    binding: EvidenceRecord | None,
    width: int,
    height: int,
) -> None:
    if registration is None or binding is None:
        _fail("registration or binding record missing")
    expected = {
        "sha256": image["sha256"],
        "source_item_identifier": image["source_item_identifier"],
        "source_scan_leaf": image["source_scan_leaf"],
        "hocr_sha256": image["hocr_sha256"],
        "page_map_sha256": image["page_map_sha256"],
        "width": width,
        "height": height,
    }
    _check_identity(binding.record, expected, "binding manifest")
    _check_identity(registration.record, expected, "registration")
    if binding.record.get("paragraph_boxes") != registration.record.get("paragraph_boxes"):
        _fail("registration and manifest geometry disagree")


def _check_identity(record: dict[str, Any], expected: dict[str, Any], label: str) -> None:
    if any(record.get(key) != value for key, value in expected.items()):
        _fail(f"{label} source identity mismatch")


def _verify_target_geometry(
    image: dict[str, Any],
    paragraphs: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
    width: int,
    height: int,
) -> None:
    bindings = {entry["paragraph_alias"]: entry for entry in image["bindings"]}
    if len(bindings) != len(image["bindings"]) or set(bindings) != set(paragraphs):
        _fail("image bindings must cover every target and context exactly")
    _validate_source_ids(image, paragraphs)
    _verify_manifest_spans(paragraphs, metadata)
    for alias, paragraph in paragraphs.items():
        _verify_one_target(alias, paragraph, bindings[alias], metadata, width, height)


def _validate_source_ids(image: dict[str, Any], paragraphs: dict[str, dict[str, Any]]) -> None:
    for para in paragraphs.values():
        _validate_source_id(image, para)


def _validate_source_id(image: dict[str, Any], paragraph: dict[str, Any]) -> None:
    item, leaf, paragraph_id = paragraph["source_id"].split(":")
    if item != image["source_item_identifier"] or int(leaf) != paragraph["scan_leaf"]:
        _fail("paragraph source id disagrees with registered item or scan leaf")
    if not paragraph_id:
        _fail("paragraph source id lacks paragraph identity")


def _verify_manifest_spans(
    paragraphs: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
) -> None:
    if metadata.get("paragraph_order") != list(paragraphs):
        _fail("source paragraph order differs from frozen binding manifest")
    expected = {
        alias: {
            "raw_sha256": para["raw"]["sha256"],
            "raw_start": 0,
            "raw_end": len(para["raw"]["text"]),
        }
        for alias, para in paragraphs.items()
    }
    if metadata.get("paragraph_bindings") != expected:
        _fail("binding manifest raw-span identities mismatch")


def _verify_one_target(
    alias: str,
    paragraph: dict[str, Any],
    item: dict[str, Any],
    metadata: dict[str, Any],
    width: int,
    height: int,
) -> None:
    if item["raw_sha256"] != paragraph["raw"]["sha256"] or (item["raw_start"], item["raw_end"]) != (
        0,
        len(paragraph["raw"]["text"]),
    ):
        _fail("image binding does not cover exact target raw text")
    box = item["crop_region"]
    if not (0 <= box["left"] < box["right"] <= width and 0 <= box["top"] < box["bottom"] <= height):
        _fail("image crop geometry outside image")
    if metadata.get("paragraph_boxes", {}).get(alias) != box:
        _fail("target geometry lacks matching frozen manifest proof")


def _validate_payload(payload: dict[str, Any], registry: EvidenceRegistry) -> dict[str, Any]:
    _validate_packet_resources(payload, registry)
    paragraphs = payload.get("paragraphs")
    if not isinstance(paragraphs, list) or not 1 <= len(paragraphs) <= 32:
        _fail("paragraph count outside contract")
    targets, contexts = _validate_paragraphs(paragraphs, registry)
    _validate_diagnostics(payload["diagnostics"], targets, registry)
    image = payload["image"]
    if image is not None:
        _verify_image(image, targets | contexts, registry)
    _validate_proposal(payload, targets, registry)
    return payload


def _validate_packet_resources(payload: dict[str, Any], registry: EvidenceRegistry) -> None:
    for key in (
        "prompt_sha256",
        "response_schema_sha256",
        "code_sha256",
        "model_digest",
        "sampling_manifest_sha256",
        "bounds_sha256",
    ):
        _require_file_hash(registry, payload[key], key)


def _require_file_hash(registry: EvidenceRegistry, digest: str, label: str) -> None:
    content = registry.files.get(digest)
    if (
        not re.fullmatch(r"[0-9a-f]{64}", digest)
        or content is None
        or sha256_bytes(content) != digest
    ):
        _fail(f"{label} resource missing or changed")


def _validate_paragraphs(
    paragraphs: list[dict[str, Any]], registry: EvidenceRegistry
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    _validate_paragraph_order(paragraphs)
    targets, contexts = _partition_paragraphs(paragraphs)
    if not targets:
        _fail("at least one target paragraph is required")
    _validate_text_budgets(targets, contexts)
    for para in paragraphs:
        _validate_one_paragraph(para, registry)
    return targets, contexts


def _validate_paragraph_order(paragraphs: list[dict[str, Any]]) -> None:
    _require_unique([p["alias"] for p in paragraphs], "paragraph alias")
    _require_unique([p["source_id"] for p in paragraphs], "source identity")


def _require_unique(values: list[str], label: str) -> None:
    if len(set(values)) != len(values):
        _fail(f"duplicate {label}")


def _partition_paragraphs(paragraphs: list[dict[str, Any]]) -> tuple[dict, dict]:
    targets = {p["alias"]: p for p in paragraphs if p["role"] == "target"}
    contexts = {p["alias"]: p for p in paragraphs if p["role"] == "context"}
    return targets, contexts


def _validate_text_budgets(targets: dict, contexts: dict) -> None:
    if (
        sum(len(p["raw"]["text"]) for p in targets.values()) > 6000
        or sum(len(p["static"]["text"]) for p in targets.values()) > 6000
    ):
        _fail("target text exceeds aggregate input bound")
    if (
        sum(len(p["raw"]["text"]) for p in contexts.values()) > 2000
        or sum(len(p["static"]["text"]) for p in contexts.values()) > 2000
    ):
        _fail("context text exceeds aggregate input bound")


def _validate_one_paragraph(para: dict[str, Any], registry: EvidenceRegistry) -> None:
    _shape(para["raw"], {"text", "sha256"}, "raw layer")
    _shape(
        para["static"], {"text", "sha256", "edits", "rule_sha256", "lexicon_sha256"}, "static layer"
    )
    raw, static = para["raw"], para["static"]
    _hash(raw["sha256"], text_sha256(raw["text"]), "raw text")
    _hash(static["sha256"], text_sha256(static["text"]), "static text")
    _require_file_hash(registry, static["rule_sha256"], "static rule")
    _require_file_hash(registry, static["lexicon_sha256"], "static lexicon")
    if _replay(raw["text"], static["edits"], "static") != static["text"]:
        _fail("static edits do not reconstruct static text")


def _validate_diagnostics(
    diagnostics: dict[str, Any], targets: dict[str, dict[str, Any]], registry: EvidenceRegistry
) -> None:
    _shape(
        diagnostics,
        {"status", "detector_sha256", "configuration_sha256", "signals", "negative_targets"},
        "diagnostics",
    )
    if diagnostics["status"] == "not_run":
        _validate_not_run(diagnostics)
        return
    _validate_frozen_diagnostics(diagnostics, targets, registry)


def _validate_not_run(diagnostics: dict[str, Any]) -> None:
    if (
        diagnostics["detector_sha256"] is not None
        or diagnostics["configuration_sha256"] is not None
    ):
        _fail("not_run diagnostics have frozen identities")
    if diagnostics["signals"] or diagnostics["negative_targets"]:
        _fail("not_run diagnostics must be empty")


def _validate_frozen_diagnostics(
    diagnostics: dict[str, Any], targets: dict[str, dict[str, Any]], registry: EvidenceRegistry
) -> None:
    _validate_detector_resources(diagnostics, registry)
    negatives = _validated_negatives(diagnostics["negative_targets"], targets)
    signaled = _validated_signals(diagnostics["signals"], targets)
    if signaled | negatives != set(targets) or signaled & negatives:
        _fail("each target needs signals or explicit detector-negative status")


def _validate_detector_resources(diagnostics: dict[str, Any], registry: EvidenceRegistry) -> None:
    _require_file_hash(registry, diagnostics["detector_sha256"], "detector")
    _require_file_hash(registry, diagnostics["configuration_sha256"], "detector configuration")


def _validated_negatives(negative_targets: list[str], targets: dict[str, Any]) -> set[str]:
    negatives = set(negative_targets)
    if len(negatives) != len(negative_targets) or negatives - set(targets):
        _fail("diagnostic negatives must uniquely name declared targets")
    return negatives


def _validated_signals(signals: list[dict[str, Any]], targets: dict[str, Any]) -> set[str]:
    seen: set[str] = set()
    signaled: set[str] = set()
    for signal in signals:
        _validate_signal(signal, targets)
        if signal["signal_id"] in seen:
            _fail("duplicate diagnostic signal id")
        seen.add(signal["signal_id"])
        signaled.add(signal["paragraph_alias"])
    return signaled


def _validate_signal(signal: dict[str, Any], targets: dict[str, dict[str, Any]]) -> None:
    para = targets.get(signal["paragraph_alias"])
    start, end = signal["raw_start"], signal["raw_end"]
    if para is None or end <= start or end > len(para["raw"]["text"]):
        _fail("diagnostic signal span outside target raw text")
    if para["raw"]["text"][start:end] != signal["raw_quote"]:
        _fail("diagnostic signal quote does not bind to raw text")


def _validate_proposal(
    payload: dict[str, Any], targets: dict[str, dict[str, Any]], registry: EvidenceRegistry
) -> None:
    if payload["role"] == "productive_repair_and_self_check":
        _check_productive_proposal(payload["saved_proposal"])
        return
    _check_audit_proposal(payload["saved_proposal"], targets, registry)


def _check_productive_proposal(proposal: dict[str, Any] | None) -> None:
    if proposal is not None:
        _fail("productive role cannot include saved proposal")


def _check_audit_proposal(
    proposal: dict[str, Any] | None, targets: dict[str, dict[str, Any]], registry: EvidenceRegistry
) -> None:
    if proposal is None:
        _fail("audit role requires a saved proposal")
    _require_file_hash(registry, proposal["record_sha256"], "saved proposal record")
    _require_file_hash(registry, proposal["prior_request_sha256"], "saved request")
    _require_file_hash(registry, proposal["prior_raw_reply_sha256"], "saved raw reply")
    _verify_saved_record(proposal, registry)
    _validate_saved_proposal(proposal, targets)


def _verify_saved_record(proposal: dict[str, Any], registry: EvidenceRegistry) -> None:
    digest = proposal["record_sha256"]
    record = {key: value for key, value in proposal.items() if key != "record_sha256"}
    if registry.files[digest] != canonical_json(record):
        _fail("saved proposal record bytes do not match canonical proposal content")


def _validate_saved_proposal(proposal: dict[str, Any], targets: dict[str, dict[str, Any]]) -> None:
    aliases = [p["paragraph_alias"] for p in proposal["paragraphs"]]
    if len(set(aliases)) != len(aliases) or set(aliases) != set(targets):
        _fail("audit requires exactly one saved proposal per target")
    for prior in proposal["paragraphs"]:
        _validate_saved_paragraph(prior, targets[prior["paragraph_alias"]])


def _validate_saved_paragraph(prior: dict[str, Any], target: dict[str, Any]) -> None:
    raw = target["raw"]["text"]
    if _replay(raw, prior["raw_edits"], "saved proposal") != prior["text"]:
        _fail("saved proposal does not replay")
    _hash(prior["sha256"], text_sha256(prior["text"]), "saved proposal text")


def validate_host(payload: dict[str, Any], registry: EvidenceRegistry) -> dict[str, Any]:
    """Validate packet envelope, hashes, replay, image evidence and semantic invariants."""
    envelope = HostEnvelope.model_validate(payload)
    _validate_payload(envelope.payload.model_dump(mode="json"), registry)
    return envelope.model_dump(mode="json")


def project_provider(validated_host: dict[str, Any]) -> dict[str, Any]:
    """Project only declared provider-visible fields, preserving source strings exactly."""
    data = validated_host["payload"]
    image = data["image"]
    if image is None:
        _fail("host packet is not launch-ready")
    _require_image_ready(image, data["diagnostics"])
    return {
        "contract": PROVIDER_CONTRACT,
        "reply_contract": REPLY_CONTRACT,
        "unit_id": data["unit_id"],
        "role": data["role"],
        "image_alias": image["alias"],
        "target_regions": _project_regions(image, data["paragraphs"], "target"),
        "context_regions": _project_regions(image, data["paragraphs"], "context"),
        "paragraphs": _project_paragraphs(data["paragraphs"]),
        "diagnostics": data["diagnostics"],
        "saved_proposal": data["saved_proposal"],
    }


def _require_image_ready(image: dict[str, Any], diagnostics: dict[str, Any]) -> None:
    if image["registration_status"] != "verified" or image["legibility_status"] != "checked":
        _fail("host packet is not launch-ready")
    if diagnostics["status"] != "frozen":
        _fail("diagnostics must be frozen before provider projection")


def _project_regions(
    image: dict[str, Any], paragraphs: list[dict[str, Any]], role: str
) -> list[dict]:
    bindings = {item["paragraph_alias"]: item for item in image["bindings"]}
    return [
        {"paragraph_alias": para["alias"], "crop_region": bindings[para["alias"]]["crop_region"]}
        for para in paragraphs
        if para["role"] == role
    ]


def _project_paragraphs(paragraphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "paragraph_alias": p["alias"],
            "role": p["role"],
            "raw_text": p["raw"]["text"],
            "static_text": p["static"]["text"],
            "static_edits": p["static"]["edits"],
        }
        for p in paragraphs
    ]
