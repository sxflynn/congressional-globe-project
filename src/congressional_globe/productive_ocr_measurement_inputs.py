"""Offline loading and verification of the frozen S5 measurement inputs."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from congressional_globe.productive_ocr_host import EvidenceRecord, EvidenceRegistry, validate_host
from congressional_globe.productive_ocr_projection import (
    RequestProjection,
    compile_request_projection,
)

ASSEMBLY = Path("artifacts/study-input-assembly-20261029-01")
HOST_SHA256 = "bfb175c53ce0b5a026516310e3670628ef3482f18f980df894838f794805a2aa"
REQUEST_SHA256 = "e19305443cf7b8676acdf25848b88455db203d55b8e1c394116bdd071aed000a"
IMAGE_SHA256 = "a1ee1cd7a90786a9133380126140dccc9e1b53f0b00bf6b9982e92840c6d1530"


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _hashes(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(_hashes(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_hashes(item) for item in value), set())
    if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
        return {value}
    return set()


def _read_verified(path: Path, digest: str) -> bytes:
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != digest:
        raise ValueError(f"registered resource changed: {digest}")
    return content


def _load_registered_resource(
    digest: str,
    root: Path,
    index: dict,
    record_ids: set[str],
    file_ids: set[str],
    records: dict[str, EvidenceRecord],
    files: dict[str, bytes],
) -> set[str]:
    if digest in record_ids:
        raw = _read_verified(root / "registered" / digest, digest)
        record = json.loads(raw)
        files[digest] = raw
        records[digest] = EvidenceRecord(record, raw)
        return _hashes(record)
    if digest in file_ids:
        path = root.parent.parent / index["files"][digest]["path"]
        files[digest] = _read_verified(path, digest)
    return set()


def _registry(root: Path, host: dict, index: dict) -> EvidenceRegistry:
    files: dict[str, bytes] = {}
    records: dict[str, EvidenceRecord] = {}
    pending = _hashes(host["payload"])
    record_ids = set(index["records"])
    file_ids = set(index["files"])
    while pending:
        digest = pending.pop()
        if digest not in records and digest not in files:
            pending.update(
                _load_registered_resource(digest, root, index, record_ids, file_ids, records, files)
            )
    image_hash = host["payload"]["image"]["sha256"]
    image_path = root.parent.parent / index["images"][image_hash]
    image_bytes = _read_verified(image_path, image_hash)
    return EvidenceRegistry({image_hash: image_bytes}, records, files)


def load_s5_inputs(repository: Path) -> tuple[dict, RequestProjection, EvidenceRegistry]:
    """Load only the S5 resource closure and check every frozen projection byte."""
    root = repository / ASSEMBLY
    host = _json(root / "S5" / "host.json")
    if host.get("packet_sha256") != HOST_SHA256:
        raise ValueError("S5 host packet identity changed")
    index = _json(root / "registry-index.json")
    registry = _registry(root, host, index)
    validate_host(host, registry)
    prompt = (root / "S5" / "prompt.txt").read_text(encoding="utf-8")
    saved = RequestProjection.model_validate(_json(root / "S5" / "projection.json"))
    request_bytes = (root / "S5" / "request.json").read_bytes()
    if hashlib.sha256(request_bytes).hexdigest() != REQUEST_SHA256:
        raise ValueError("S5 request body identity changed")
    projection, _schema = compile_request_projection(host, registry, prompt, saved.model_name)
    if projection != saved or projection.body_utf8.encode("utf-8") != request_bytes:
        raise ValueError("S5 frozen projection or request bytes disagree with reconstructed inputs")
    return host, projection, registry


def load_s5_text_inputs(repository: Path) -> tuple[dict, RequestProjection, EvidenceRegistry]:
    """Bind the reviewed T97 S5 inputs to today's code and the approved installed model."""
    from congressional_globe.productive_ocr_authority import MODEL_NAME
    from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
    from congressional_globe.productive_ocr_runner import code_identity

    original, _projection, registry = load_s5_inputs(repository)
    root = repository / "artifacts/two-stage-integration-20261030-01"
    host_bytes = _read_verified(
        root / "S5-host.json", "092c6cf332e88fcafc49b4c4da18f33af4c77b1f7b543e9c45b342f7c5115f26"
    )
    host = json.loads(host_bytes)
    _load_text_resources(root, registry)
    validate_host(host, registry)
    _same_s5_source(original, host)
    code_bytes = canonical_json(code_identity())
    host["payload"]["code_sha256"] = sha256_bytes(code_bytes)
    registry.files[sha256_bytes(code_bytes)] = code_bytes
    host["packet_sha256"] = sha256_bytes(canonical_json(host["payload"]))
    prompt = registry.files[host["payload"]["prompt_sha256"]].decode("utf-8")
    projection, _schema = compile_request_projection(host, registry, prompt, MODEL_NAME)
    return host, projection, registry


