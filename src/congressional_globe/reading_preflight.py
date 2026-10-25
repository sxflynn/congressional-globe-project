"""Fail-closed, offline preflight for the frozen holistic reading pilot.

This module reads saved identity evidence and frozen inputs only. It never
contacts Ollama and never estimates model tokens from characters, words, or
image bytes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
PREPARATION = REPO_ROOT / "artifacts/reading-prepare-20261024-03"
RUNTIME_EVIDENCE = REPO_ROOT / "artifacts/vision-probe-20261024-01"
OUTPUT_DIRECTORY = REPO_ROOT / "artifacts/reading-preflight-20261024-01"

SUPPORTED_MODELS = {
    "qwen3.8:27b-mlx": "5642e97495e1a088883805981563dcdc4a040c2f53388b7a41d1f24d3622cf7e",
    "gemma4:31b-mlx": "637cc0ff15709212de4aa694be67e3af5e80533ca538c86ad69c53c511e40840",
    "muse-glimmer:30b-mlx": "015fa21845bead56096c2f8773aff7a2047063507fe82897e662ad544c5b2fa6",
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_record(path: Path) -> dict[str, str | int]:
    payload = path.read_bytes()
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "sha256": _sha(payload),
        "bytes": len(payload),
    }


class FrozenInputs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_file: dict[str, str | int]
    prompt_file: dict[str, str | int]
    reply_schema_file: dict[str, str | int]
    candidate_count: int = Field(ge=1)
    primary_count: int = Field(ge=0)
    confirmation_count: int = Field(ge=0)
    primary_word_count: int = Field(ge=0)
    candidate_ids: list[str]


class RuntimeEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    digest: str | None
    runner: str | None
    capabilities: list[str]
    runtime_version: str | None
    model_context_limit: int | None
    prior_probe_config: dict[str, str | int | bool]
    prior_loaded_models: list[dict[str, object]]
    prior_ps_snapshot_sha256: str
    snapshot_file: str
    snapshot_sha256: str
    evidence_age: Literal["current_snapshot", "historical_snapshot"]
    current_loaded_models: list[dict[str, object]]
    current_ps_snapshot_sha256: str
    runtime_evidence_files: dict[str, str]
    process_observation: dict[str, object]


class TokenFitEvidence(BaseModel):
    """Actual counts for the exact assembled request, never a heuristic estimate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text_tokens: int = Field(ge=0)
    image_tokens: int = Field(ge=0)
    output_reserve_tokens: int = Field(gt=0)
    requested_context_tokens: int = Field(gt=0)
    method: Literal["local_model_tokenizer_processor", "documented_tokenize_endpoint"]
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ModelAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    expected_digest: str | None
    observed_digest: str | None
    runner: str | None
    capabilities: list[str]
    runtime_version: str | None
    model_context_limit: int | None
    prior_probe_config: dict[str, str | int | bool]
    prior_loaded_models: list[dict[str, object]]
    prior_ps_snapshot_sha256: str
    text_tokens: int | None = None
    image_tokens: int | None = None
    token_fit_status: Literal["unknown", "fits", "exceeds"] = "unknown"
    runtime_state: Literal["idle", "busy", "unknown"]
    current_loaded_models: list[dict[str, object]]
    current_ps_snapshot_sha256: str
    runtime_evidence_files: dict[str, str]
    process_observation: dict[str, object]
    launch_ready: bool = False
    blockers: list[str]
    source_snapshot: str
    source_snapshot_sha256: str


class ReadingPreflightReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["reading-preflight-v1"] = "reading-preflight-v1"
    status: Literal["blocked"] = "blocked"
    created_utc: str
    process_inspection: dict[str, str]
    runtime_api_calls: int = 6
    inference_calls: int = 0
    warmup_calls: int = 0
    downloads: int = 0
    frozen_inputs: FrozenInputs
    tokenizer_finding: str
    tokenizer_assets: list[dict[str, str | int | bool]]
    image_evidence: dict[str, object]
    supported_models: list[ModelAssessment]
    launch_ready: bool = False
    global_blockers: list[str]


def _read_runtime_snapshot(model: str) -> RuntimeEvidence:
    folder = _runtime_folder(model)
    base = RUNTIME_EVIDENCE / folder
    files = _runtime_files(model, base)
    historical_summary = json.loads((base / "preflight.json").read_text(encoding="utf-8"))
    values = _read_runtime_values(model, files, base, historical_summary)
    return RuntimeEvidence(
        model=model,
        digest=values["digest"],
        runner=values["runner"],
        capabilities=values["capabilities"],
        runtime_version=values["runtime_version"],
        model_context_limit=values["model_context_limit"],
        prior_probe_config=values["prior_probe_config"],
        prior_loaded_models=values["prior_loaded_models"],
        prior_ps_snapshot_sha256=values["prior_ps_snapshot_sha256"],
        snapshot_file=values["snapshot_file"],
        snapshot_sha256=values["snapshot_sha256"],
        evidence_age=values["evidence_age"],
        current_loaded_models=values["current_loaded_models"],
        current_ps_snapshot_sha256=values["current_ps_snapshot_sha256"],
        runtime_evidence_files=values["runtime_evidence_files"],
        process_observation=values["process_observation"],
    )


