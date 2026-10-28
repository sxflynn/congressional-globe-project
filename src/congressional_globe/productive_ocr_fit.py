"""Strict request-bound multimodal fit evidence gate; no token estimates from bytes."""

from __future__ import annotations

import io
import json
from typing import Annotated, Literal

from PIL import Image
from pydantic import Field

from congressional_globe.bracket_cues import Contract
from congressional_globe.productive_ocr_host import (
    EvidenceRegistry,
    canonical_json,
    sha256_bytes,
    validate_host,
)
from congressional_globe.productive_ocr_projection import (
    RequestProjection,
    compile_request_projection,
)
from congressional_globe.productive_ocr_runner import FrozenJob, TokenFit


class TileObservation(Contract):
    tile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    left: int = Field(ge=0)
    top: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    token_count: int = Field(ge=1)


class TokenIdTrace(Contract):
    contract: Literal["productive-ocr-native-token-id-trace-v1"]
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rendered_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tokenizer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    preprocessor_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    token_ids: tuple[Annotated[int, Field(ge=0)], ...] = Field(min_length=1, max_length=6000)


class ImageSchedule(Contract):
    image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    paragraph_aliases: tuple[str, ...] = Field(min_length=1, max_length=32)
    crop_regions: tuple[dict, ...] = Field(min_length=1, max_length=32)
    rendered_width: int = Field(ge=1)
    rendered_height: int = Field(ge=1)
    tiles: tuple[TileObservation, ...] = Field(min_length=1, max_length=256)
    image_tokens: int = Field(ge=1)


class NativeObservation(Contract):
    contract: Literal["productive-ocr-native-fit-observation-v1"]
    capture_method: Literal[
        "owned_backend_dry_run",
        "verified_offline_native_preprocessing",
        "owned_backend_completed_request",
    ]
    request_id: str = Field(min_length=1)
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    image_bindings_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_name: str = Field(min_length=1)
    model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    tokenizer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    preprocessor_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    renderer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rendered_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    token_id_trace_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text_tokens: int = Field(ge=1)
    image_tokens: int = Field(ge=1)
    input_tokens: int = Field(ge=1)
    output_token_limit: int = Field(ge=1, le=1500)
    observed_output_tokens: int | None = Field(default=None, ge=0, le=1500)
    image_schedule: tuple[ImageSchedule, ...] = Field(min_length=1, max_length=1)


class FitEvidence(Contract):
    contract: Literal["productive-ocr-complete-fit-v1"]
    evidence_scope: Literal["complete_native_backend"]
    request_projection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    host_packet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    image_bindings_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_name: str = Field(min_length=1)
    model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    tokenizer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    preprocessor_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    renderer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rendered_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    token_id_trace_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_layers_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    diagnostics_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    saved_proposal_sha256: str | None = Field(pattern=r"^[0-9a-f]{64}$")
    text_tokens: int = Field(ge=1)
    image_tokens: int = Field(ge=1)
    input_tokens: int = Field(ge=1, le=6000)
    output_token_limit: int = Field(ge=1, le=1500)
    observed_output_tokens: int | None = Field(default=None, ge=0, le=1500)
    native_observation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FitGate(Contract):
    contract: Literal["productive-ocr-fit-gate-v1"] = "productive-ocr-fit-gate-v1"
    ready: bool
    reason: str | None
    evidence_sha256: str | None
    evidence: FitEvidence | None


class PreparedOwnedJob(Contract):
    contract: Literal["productive-ocr-prepared-owned-job-v1"] = (
        "productive-ocr-prepared-owned-job-v1"
    )
    job: FrozenJob
    full_fit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    full_fit_record_json: str = Field(min_length=1)
    token_fit_record_json: str = Field(min_length=1)


def _registry_json(registry: EvidenceRegistry, digest: str, label: str) -> dict:
    data = registry.files.get(digest)
    if data is None or sha256_bytes(data) != digest:
        raise ValueError(f"{label} evidence bytes missing or changed")
    value = json.loads(data)
    if not isinstance(value, dict) or canonical_json(value) != data:
        raise ValueError(f"{label} evidence must be canonical JSON")
    return value


