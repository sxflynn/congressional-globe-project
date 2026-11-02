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


def load_s1_scoped_inputs(repository: Path) -> tuple[dict, RequestProjection, EvidenceRegistry]:
    """Reconstruct original S1 with frozen feedback, strict reply and visible boundaries."""
    from congressional_globe.productive_ocr_authority import MODEL_NAME
    from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
    from congressional_globe.productive_ocr_measurement_scoped import S1_BODY_SHA
    from congressional_globe.productive_ocr_projection import derive_reply_schema
    from congressional_globe.productive_ocr_routing import TEXT_PROMPT, TEXT_PROMPT_V4
    from congressional_globe.productive_ocr_runner import code_identity
    from congressional_globe.productive_ocr_scope import prepare_source_scope

    root = repository / ASSEMBLY
    original = _json(root / "S1/host.json")
    registry = _registry(root, original, _json(root / "registry-index.json"))
    t97 = repository / "artifacts/two-stage-integration-20261030-01"
    host = json.loads(
        _read_verified(
            t97 / "S1-host.json", "7a2b170d786e778c34d1f6fc8b84a16feb5f01a026a9f67125d7751f36d02d5f"
        )
    )
    _load_text_resources(t97, registry)
    validate_host(host, registry)
    _same_s5_source(original, host)
    old_prompt = registry.files[host["payload"]["prompt_sha256"]].decode()
    if not old_prompt.startswith(TEXT_PROMPT + "\n\n"):
        raise ValueError("S1 source-specific feedback prompt changed")
    prompt = TEXT_PROMPT_V4 + old_prompt[len(TEXT_PROMPT) :]
    _bind_s1_resources(host, registry, prompt, canonical_json(code_identity()))
    schema = derive_reply_schema(host["payload"], conformance_v4=True)
    registry.files[schema.schema_sha256] = schema.schema_text.encode()
    host["payload"]["response_schema_sha256"] = schema.schema_sha256
    host["packet_sha256"] = sha256_bytes(canonical_json(host["payload"]))
    bundle = repository / "artifacts/ocr-live-readiness-20261028-01/images/S1/bundle.json"
    context = [("congressionalg7391unit:526:par_000526_000022", "line_000526_000253")]
    host = prepare_source_scope(host, registry, bundle.read_bytes(), context)
    prompt = registry.files[host["payload"]["prompt_sha256"]].decode()
    projection, _schema = compile_request_projection(
        host, registry, prompt, MODEL_NAME, conformance_v4=True
    )
    if projection.body_sha256 != S1_BODY_SHA:
        raise ValueError("S1 differs from exact feedback-conditioned request")
    return host, projection, registry


def _bind_s1_resources(host, registry, prompt, code):
    from congressional_globe.productive_ocr_host import sha256_bytes

    for field, data in [("prompt_sha256", prompt.encode()), ("code_sha256", code)]:
        digest = sha256_bytes(data)
        host["payload"][field] = digest
        registry.files[digest] = data