def _load_text_resources(root, registry):
    closure = _json(root / "registry-closure.json")
    for digest, record in closure["new_files"].items():
        registry.files[digest] = _read_verified(root / record["path"], digest)


def _same_s5_source(original, host):
    old, new = original["payload"], host["payload"]
    if (new["unit_id"], new["image"], new["sampling_manifest_sha256"]) != (
        old["unit_id"],
        old["image"],
        old["sampling_manifest_sha256"],
    ):
        raise ValueError("text measurement changed original S5 source/image/sample")
    before = [(p["source_id"], p["raw"], p["role"]) for p in old["paragraphs"]]
    after = [(p["source_id"], p["raw"], p["role"]) for p in new["paragraphs"]]
    if before != after:
        raise ValueError("text measurement changed original S5 paragraph boundaries/raw")


def load_s5_conformance_inputs(
    repository: Path,
) -> tuple[dict, RequestProjection, EvidenceRegistry]:
    """Load only the reviewed strict-schema body, preserving both historical loaders."""
    from congressional_globe.productive_ocr_authority import MODEL_NAME
    from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
    from congressional_globe.productive_ocr_runner import code_identity

    original, _projection, registry = load_s5_inputs(repository)
    t97 = repository / "artifacts/two-stage-integration-20261030-01"
    root = repository / "artifacts/text-reply-conformance-20261030-01"
    host = json.loads(
        _read_verified(
            root / "candidate-host.json",
            "407bec1b03c049d00454acc9f2690caccb656548272da00a8b3494a2a7d4ea79",
        )
    )
    _load_text_resources(t97, registry)
    _load_text_resources(root, registry)
    validate_host(host, registry)
    _same_s5_source(original, host)
    code = canonical_json(code_identity())
    host["payload"]["code_sha256"] = sha256_bytes(code)
    registry.files[sha256_bytes(code)] = code
    host["packet_sha256"] = sha256_bytes(canonical_json(host["payload"]))
    prompt = registry.files[host["payload"]["prompt_sha256"]].decode("utf-8")
    projection, _schema = compile_request_projection(
        host, registry, prompt, MODEL_NAME, conformance_v4=True
    )
    return host, projection, registry


def load_s5_scoped_inputs(repository: Path) -> tuple[dict, RequestProjection, EvidenceRegistry]:
    """Derive the reviewed target/context scope without changing the T104 wire request."""
    from congressional_globe.productive_ocr_authority import MODEL_NAME
    from congressional_globe.productive_ocr_measurement_scoped import BODY_SHA
    from congressional_globe.productive_ocr_scope import prepare_source_scope

    original, _projection, registry = load_s5_conformance_inputs(repository)
    bundle = repository / "artifacts/ocr-live-readiness-20261028-01/images/S5/bundle.json"
    context = [("congressionalglo7395unit:529:par_000529_000007", "line_000529_000019")]
    host = prepare_source_scope(original, registry, bundle.read_bytes(), context)
    prompt = registry.files[host["payload"]["prompt_sha256"]].decode()
    projection, _schema = compile_request_projection(
        host, registry, prompt, MODEL_NAME, conformance_v4=True
    )
    if projection.body_sha256 != BODY_SHA:
        raise ValueError("scoped measurement differs from exact T104 request")
    return host, projection, registry