def _same_fit(fit: FitEvidence, observed: NativeObservation, projection: RequestProjection) -> None:
    pairs = _fit_projection_pairs(fit, projection) + _fit_observation_pairs(fit, observed)
    if any(left != right for left, right in pairs):
        raise ValueError("fit evidence does not match exact request or native observation")
    _check_output_capture(observed)


def _fit_projection_pairs(
    fit: FitEvidence, projection: RequestProjection
) -> tuple[tuple[object, object], ...]:
    return (
        (
            fit.request_projection_sha256,
            sha256_bytes(canonical_json(projection.model_dump(mode="json"))),
        ),
        (fit.host_packet_sha256, projection.host_packet_sha256),
        (fit.body_sha256, projection.body_sha256),
        (fit.model_name, projection.model_name),
        (fit.model_digest, projection.model_digest),
        (fit.source_layers_sha256, projection.source_layers_sha256),
        (fit.image_sha256, projection.image_sha256),
        (fit.diagnostics_sha256, projection.diagnostics_sha256),
        (fit.saved_proposal_sha256, projection.saved_proposal_sha256),
        (fit.output_token_limit, json.loads(projection.body_utf8)["options"]["num_predict"]),
    )


def _fit_observation_pairs(
    fit: FitEvidence, observed: NativeObservation
) -> tuple[tuple[object, object], ...]:
    return (
        (fit.tokenizer_sha256, observed.tokenizer_sha256),
        (fit.preprocessor_sha256, observed.preprocessor_sha256),
        (fit.renderer_sha256, observed.renderer_sha256),
        (fit.rendered_text_sha256, observed.rendered_text_sha256),
        (fit.token_id_trace_sha256, observed.token_id_trace_sha256),
        (fit.text_tokens, observed.text_tokens),
        (fit.image_tokens, observed.image_tokens),
        (fit.input_tokens, observed.input_tokens),
        (fit.output_token_limit, observed.output_token_limit),
        (fit.observed_output_tokens, observed.observed_output_tokens),
        (fit.body_sha256, observed.body_sha256),
        (fit.image_bindings_sha256, observed.image_bindings_sha256),
        (fit.model_name, observed.model_name),
        (fit.model_digest, observed.model_digest),
    )


def _check_output_capture(observed: NativeObservation) -> None:
    if observed.capture_method == "owned_backend_completed_request":
        if observed.observed_output_tokens is None:
            raise ValueError("completed request is missing observed output-token count")
        return
    if observed.observed_output_tokens is not None:
        raise ValueError("pre-inference fit evidence must not claim generated output tokens")


def _check_image_schedule(
    observed: NativeObservation, projection: RequestProjection, registry: EvidenceRegistry
) -> None:
    schedule = observed.image_schedule[0]
    _check_scheduled_regions(schedule, projection)
    _check_tile_resources(schedule, registry)
    if sum(tile.token_count for tile in schedule.tiles) != observed.image_tokens:
        raise ValueError("native image token schedule does not sum to observed image count")


def _check_scheduled_regions(schedule: ImageSchedule, projection: RequestProjection) -> None:
    expected = json.loads(projection.image_bindings_json)
    aliases = tuple(item["paragraph_alias"] for item in expected)
    crops = tuple(item["crop_region"] for item in expected)
    _require_schedule_binding(schedule, projection, aliases, crops)
    _require_tile_sum(schedule)


def _require_schedule_binding(
    schedule: ImageSchedule,
    projection: RequestProjection,
    aliases: tuple[str, ...],
    crops: tuple[dict, ...],
) -> None:
    if schedule.image_sha256 != projection.image_sha256:
        raise ValueError("native image schedule does not bind the frozen image")
    if schedule.paragraph_aliases != aliases or schedule.crop_regions != crops:
        raise ValueError("native image schedule differs from frozen paragraph geometry")


