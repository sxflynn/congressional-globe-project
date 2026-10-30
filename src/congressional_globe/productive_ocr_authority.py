"""Narrow recorded first-chunk authority; engineering fixtures cannot grant real dispatch."""

import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from congressional_globe.bracket_cues import Contract
from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
from congressional_globe.scan_models import Sha256

APPROVAL_SHA256 = "34282bb2d794569ab4458051891adb107650b2aa952dac44968f5829a5214593"
SAMPLE_SHA256 = "9ad0e2789e28ce29d3d8ec20a52a3a54b2859b4b38d6629c806e72746f3fb7f0"
MODEL_NAME = "qwen3.8:27b-mlx"
MODEL_DIGEST = "5642e97495e1a088883805981563dcdc4a040c2f53388b7a41d1f24d3622cf7e"
# Deliberately absent while T55 is blocked. A future reviewed readiness unit must
# pin its verified clearance here; a caller registry cannot grant launch authority.
TRUSTED_T55_CLEARANCE_SHA256: str | None = None
SIMULATION_BLOB = b"synthetic model bytes; not weights and never loaded"


class LaunchClearance(Contract):
    contract: Literal["productive-ocr-t55-clearance-v1"]
    task_id: Literal["T55"]
    authorization_sha256: Sha256
    sample_binding_sha256: Sha256
    jobs_sha256: Sha256
    backend_plan_sha256: Sha256
    resolved_conditions: tuple[Literal["R1", "R2", "R3", "R4"], ...] = Field(
        min_length=4, max_length=4
    )
    unresolved_conditions: tuple[str, ...] = Field(max_length=0)
    condition_evidence: dict[Literal["R1", "R2", "R3", "R4"], Sha256]


def registered(registry, digest):
    data = registry.files.get(digest)
    if data is None or sha256_bytes(data) != digest:
        raise ValueError("recorded authority/readiness evidence missing or changed")
    return data


def verify_real_authority(readiness, prepared, client, registry, authorization_sha):
    _require_v2_live_mode(prepared)
    if authorization_sha != APPROVAL_SHA256:
        raise ValueError("real execution requires the recorded human approval scope")
    registered(registry, APPROVAL_SHA256)
    if readiness.execution_profile != "approved_first_chunk":
        raise ValueError("simulation readiness cannot authorize real execution")
    if readiness.clearance_sha256 is None:
        raise ValueError("T55 has no recorded launch clearance; blocked conditions remain")
    _verify_trusted_clearance(readiness.clearance_sha256)
    _verify_real_model(client)
    sample = json.loads(registered(registry, SAMPLE_SHA256))
    _verify_selected_scope(sample, prepared, registry)
    clearance = LaunchClearance.model_validate_json(
        registered(registry, readiness.clearance_sha256)
    )
    _verify_clearance(clearance, readiness, registry)
    _verify_native_resources(prepared, client, registry)


def _verify_trusted_clearance(digest):
    if TRUSTED_T55_CLEARANCE_SHA256 is None or digest != TRUSTED_T55_CLEARANCE_SHA256:
        raise ValueError(
            "T55 has no independently pinned ready clearance; "
            "caller assertions cannot clear blockers"
        )


def _verify_real_model(client):
    if (client.plan.model_name, client.plan.model_digest) != (MODEL_NAME, MODEL_DIGEST):
        raise ValueError("real backend differs from the approved installed model")


def _verify_selected_scope(sample, prepared, registry):
    sequence = sample["fixed_request_sequence"]
    expected = tuple((r["unit_id"], r["role"]) for r in sequence)
    actual = tuple((p.job.window_id, p.job.host["payload"]["role"]) for p in prepared)
    if actual != expected or len(prepared) != 7:
        raise ValueError("real readiness must include the exact approved seven-unit sequence")
    for unit, item in zip(sample["units"], prepared, strict=True):
        _verify_unit_sources(unit, item.job.host["payload"], registry)


def _verify_unit_sources(unit, payload, registry):
    targets = [r for r in payload["paragraphs"] if r["role"] == "target"]
    actual = tuple((r["source_id"], r["raw"]["sha256"], r["static"]["sha256"]) for r in targets)
    if actual != _expected_sources(unit, registry):
        raise ValueError("real request substitutes or omits an approved source target")
    _verify_saved_image(unit, payload)