def load_s2_scoped_inputs(repository: Path) -> tuple[dict, RequestProjection, EvidenceRegistry]:
    """Reconstruct original S2 with frozen feedback, strict reply and visible boundaries."""
    from congressional_globe.productive_ocr_authority import MODEL_NAME
    from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
    from congressional_globe.productive_ocr_measurement_scoped import S2_BODY_SHA
    from congressional_globe.productive_ocr_projection import derive_reply_schema
    from congressional_globe.productive_ocr_routing import TEXT_PROMPT, TEXT_PROMPT_V4
    from congressional_globe.productive_ocr_runner import code_identity
    from congressional_globe.productive_ocr_scope import prepare_source_scope

    root = repository / ASSEMBLY
    original = _json(root / "S2/host.json")
    registry = _registry(root, original, _json(root / "registry-index.json"))
    t97 = repository / "artifacts/two-stage-integration-20261030-01"
    host = json.loads(
        _read_verified(
            t97 / "S2-host.json", "0afbc0497e89bf3e60a4fc8ae88519c86e4aa0c575ea0d42e035ed1dd5f1c74f"
        )
    )
    _load_text_resources(t97, registry)
    validate_host(host, registry)
    _same_s5_source(original, host)
    old_prompt = registry.files[host["payload"]["prompt_sha256"]].decode()
    if not old_prompt.startswith(TEXT_PROMPT + "\n\n"):
        raise ValueError("S2 source-specific feedback prompt changed")
    prompt = TEXT_PROMPT_V4 + old_prompt[len(TEXT_PROMPT) :]
    _bind_s1_resources(host, registry, prompt, canonical_json(code_identity()))
    schema = derive_reply_schema(host["payload"], conformance_v4=True)
    registry.files[schema.schema_sha256] = schema.schema_text.encode()
    host["payload"]["response_schema_sha256"] = schema.schema_sha256
    host["packet_sha256"] = sha256_bytes(canonical_json(host["payload"]))
    bundle = repository / "artifacts/ocr-live-readiness-20261028-01/images/S2/bundle.json"
    context = [("congressionalglo7392unit:716:par_000716_000019", "line_000716_000100")]
    host = prepare_source_scope(host, registry, bundle.read_bytes(), context)
    prompt = registry.files[host["payload"]["prompt_sha256"]].decode()
    projection, _schema = compile_request_projection(
        host, registry, prompt, MODEL_NAME, conformance_v4=True
    )
    if projection.body_sha256 != S2_BODY_SHA:
        raise ValueError("S2 differs from exact feedback-conditioned request")
    return host, projection, registry


def load_scoped_inputs(repository, spec):
    from congressional_globe import productive_ocr_measurement_scoped as scoped

    window = scoped.window(spec)
    if window in {"D1A", "D1W"}:
        from congressional_globe.productive_ocr_lean_audit import load_lean_inputs
        from congressional_globe.productive_ocr_whole_audit import load_whole_inputs

        loader = {"D1A": load_lean_inputs, "D1W": load_whole_inputs}[window]
        host, projection, registry = loader(repository)
        if projection.body_sha256 != scoped.authority(spec)[1]:
            raise ValueError("lean audit differs from the exact frozen request")
        return host, projection, registry
    if window in {"D1C", "D1L"}:
        from congressional_globe.productive_ocr_compact_measurement import load_compact_inputs

        return load_compact_inputs(repository)
    if window in {"D1", "D2"}:
        return load_audit_inputs(repository, window)
    loaders = {
        "S1": load_s1_scoped_inputs,
        "S2": load_s2_scoped_inputs,
        "S5": load_s5_scoped_inputs,
    }
    return loaders[window](repository)


def load_audit_inputs(repository: Path, unit: str):
    """Retain every original audit target, saved proposal and registered source byte."""
    from congressional_globe import productive_ocr_measurement_scoped as scoped
    from congressional_globe.productive_ocr_authority import MODEL_NAME
    from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
    from congressional_globe.productive_ocr_runner import code_identity

    expected = {"D1": scoped.D1_BODY_SHA, "D2": scoped.D2_BODY_SHA}[unit]
    root = repository / ASSEMBLY
    host = _json(root / unit / "host.json")
    registry = _registry(root, host, _json(root / "registry-index.json"))
    validate_host(host, registry)
    code = canonical_json(code_identity())
    host["payload"]["code_sha256"] = sha256_bytes(code)
    registry.files[sha256_bytes(code)] = code
    host["packet_sha256"] = sha256_bytes(canonical_json(host["payload"]))
    prompt = registry.files[host["payload"]["prompt_sha256"]].decode()
    projection, _schema = compile_request_projection(host, registry, prompt, MODEL_NAME)
    if projection.body_sha256 != expected:
        raise ValueError("audit differs from the exact original target/proposal request")
    return host, projection, registry