def _require_tile_sum(schedule: ImageSchedule) -> None:
    if sum(tile.token_count for tile in schedule.tiles) != schedule.image_tokens:
        raise ValueError("native tile-token counts do not equal image-token count")


def _check_tile_resources(schedule: ImageSchedule, registry: EvidenceRegistry) -> None:
    for tile in schedule.tiles:
        _check_one_tile(tile, schedule, registry)


def _check_one_tile(
    tile: TileObservation, schedule: ImageSchedule, registry: EvidenceRegistry
) -> None:
    data = _registered_tile_bytes(tile, registry)
    _check_tile_bounds(tile, schedule)
    dimensions = _tile_dimensions(data)
    if dimensions != (tile.width, tile.height):
        raise ValueError("native tile bytes disagree with observed tile dimensions")


def _registered_tile_bytes(tile: TileObservation, registry: EvidenceRegistry) -> bytes:
    data = registry.files.get(tile.tile_sha256)
    if data is None or sha256_bytes(data) != tile.tile_sha256:
        raise ValueError("native rendered tile bytes missing or changed")
    return data


def _check_tile_bounds(tile: TileObservation, schedule: ImageSchedule) -> None:
    if (
        tile.left + tile.width > schedule.rendered_width
        or tile.top + tile.height > schedule.rendered_height
    ):
        raise ValueError("native tile geometry exceeds rendered image dimensions")


def _tile_dimensions(data: bytes) -> tuple[int, int]:
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            dimensions = image.size
    except Exception as exc:
        raise ValueError("native tile evidence is not a decodable image") from exc
    return dimensions


def _check_resources(fit: FitEvidence, registry: EvidenceRegistry) -> None:
    for digest, label in (
        (fit.tokenizer_sha256, "tokenizer"),
        (fit.preprocessor_sha256, "preprocessor"),
        (fit.renderer_sha256, "renderer"),
    ):
        content = registry.files.get(digest)
        if content is None or sha256_bytes(content) != digest:
            raise ValueError(f"pinned {label} resource missing or changed")


def _check_token_trace(
    fit: FitEvidence,
    observed: NativeObservation,
    projection: RequestProjection,
    registry: EvidenceRegistry,
) -> None:
    rendered = registry.files.get(fit.rendered_text_sha256)
    if rendered is None or sha256_bytes(rendered) != fit.rendered_text_sha256:
        raise ValueError("exact native rendered-text bytes missing or changed")
    try:
        rendered.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("native rendered-text bytes are not exact UTF-8") from exc
    trace_dict = _registry_json(registry, fit.token_id_trace_sha256, "native token-id trace")
    trace = TokenIdTrace.model_validate_json(canonical_json(trace_dict))
    expected = (
        trace.body_sha256 == projection.body_sha256,
        trace.rendered_text_sha256 == fit.rendered_text_sha256,
        trace.tokenizer_sha256 == fit.tokenizer_sha256,
        trace.preprocessor_sha256 == fit.preprocessor_sha256,
        len(trace.token_ids) == fit.text_tokens == observed.text_tokens,
    )
    if not all(expected):
        raise ValueError("native token-id trace does not match exact request or text count")


def _parse_fit_evidence(text: str) -> FitEvidence:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("fit evidence must be a JSON object")
    missing = sorted(set(FitEvidence.model_fields) - value.keys())
    if missing:
        raise ValueError(
            "incomplete multimodal fit evidence; missing fields: " + ", ".join(missing)
        )
    return FitEvidence.model_validate(value)