def _runtime_folder(model: str) -> str:
    return {
        "qwen3.8:27b-mlx": "qwen-json",
        "gemma4:31b-mlx": "gemma-json",
        "muse-glimmer:30b-mlx": "muse-json",
    }[model]


def _runtime_files(model: str, base: Path) -> dict[str, Path | str]:
    current = OUTPUT_DIRECTORY / "current-runtime"
    current_tags_path = current / "tags.json"
    current_version_path = current / "version.json"
    current_ps_path = current / "ps.json"
    current_show_path = current / f"show-{model.replace(':', '-')}.json"
    current_files = [current_tags_path, current_version_path, current_ps_path, current_show_path]
    current_complete = all(path.exists() for path in current_files)
    if current_complete:
        tags_path, version_path, ps_path, show_path = current_files
        evidence_age = "current_snapshot"
    else:
        tags_path = base / "preflight/tags.json"
        version_path = base / "preflight/version.json"
        ps_path = base / "preflight/ps.json"
        show_path = base / "preflight/show.json"
        evidence_age = "historical_snapshot"
    return {
        "base": base,
        "current": current,
        "tags": tags_path,
        "version": version_path,
        "ps": ps_path,
        "show": show_path,
        "evidence_age": evidence_age,
    }


def _read_runtime_values(
    model: str, files: dict[str, Path | str], base: Path, historical_summary: dict
) -> dict:
    tags_path = files["tags"]
    version_path = files["version"]
    ps_path = files["ps"]
    show_path = files["show"]
    current = files["current"]
    assert isinstance(tags_path, Path) and isinstance(version_path, Path)
    assert isinstance(ps_path, Path) and isinstance(show_path, Path) and isinstance(current, Path)
    show = _read_json(show_path)
    version = _read_json(version_path)
    tags = _read_json(tags_path)
    ps = _read_json(ps_path)
    historical_ps = json.loads((base / "preflight/ps.json").read_text(encoding="utf-8"))
    result = _snapshot_values(
        model, show, version, tags, ps, historical_summary, files["evidence_age"]
    )
    result.update(_snapshot_files(files, base, historical_ps))
    return result


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _matching_tag(model: str, tags: dict) -> dict:
    return next(
        (
            item
            for item in tags.get("models", [])
            if item.get("name") == model or item.get("model") == model
        ),
        {},
    )


def _context_length(show: dict) -> int | None:
    values = [
        value
        for key, value in show.get("model_info", {}).items()
        if key.endswith(".context_length") and isinstance(value, int)
    ]
    return values[0] if values else None


def _snapshot_values(model, show, version, tags, ps, historical_summary, evidence_age) -> dict:
    tag = _matching_tag(model, tags)
    current = _current_snapshot_values(tag, show, version, ps)
    if evidence_age == "current_snapshot":
        return current
    return _historical_snapshot_fallback(current, historical_summary)


def _current_snapshot_values(tag, show, version, ps) -> dict:
    return {
        "digest": tag.get("digest"),
        "runner": (tag.get("details") or {}).get("runner"),
        "capabilities": show.get("capabilities", []),
        "runtime_version": version.get("version"),
        "model_context_limit": _context_length(show),
        "current_loaded_models": ps.get("models", []),
    }


def _historical_snapshot_fallback(values: dict, summary: dict) -> dict:
    values["digest"] = values["digest"] or summary.get("digest")
    values["runner"] = values["runner"] or summary.get("runner")
    values["capabilities"] = values["capabilities"] or summary.get("capabilities", [])
    values["runtime_version"] = values["runtime_version"] or summary.get("version")
    return values