def _expected_sources(unit, registry):
    if "source_id" in unit:
        return ((unit["source_id"], unit["raw_sha256"], unit["static_sha256"]),)
    reference = unit["fixture_ref"]
    fixtures = json.loads(registered(registry, reference["sha256"]))
    case = next(row for row in fixtures["cases"] if row["id"] == reference["case_id"])
    return tuple(_fixture_source(row) for row in case["candidate"]["target"])


def _fixture_source(row):
    identity = f"{row['item_identifier']}:{row['scan_leaf']}:{row['paragraph_id']}"
    return identity, row["raw_sha256"], row["static_sha256"]


def _verify_saved_image(unit, payload):
    if "image_bindings_as_recorded" not in unit:
        return
    if payload["image"]["sha256"] != unit["image_bindings_as_recorded"][0]["sha256"]:
        raise ValueError("saved-failure image differs from the approved frozen comparison")


def _verify_clearance(clearance, readiness, registry):
    jobs = [job.model_dump(mode="json") for job in readiness.jobs]
    expected = (
        APPROVAL_SHA256,
        SAMPLE_SHA256,
        sha256_bytes(canonical_json(jobs)),
        readiness.backend_plan_sha256,
    )
    actual = (
        clearance.authorization_sha256,
        clearance.sample_binding_sha256,
        clearance.jobs_sha256,
        clearance.backend_plan_sha256,
    )
    if actual != expected:
        raise ValueError("T55 clearance does not bind the approved sample/jobs/backend")
    conditions = {"R1", "R2", "R3", "R4"}
    if (
        set(clearance.resolved_conditions) != conditions
        or set(clearance.condition_evidence) != conditions
    ):
        raise ValueError("T55 clearance has missing or duplicate blocker dispositions")
    for digest in clearance.condition_evidence.values():
        registered(registry, digest)


def _verify_native_resources(prepared, client, registry):
    from congressional_globe.productive_ocr_fit import require_complete_fit

    manifest = json.loads(registered(registry, MODEL_DIGEST))
    layers = {part.get("name"): part for part in manifest["layers"]}
    expected = (
        layers["tokenizer.json"]["digest"].removeprefix("sha256:"),
        layers["preprocessor_config.json"]["digest"].removeprefix("sha256:"),
        client.plan.executable_sha256,
    )
    for item in prepared:
        fit = require_complete_fit(item, registry)
        if (fit.tokenizer_sha256, fit.preprocessor_sha256, fit.renderer_sha256) != expected:
            raise ValueError("native fit resources do not match the actual selected model/backend")


def verify_simulation(readiness, client):
    """Check toy-store identity, not arbitrary executable safety.

    This is an explicit engineering test hook for inspected fixture executables.
    It does not authorize running untrusted code or certify executable behavior.
    """
    if (
        readiness.execution_profile != "synthetic_http_fixture"
        or readiness.clearance_sha256 is not None
    ):
        raise ValueError("simulation must use its explicit fixture profile, never real clearance")
    if not client.plan.model_name.startswith("fake:"):
        raise ValueError("simulation cannot select a real model tag")
    if not Path(client.plan.executable).name.startswith("fake-"):
        raise ValueError("simulation requires an explicit fake server executable")
    _verify_simulation_blobs(client.plan)


def _verify_simulation_blobs(plan):
    manifest = json.loads(Path(plan.model_manifest).read_bytes())
    parts = [manifest["config"], *manifest["layers"]]
    if len(parts) > 4:
        raise ValueError("simulation store contains unexpected model resources")
    for part in parts:
        path = Path(plan.model_store) / "blobs" / part["digest"].replace(":", "-")
        if path.stat().st_size != len(SIMULATION_BLOB) or path.read_bytes() != SIMULATION_BLOB:
            raise ValueError("simulation store contains real or unrecognized model data")


def _require_v2_live_mode(prepared):
    for item in prepared:
        if item.job.host["payload"]["contract"] == "ocr-productive-repair-host-input-v3":
            raise ValueError("text v3 mode is offline only; requires separate live authority")