def inspect_fit_evidence(
    projection: RequestProjection,
    fit_evidence_json: str,
    registry: EvidenceRegistry,
) -> FitGate:
    """Reject text-only counters; require exact body, source layers and native image trace."""
    try:
        fit = _parse_fit_evidence(fit_evidence_json)
        evidence_bytes = canonical_json(fit.model_dump(mode="json"))
        evidence_sha = sha256_bytes(evidence_bytes)
        if registry.files.get(evidence_sha) != evidence_bytes:
            raise ValueError("full-fit evidence is not registered by exact canonical bytes")
        observation = _registry_json(
            registry, fit.native_observation_sha256, "native multimodal observation"
        )
        native = NativeObservation.model_validate_json(canonical_json(observation))
        _check_resources(fit, registry)
        _same_fit(fit, native, projection)
        _check_token_trace(fit, native, projection, registry)
        if fit.input_tokens != fit.text_tokens + fit.image_tokens:
            raise ValueError("complete input tokens must equal measured text plus image tokens")
        if fit.input_tokens > 6000 or fit.output_token_limit > 1500:
            raise ValueError("complete request exceeds frozen token ceilings")
        _check_image_schedule(native, projection, registry)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        return FitGate(ready=False, reason=str(error)[:1000], evidence_sha256=None, evidence=None)
    return FitGate(ready=True, reason=None, evidence_sha256=evidence_sha, evidence=fit)


def _projection_from_job(job: FrozenJob, registry: EvidenceRegistry) -> RequestProjection:
    host = validate_host(job.host, registry)
    body_sha = sha256_bytes(job.body_utf8.encode("utf-8"))
    body = json.loads(job.body_utf8)
    prompt = body["messages"][0]["content"]
    projection, _schema = compile_request_projection(
        host, registry, prompt, body["model"], body["options"]["num_predict"]
    )
    if projection.body_sha256 != body_sha:
        raise ValueError("FrozenJob body differs from exact production projection")
    return projection


def require_complete_fit(prepared: PreparedOwnedJob, registry: EvidenceRegistry) -> FitEvidence:
    """Require the exact registered native-fit artifact for a prepared frozen job."""
    job = prepared.job
    full_fit_sha = prepared.full_fit_sha256
    raw = registry.files.get(full_fit_sha)
    if raw is None or sha256_bytes(raw) != full_fit_sha:
        raise ValueError("complete native multimodal fit evidence bytes missing or changed")
    projection = _projection_from_job(job, registry)
    gate = inspect_fit_evidence(projection, raw.decode("utf-8"), registry)
    if not gate.ready or gate.evidence is None or gate.evidence_sha256 != full_fit_sha:
        raise ValueError(gate.reason or "complete native multimodal fit evidence is required")
    return gate.evidence


def prepare_owned_job(
    projection: RequestProjection,
    host: dict,
    registry: EvidenceRegistry,
    fit_evidence_json: str,
) -> PreparedOwnedJob:
    """Build runner-compatible FrozenJob only after complete fit evidence passes."""
    gate = inspect_fit_evidence(projection, fit_evidence_json, registry)
    if not gate.ready or gate.evidence is None or gate.evidence_sha256 is None:
        raise ValueError(gate.reason or "complete native multimodal fit evidence is required")
    fit, full_fit_sha = gate.evidence, gate.evidence_sha256
    token_fit_json = canonical_json(
        TokenFit(
            model_name=fit.model_name,
            body_sha256=fit.body_sha256,
            model_digest=fit.model_digest,
            input_tokens=fit.input_tokens,
            output_tokens=fit.output_token_limit,
            evidence_scope="actual_tokenizer",
        ).model_dump(mode="json")
    ).decode("utf-8")
    token_fit_sha = sha256_bytes(token_fit_json.encode("utf-8"))
    job = FrozenJob(
        window_id=host["payload"]["unit_id"],
        host=host,
        body_utf8=projection.body_utf8,
        body_sha256=projection.body_sha256,
        input_tokens=fit.input_tokens,
        token_fit_sha256=token_fit_sha,
    )
    fit_record_json = canonical_json(fit.model_dump(mode="json")).decode("utf-8")
    return PreparedOwnedJob(
        job=job,
        full_fit_sha256=full_fit_sha,
        full_fit_record_json=fit_record_json,
        token_fit_record_json=token_fit_json,
    )