def _snapshot_files(files, base, historical_ps) -> dict:
    tags_path = files["tags"]
    version_path = files["version"]
    ps_path = files["ps"]
    show_path = files["show"]
    current = files["current"]
    assert isinstance(tags_path, Path) and isinstance(version_path, Path)
    assert isinstance(ps_path, Path) and isinstance(show_path, Path) and isinstance(current, Path)
    process_path = current / "process-observation.json"
    return {
        "prior_probe_config": json.loads((base / "manifest.json").read_text(encoding="utf-8")).get(
            "config", {}
        ),
        "prior_loaded_models": historical_ps.get("models", []),
        "prior_ps_snapshot_sha256": _sha((base / "preflight/ps.json").read_bytes()),
        "snapshot_file": str(show_path.relative_to(REPO_ROOT)),
        "snapshot_sha256": _sha(show_path.read_bytes()),
        "evidence_age": files["evidence_age"],
        "current_ps_snapshot_sha256": _sha(ps_path.read_bytes()),
        "runtime_evidence_files": {
            str(path.relative_to(REPO_ROOT)): _sha(path.read_bytes())
            for path in [tags_path, version_path, ps_path, show_path]
        },
        "process_observation": _read_json(process_path)
        if files["evidence_age"] == "current_snapshot" and process_path.exists()
        else {},
    }


def _assess(
    runtime: RuntimeEvidence,
    token_fit: TokenFitEvidence | None = None,
) -> ModelAssessment:
    expected = SUPPORTED_MODELS.get(runtime.model)
    runtime_state = _runtime_state(runtime)
    fit_status, fit_blockers = _token_fit_status(runtime, token_fit)
    blockers = _identity_blockers(runtime, expected)
    blockers.extend(_runtime_blockers(runtime, runtime_state))
    blockers.extend(fit_blockers)
    blockers.extend(_pending_blockers())
    return ModelAssessment(
        model=runtime.model,
        expected_digest=expected,
        observed_digest=runtime.digest,
        runner=runtime.runner,
        capabilities=runtime.capabilities,
        runtime_version=runtime.runtime_version,
        model_context_limit=runtime.model_context_limit,
        prior_probe_config=runtime.prior_probe_config,
        prior_loaded_models=runtime.prior_loaded_models,
        prior_ps_snapshot_sha256=runtime.prior_ps_snapshot_sha256,
        runtime_state=runtime_state,
        current_loaded_models=runtime.current_loaded_models,
        current_ps_snapshot_sha256=runtime.current_ps_snapshot_sha256,
        runtime_evidence_files=runtime.runtime_evidence_files,
        process_observation=runtime.process_observation,
        text_tokens=token_fit.text_tokens if token_fit else None,
        image_tokens=token_fit.image_tokens if token_fit else None,
        token_fit_status=fit_status,
        launch_ready=False,
        blockers=blockers,
        source_snapshot=runtime.snapshot_file,
        source_snapshot_sha256=runtime.snapshot_sha256,
    )


def _identity_blockers(runtime: RuntimeEvidence, expected: str | None) -> list[str]:
    blockers = []
    if expected is None:
        blockers.append("unsupported_model")
    if not runtime.digest:
        blockers.append("missing_exact_digest")
    elif expected and runtime.digest != expected:
        blockers.append("exact_digest_mismatch")
    if "vision" not in runtime.capabilities:
        blockers.append("image_capability_absent")
    return blockers


def _runtime_state(runtime: RuntimeEvidence) -> Literal["idle", "busy", "unknown"]:
    if runtime.evidence_age == "current_snapshot" and not runtime.current_loaded_models:
        return "idle"
    return "unknown"


def _runtime_blockers(
    runtime: RuntimeEvidence, runtime_state: Literal["idle", "busy", "unknown"]
) -> list[str]:
    blockers = []
    if runtime.runner != "mlx":
        blockers.append("expected_mlx_runner_unconfirmed")
    if runtime.model_context_limit is None:
        blockers.append("context_limit_unconfirmed")
    if runtime_state != "idle":
        blockers.append("current_runtime_state_unknown")
    return blockers


def _token_fit_status(
    runtime: RuntimeEvidence, token_fit: TokenFitEvidence | None
) -> tuple[Literal["unknown", "fits", "exceeds"], list[str]]:
    if token_fit is None:
        return "unknown", ["exact_text_token_fit_unknown", "image_token_fit_unknown"]
    if runtime.model_context_limit is None:
        return "unknown", ["context_limit_unconfirmed"]
    if token_fit.requested_context_tokens > runtime.model_context_limit:
        return "exceeds", ["requested_context_exceeds_model_limit"]
    total = token_fit.text_tokens + token_fit.image_tokens + token_fit.output_reserve_tokens
    if total > token_fit.requested_context_tokens:
        return "exceeds", ["measured_request_exceeds_requested_context"]
    return "fits", []


def _pending_blockers() -> list[str]:
    return ["source_expectations_and_human_review_effort_pending"]


def build_report(created_utc: str) -> ReadingPreflightReport:
    """Build a report from frozen files and saved snapshots; perform no I/O to services."""
    return ReadingPreflightReport(
        created_utc=created_utc,
        process_inspection=_process_inspection(),
        frozen_inputs=_frozen_inputs(),
        tokenizer_finding=_tokenizer_finding(),
        tokenizer_assets=_tokenizer_assets(),
        image_evidence=_image_evidence(),
        supported_models=[_assess(_read_runtime_snapshot(model)) for model in SUPPORTED_MODELS],
        global_blockers=[
            "live_process_and_queue_observation_must_be_rechecked_before_model_execution",
            "exact_per_unit_text_and_image_token_fit_unknown_for_every_model",
            "source_expectations_and_human_review_effort_pending",
        ],
    )


def _image_evidence() -> dict[str, object]:
    directory = REPO_ROOT / "artifacts/reading-images-20261024-01"
    index_path = directory / "index.json"
    proof_path = directory / "coverage-proof.json"
    index_bytes = index_path.read_bytes()
    proof_bytes = proof_path.read_bytes()
    index = json.loads(index_bytes)
    proof = json.loads(proof_bytes)
    index_hash = _sha(index_bytes)
    proof_matches = proof.get("index_sha256") == index_hash
    counts_match = (
        proof.get("primary_units") == index.get("primary_units") == 18
        and proof.get("images") == index.get("plans") == 19
    )
    no_provider_calls = proof.get("provider_calls") == index.get("provider_calls") == 0
    return {
        "index_path": str(index_path.relative_to(REPO_ROOT)),
        "index_sha256": index_hash,
        "coverage_proof_path": str(proof_path.relative_to(REPO_ROOT)),
        "coverage_proof_sha256": _sha(proof_bytes),
        "coverage_proof_index_sha256": proof.get("index_sha256"),
        "proof_matches_index": proof_matches,
        "counts_match": counts_match,
        "no_provider_calls": no_provider_calls,
        "primary_units": index.get("primary_units"),
        "images": index.get("plans"),
        "total_transfer_bytes": index.get("total_transfer_bytes"),
        "provider_calls": proof.get("provider_calls"),
        "geometry_coverage_complete": proof_matches
        and counts_match
        and no_provider_calls
        and proof.get("geometry_coverage_complete") is True,
    }


def _frozen_inputs() -> FrozenInputs:
    rows = _candidate_rows()
    primary_count, confirmation_count = _candidate_split_counts(rows)
    word_count = json.loads((PREPARATION / "manifest.json").read_text(encoding="utf-8"))[
        "primary_word_count"
    ]
    return FrozenInputs(
        candidate_file=_file_record(PREPARATION / "candidates.jsonl"),
        prompt_file=_file_record(PREPARATION / "prompt.txt"),
        reply_schema_file=_file_record(PREPARATION / "reply.schema.json"),
        candidate_count=len(rows),
        primary_count=primary_count,
        confirmation_count=confirmation_count,
        primary_word_count=word_count,
        candidate_ids=[row["id"] for row in rows],
    )


def _candidate_rows() -> list[dict]:
    return [
        json.loads(line)
        for line in (PREPARATION / "candidates.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _candidate_split_counts(rows: list[dict]) -> tuple[int, int]:
    primary = sum(row.get("split") == "primary" for row in rows)
    confirmation = sum(row.get("split") == "confirmation" for row in rows)
    return primary, confirmation


def _process_inspection() -> dict[str, str]:
    return {
        "status": "confirmed",
        "method": "ps -axo pid,lstart,etime,command (elevated)",
        "result": "Ollama PID 87597; no cleanup, reading, vision, or role worker; /api/ps empty.",
    }


def _tokenizer_assets() -> list[dict[str, str | int | bool]]:
    assets_path = OUTPUT_DIRECTORY / "current-runtime/model-assets.json"
    return json.loads(assets_path.read_text(encoding="utf-8"))["assets"]


def _tokenizer_finding() -> str:
    return (
        "Ollama manifests include model-specific tokenizer.json/config assets and Qwen's "
        "preprocessor config. The installed binary contains internal MLX tokenizer code. "
        "Installed Python lacks `tokenizers`, `transformers`, `mlx`, and `sentencepiece`. "
        "Binary strings expose an internal runner POST /v1/tokenize route, but it is not "
        "documented as a public Ollama endpoint; its load/state semantics are not established. "
        "No tokenizer-only request was made. No documented no-inference path for full "
        "chat-plus-image fit was verified. Actual text and image token fit remain unknown."
    )


def write_report(path: Path = OUTPUT_DIRECTORY, created_utc: str = "unknown") -> Path:
    """Write the typed offline report to a caller-selected owned artifact path."""
    path.mkdir(parents=True, exist_ok=True)
    destination = path / "report.json"
    destination.write_text(
        build_report(created_utc).model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return destination
