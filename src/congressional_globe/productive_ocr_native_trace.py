"""Strict v2 contract for an actual native preprocessing trace; no launch clearance.

T70's v1 fit contract assumed decodable JPEG tiles plus a text-only token count.
T71 found that the installed backend instead prepares float32 patch rows, a grid
shape and positional layout, and expands image boundary/pad tokens into the
request stream. This module supplies the separately versioned v2 representation
and an explicit producer/export boundary. No authentic producer exists yet and
no synthetic trace here becomes native truth or launch readiness.

Contract semantics: `rendered_text` is the exact textual byte stream after any
image placeholder substitution; it is tiled exactly by the text segments, while
the media segment carries the expanded image boundary/pad token run. A debug
request is separate bytes and must bind a registered deterministic transform of
the intended study body.
"""

from __future__ import annotations

import json
import math
import sys
from array import array
from dataclasses import dataclass
from typing import Annotated, Literal, NoReturn, Protocol

from pydantic import Field, model_validator

from congressional_globe.bracket_cues import Contract
from congressional_globe.productive_ocr_host import (
    EvidenceRegistry,
    canonical_json,
    sha256_bytes,
)
from congressional_globe.productive_ocr_projection import RequestProjection

TRACE_CONTRACT = "productive-ocr-native-fit-trace-v2"
MAX_INPUT_TOKENS = 6000
MAX_OUTPUT_TOKENS = 1500
MAX_SEGMENTS = 64
MAX_PATCH_ELEMENTS = 16_777_216
MAX_POSITION_BYTES = 4 * 4 * MAX_INPUT_TOKENS
FLOAT32_BYTES = 4

BASE_BLOCKERS = (
    "no authentic complete native preprocessing producer/export is implemented",
    "exact installed dirty-build parity is unproved",
    "trusted T55 launch clearance is absent",
    "actual selected backend stopping and compatibility are unproved",
)
FIXTURE_BLOCKER = "trace is an authored fixture, not native backend output"
CAPTURE_BLOCKER = "capture claim is self-asserted, not independently attested"
OWNED_CAPTURE_BLOCKER = "owned capture bytes still need independent readiness review"

Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class StreamSegment(Contract):
    index: int = Field(ge=0, lt=MAX_SEGMENTS)
    kind: Literal["text", "media"]
    token_ids: tuple[Annotated[int, Field(ge=0, lt=2**32)], ...] = Field(
        min_length=1, max_length=MAX_INPUT_TOKENS
    )
    text_start: int | None = Field(default=None, ge=0)
    text_end: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _span_matches_kind(self) -> StreamSegment:
        has_span = self.text_start is not None and self.text_end is not None
        if (self.kind == "text") != has_span:
            raise ValueError("native segment kind disagrees with its rendered-text span")
        if has_span and self.text_end <= self.text_start:
            raise ValueError("native text segment span is empty or reversed")
        return self


class MediaBlock(Contract):
    image_index: int = Field(ge=0, le=31)
    segment_index: int = Field(ge=0, lt=MAX_SEGMENTS)
    token_start: int = Field(ge=0, lt=MAX_INPUT_TOKENS)
    token_end: int = Field(ge=1, le=MAX_INPUT_TOKENS)
    boundary_token_count: int = Field(ge=1, le=MAX_INPUT_TOKENS)
    patch_token_count: int = Field(ge=1, le=MAX_INPUT_TOKENS)
    paragraph_aliases: tuple[str, ...] = Field(min_length=1, max_length=32)
    crop_regions: tuple[dict, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def _span_matches_counts(self) -> MediaBlock:
        if self.token_end - self.token_start != (
            self.boundary_token_count + self.patch_token_count
        ):
            raise ValueError("native media boundary/patch counts disagree with its token span")
        if len(self.paragraph_aliases) != len(self.crop_regions):
            raise ValueError("native media block has mismatched alias and crop counts")
        return self


class PatchTensor(Contract):
    image_index: int = Field(ge=0, le=31)
    dtype: Literal["float32"]
    byte_order: Literal["little"]
    channels: Literal[3]
    patch_size: int = Field(ge=1, le=64)
    temporal: int = Field(ge=1, le=8)
    grid_height: int = Field(ge=1, le=1024)
    grid_width: int = Field(ge=1, le=1024)
    merge_size: int = Field(ge=1, le=8)
    rows: int = Field(ge=1)
    features: int = Field(ge=1)
    element_count: int = Field(ge=1, le=MAX_PATCH_ELEMENTS)
    byte_length: int = Field(ge=FLOAT32_BYTES)
    data_sha256: Hash
    min_value: float
    max_value: float

    @model_validator(mode="after")
    def _grid_shape(self) -> PatchTensor:
        if self.grid_height % self.merge_size or self.grid_width % self.merge_size:
            raise ValueError("native patch grid is not divisible by the merge size")
        if self.rows != self.temporal * self.grid_height * self.grid_width:
            raise ValueError("native patch rows disagree with the temporal grid")
        if self.features != self.channels * self.patch_size * self.patch_size:
            raise ValueError("native patch features disagree with channels and patch size")
        return self

    @model_validator(mode="after")
    def _element_counts(self) -> PatchTensor:
        if self.element_count != self.rows * self.features:
            raise ValueError("native patch element count disagrees with the shape")
        if self.byte_length != self.element_count * FLOAT32_BYTES:
            raise ValueError("native patch byte length disagrees with the element count")
        return self

    @model_validator(mode="after")
    def _declared_range(self) -> PatchTensor:
        if not math.isfinite(self.min_value) or not math.isfinite(self.max_value):
            raise ValueError("native patch declared range is not finite")
        if self.min_value > self.max_value:
            raise ValueError("native patch declared range is reversed")
        return self


class PositionLayout(Contract):
    dtype: Literal["int32"]
    byte_order: Literal["little"]
    entry_width: int = Field(ge=1, le=4)
    entry_count: int = Field(ge=1, le=MAX_INPUT_TOKENS)
    byte_length: int = Field(ge=4, le=MAX_POSITION_BYTES)
    data_sha256: Hash

    @model_validator(mode="after")
    def _byte_arithmetic(self) -> PositionLayout:
        if self.byte_length != self.entry_count * self.entry_width * 4:
            raise ValueError("native positional-layout bytes disagree with declared entries")
        return self


class ProducerIdentity(Contract):
    kind: Literal["owned_backend_capture", "authored_fixture"]
    producer_id: str = Field(min_length=1, max_length=256)
    executable_sha256: Hash | None = None
    capture_receipt_sha256: Hash | None = None

    @model_validator(mode="after")
    def _kind_requires_receipt(self) -> ProducerIdentity:
        if self.kind == "authored_fixture":
            _refuse_fixture_identity(self)
        else:
            _require_owned_identity(self)
        return self


def _refuse_fixture_identity(identity: ProducerIdentity) -> None:
    if (identity.capture_receipt_sha256, identity.executable_sha256) != (None, None):
        raise ValueError("an authored fixture must not claim a capture receipt or executable")


def _require_owned_identity(identity: ProducerIdentity) -> None:
    if identity.capture_receipt_sha256 is None or identity.executable_sha256 is None:
        raise ValueError("an owned capture requires a receipt and executable identity")


class CaptureReceipt(Contract):
    contract: Literal["productive-ocr-native-capture-receipt-v1"]
    capture_method: Literal["owned_backend_zero_generation_capture"]
    producer_id: str = Field(min_length=1, max_length=256)
    body_sha256: Hash
    rendered_text_sha256: Hash
    executable_sha256: Hash
    model_digest: Hash
    build_revision: str = Field(min_length=1, max_length=128)
    build_dirty: bool


class DebugTransform(Contract):
    contract: Literal["productive-ocr-debug-transform-v1"]
    intended_body_sha256: Hash
    output_body_sha256: Hash
    method: str = Field(min_length=1, max_length=256)
    steps: tuple[str, ...] = Field(min_length=1, max_length=32)


class DebugRequestBinding(Contract):
    debug_body_sha256: Hash
    transform_sha256: Hash


class NativeTraceV2(Contract):
    contract: Literal["productive-ocr-native-fit-trace-v2"] = TRACE_CONTRACT
    scope: Literal["preprocessing_only"]
    launch_clearance: Literal[False]
    request_projection_sha256: Hash
    host_packet_sha256: Hash
    body_sha256: Hash
    image_sha256: Hash
    image_bindings_sha256: Hash
    diagnostics_sha256: Hash
    saved_proposal_sha256: Hash | None
    model_name: str = Field(min_length=1)
    model_digest: Hash
    tokenizer_sha256: Hash
    preprocessor_sha256: Hash
    renderer_sha256: Hash
    rendered_text_sha256: Hash
    rendered_text_length: int = Field(ge=1, le=24 * 1024 * 1024)
    input_tokens: int = Field(ge=1, le=MAX_INPUT_TOKENS)
    text_tokens: int = Field(ge=1, le=MAX_INPUT_TOKENS)
    image_tokens: int = Field(ge=1, le=MAX_INPUT_TOKENS)
    output_token_limit: int = Field(ge=1, le=MAX_OUTPUT_TOKENS)
    segments: tuple[StreamSegment, ...] = Field(min_length=2, max_length=MAX_SEGMENTS)
    media: tuple[MediaBlock, ...] = Field(min_length=1, max_length=1)
    patches: tuple[PatchTensor, ...] = Field(min_length=1, max_length=1)
    positions: PositionLayout
    producer: ProducerIdentity
    debug_request: DebugRequestBinding | None = None

    @model_validator(mode="after")
    def _single_image(self) -> NativeTraceV2:
        if self.media[0].image_index != self.patches[0].image_index:
            raise ValueError("native media block and patch tensor disagree on the image index")
        return self


class NativeTraceGate(Contract):
    contract: Literal["productive-ocr-native-trace-gate-v2"] = "productive-ocr-native-trace-gate-v2"
    trace_valid: bool
    reason: str | None
    trace_sha256: Hash | None
    trace: NativeTraceV2 | None
    producer_kind: Literal["owned_backend_capture", "authored_fixture"] | None
    declared_owned_capture: bool
    authentic_capture: Literal[False] = False
    exact_build_parity: Literal[False] = False
    launch_ready: Literal[False] = False
    blockers: tuple[str, ...]

    @model_validator(mode="after")
    def _consistent(self) -> NativeTraceGate:
        if self.trace_valid != (self.trace is not None):
            raise ValueError("gate validity disagrees with the presence of a trace")
        if self.trace_valid != (self.trace_sha256 is not None):
            raise ValueError("gate validity disagrees with the presence of a trace digest")
        if self.trace is not None and self.producer_kind != self.trace.producer.kind:
            raise ValueError("gate producer kind disagrees with the validated trace")
        return self


class NativeTraceProducer(Protocol):
    """Explicit boundary a future owned-backend exporter must implement."""

    def identity(self) -> ProducerIdentity: ...

    def export(self) -> bytes: ...


@dataclass(frozen=True)
class AuthoredFixtureProducer:
    """Test/inspection adapter; never represents native backend output."""

    producer: ProducerIdentity
    payload: bytes

    def identity(self) -> ProducerIdentity:
        return self.producer

    def export(self) -> bytes:
        return self.payload


def freeze_projection(
    *,
    host_packet_sha256: str,
    body: dict,
    schema_sha256: str,
    prompt_sha256: str,
    model_name: str,
    model_digest: str,
    image_sha256: str,
    source_layers_sha256: str,
    image_bindings: list[dict],
    diagnostics_sha256: str,
    saved_proposal_sha256: str | None = None,
) -> RequestProjection:
    """Build the exact frozen binding object directly for offline fixtures."""
    body_utf8 = canonical_json(body).decode("utf-8")
    bindings_json = canonical_json(image_bindings)
    return RequestProjection(
        host_packet_sha256=host_packet_sha256,
        body_utf8=body_utf8,
        body_sha256=sha256_bytes(body_utf8.encode("utf-8")),
        schema_sha256=schema_sha256,
        prompt_sha256=prompt_sha256,
        model_name=model_name,
        model_digest=model_digest,
        image_sha256=image_sha256,
        source_layers_sha256=source_layers_sha256,
        image_bindings_json=bindings_json.decode("utf-8"),
        image_bindings_sha256=sha256_bytes(bindings_json),
        diagnostics_sha256=diagnostics_sha256,
        saved_proposal_sha256=saved_proposal_sha256,
    )


def _registered_bytes(registry: EvidenceRegistry, digest: str, label: str) -> bytes:
    data = registry.files.get(digest)
    if data is None or sha256_bytes(data) != digest:
        raise ValueError(f"{label} bytes missing or changed")
    return data


def _load_model[ModelT: Contract](
    registry: EvidenceRegistry, digest: str, model: type[ModelT]
) -> ModelT:
    data = _registered_bytes(registry, digest, "native trace evidence")
    try:
        value = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ValueError("native trace evidence is not JSON") from exc
    if not isinstance(value, dict) or canonical_json(value) != data:
        raise ValueError("native trace evidence must be canonical JSON")
    return model.model_validate_json(data)


def _parse_trace(text: str) -> NativeTraceV2:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("native v2 trace is not JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("native v2 trace must be a JSON object")
    missing = sorted(set(NativeTraceV2.model_fields) - value.keys())
    if missing:
        raise ValueError("incomplete native v2 trace; missing fields: " + ", ".join(missing))
    return NativeTraceV2.model_validate_json(canonical_json(value))


def _register_trace(trace: NativeTraceV2, registry: EvidenceRegistry) -> str:
    data = canonical_json(trace.model_dump(mode="json"))
    digest = sha256_bytes(data)
    if registry.files.get(digest) != data:
        raise ValueError("native v2 trace is not registered by exact canonical bytes")
    return digest


def _check_projection_consistency(projection: RequestProjection) -> None:
    if sha256_bytes(projection.body_utf8.encode("utf-8")) != projection.body_sha256:
        raise ValueError("request projection body hash is internally inconsistent")
    bindings_sha = sha256_bytes(projection.image_bindings_json.encode("utf-8"))
    if bindings_sha != projection.image_bindings_sha256:
        raise ValueError("request projection image-bindings hash is internally inconsistent")


def _check_binding(trace: NativeTraceV2, projection: RequestProjection) -> None:
    _check_projection_consistency(projection)
    pairs = (
        (
            trace.request_projection_sha256,
            sha256_bytes(canonical_json(projection.model_dump(mode="json"))),
        ),
        (trace.host_packet_sha256, projection.host_packet_sha256),
        (trace.body_sha256, projection.body_sha256),
        (trace.image_sha256, projection.image_sha256),
        (trace.image_bindings_sha256, projection.image_bindings_sha256),
        (trace.diagnostics_sha256, projection.diagnostics_sha256),
        (trace.saved_proposal_sha256, projection.saved_proposal_sha256),
        (trace.model_name, projection.model_name),
        (trace.model_digest, projection.model_digest),
        (trace.output_token_limit, json.loads(projection.body_utf8)["options"]["num_predict"]),
    )
    if any(left != right for left, right in pairs):
        raise ValueError("native v2 trace does not bind the exact request projection")


def _check_resources(trace: NativeTraceV2, registry: EvidenceRegistry) -> None:
    for digest, label in (
        (trace.tokenizer_sha256, "tokenizer"),
        (trace.preprocessor_sha256, "preprocessor"),
        (trace.renderer_sha256, "renderer"),
    ):
        _registered_bytes(registry, digest, f"pinned {label} resource")


def _rendered_bytes(trace: NativeTraceV2, registry: EvidenceRegistry) -> bytes:
    data = _registered_bytes(registry, trace.rendered_text_sha256, "native rendered text")
    try:
        data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("native rendered-text bytes are not exact UTF-8") from exc
    if len(data) != trace.rendered_text_length:
        raise ValueError("native rendered-text byte length disagrees with the trace")
    return data


def _check_segment_order(segments: tuple[StreamSegment, ...]) -> None:
    if tuple(segment.index for segment in segments) != tuple(range(len(segments))):
        raise ValueError("native segment indices are not contiguous and ordered")


def _has_text_segment(segments: tuple[StreamSegment, ...]) -> bool:
    return any(segment.kind == "text" for segment in segments)


def _media_segment_count(segments: tuple[StreamSegment, ...]) -> int:
    return sum(1 for segment in segments if segment.kind == "media")


def _check_segment_kinds(segments: tuple[StreamSegment, ...]) -> None:
    if not _has_text_segment(segments):
        raise ValueError("native trace has no rendered-text segment")
    if _media_segment_count(segments) != 1:
        raise ValueError("native trace must contain exactly one media segment")


def _check_segment_indices(segments: tuple[StreamSegment, ...]) -> None:
    _check_segment_order(segments)
    _check_segment_kinds(segments)


def _token_counts(segments: tuple[StreamSegment, ...]) -> tuple[int, int, int]:
    total = sum(len(segment.token_ids) for segment in segments)
    text = sum(len(segment.token_ids) for segment in segments if segment.kind == "text")
    return total, text, total - text


def _check_segment_tokens(segments: tuple[StreamSegment, ...], trace: NativeTraceV2) -> None:
    counts = _token_counts(segments)
    if counts != (trace.input_tokens, trace.text_tokens, trace.image_tokens):
        raise ValueError("native segment token counts disagree with the declared totals")


def _check_one_text_segment(segment: StreamSegment, rendered: bytes, cursor: int) -> int:
    if segment.text_start != cursor or segment.text_end is None:
        raise ValueError("native text segments do not tile the rendered text exactly")
    try:
        rendered[segment.text_start : segment.text_end].decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("native text segment does not fall on UTF-8 boundaries") from exc
    return segment.text_end


def _check_text_tiling(segments: tuple[StreamSegment, ...], rendered: bytes) -> None:
    cursor = 0
    for segment in (item for item in segments if item.kind == "text"):
        cursor = _check_one_text_segment(segment, rendered, cursor)
    if cursor != len(rendered):
        raise ValueError("native text segments do not cover the rendered text exactly")


def _check_segments(trace: NativeTraceV2, registry: EvidenceRegistry) -> None:
    _check_segment_indices(trace.segments)
    _check_segment_tokens(trace.segments, trace)
    _check_text_tiling(trace.segments, _rendered_bytes(trace, registry))


def _expected_geometry(projection: RequestProjection) -> tuple[tuple[str, ...], tuple[dict, ...]]:
    bindings = json.loads(projection.image_bindings_json)
    return (
        tuple(item["paragraph_alias"] for item in bindings),
        tuple(item["crop_region"] for item in bindings),
    )


def _check_media_span(
    media: MediaBlock, segment: StreamSegment, segments: tuple[StreamSegment, ...]
) -> None:
    prefix = sum(len(item.token_ids) for item in segments[: media.segment_index])
    if segment.kind != "media":
        raise ValueError("native media block does not reference the media token segment")
    if media.token_start != prefix or media.token_end != prefix + len(segment.token_ids):
        raise ValueError("native media block does not cover its whole expanded segment")


def _check_media_geometry(media: MediaBlock, projection: RequestProjection) -> None:
    aliases, crops = _expected_geometry(projection)
    if media.image_index != 0 or media.paragraph_aliases != aliases:
        raise ValueError("native media block differs from frozen paragraph aliases")
    if media.crop_regions != crops:
        raise ValueError("native media block differs from frozen crop geometry")


def _check_media(trace: NativeTraceV2, projection: RequestProjection) -> None:
    media = trace.media[0]
    if media.segment_index >= len(trace.segments):
        raise ValueError("native media block references a missing token segment")
    segment = trace.segments[media.segment_index]
    _check_media_span(media, segment, trace.segments)
    _check_media_geometry(media, projection)


def _check_patch_geometry(trace: NativeTraceV2) -> None:
    media = trace.media[0]
    patch = trace.patches[0]
    cells = (patch.grid_height // patch.merge_size) * (patch.grid_width // patch.merge_size)
    if cells * patch.temporal != media.patch_token_count:
        raise ValueError("native patch grid does not equal the media patch-token count")


def _patch_values(patch: PatchTensor, data: bytes) -> array:
    if len(data) != patch.byte_length or len(data) != patch.element_count * FLOAT32_BYTES:
        raise ValueError("native float32 patch bytes disagree with the declared shape")
    values = array("f")
    if values.itemsize != FLOAT32_BYTES:
        raise ValueError("this host cannot decode 4-byte float32 patch values")
    values.frombytes(data)
    if sys.byteorder != "little":
        values.byteswap()
    return values


def _check_patch_values(patch: PatchTensor, data: bytes) -> None:
    values = _patch_values(patch, data)
    if any(not math.isfinite(value) for value in values):
        raise ValueError("native float32 patch data contains a non-finite value")
    if min(values) != patch.min_value or max(values) != patch.max_value:
        raise ValueError("native float32 patch values disagree with the declared min/max")


def _check_patches(trace: NativeTraceV2, registry: EvidenceRegistry) -> None:
    patch = trace.patches[0]
    data = _registered_bytes(registry, patch.data_sha256, "native float32 patch data")
    _check_patch_values(patch, data)
    _check_patch_geometry(trace)


def _check_positions(trace: NativeTraceV2, registry: EvidenceRegistry) -> None:
    layout = trace.positions
    data = _registered_bytes(registry, layout.data_sha256, "native positional layout")
    if len(data) != layout.byte_length:
        raise ValueError("native positional layout bytes disagree with the declared length")
    if layout.entry_count != trace.input_tokens:
        raise ValueError("native positional layout does not cover the expanded token stream")


def _check_debug_request(trace: NativeTraceV2, registry: EvidenceRegistry) -> None:
    debug = trace.debug_request
    if debug is None:
        return
    transform = _load_model(registry, debug.transform_sha256, DebugTransform)
    intended = transform.intended_body_sha256
    if intended != trace.body_sha256 or transform.output_body_sha256 != debug.debug_body_sha256:
        raise ValueError("debug request transform does not bind the intended body exactly")
    if debug.debug_body_sha256 == trace.body_sha256:
        raise ValueError("debug request must be separate bytes from the study request")
    _registered_bytes(registry, debug.debug_body_sha256, "debug request body")


def _check_receipt(receipt: CaptureReceipt, trace: NativeTraceV2) -> None:
    pairs = (
        (receipt.producer_id, trace.producer.producer_id),
        (receipt.body_sha256, trace.body_sha256),
        (receipt.rendered_text_sha256, trace.rendered_text_sha256),
        (receipt.executable_sha256, trace.producer.executable_sha256),
        (receipt.model_digest, trace.model_digest),
    )
    if any(left != right for left, right in pairs):
        raise ValueError("capture receipt does not bind the exact trace identity")


def _check_producer(
    trace: NativeTraceV2, registry: EvidenceRegistry, producer: NativeTraceProducer | None
) -> None:
    if producer is not None and producer.identity() != trace.producer:
        raise ValueError("exporting producer identity differs from the trace's declared producer")
    if trace.producer.kind == "authored_fixture":
        return
    receipt_sha = trace.producer.capture_receipt_sha256
    if receipt_sha is None:
        raise ValueError("an owned capture requires a registered receipt identity")
    receipt = _load_model(registry, receipt_sha, CaptureReceipt)
    _check_receipt(receipt, trace)


def _blockers(kind: Literal["owned_backend_capture", "authored_fixture"]) -> tuple[str, ...]:
    if kind == "authored_fixture":
        return (*BASE_BLOCKERS, FIXTURE_BLOCKER, CAPTURE_BLOCKER)
    return (*BASE_BLOCKERS, CAPTURE_BLOCKER, OWNED_CAPTURE_BLOCKER)


def _failed_gate(error: Exception) -> NativeTraceGate:
    return NativeTraceGate(
        trace_valid=False,
        reason=str(error)[:1000],
        trace_sha256=None,
        trace=None,
        producer_kind=None,
        declared_owned_capture=False,
        blockers=BASE_BLOCKERS,
    )


def inspect_native_trace(
    projection: RequestProjection,
    trace_json: str,
    registry: EvidenceRegistry,
    producer: NativeTraceProducer | None = None,
) -> NativeTraceGate:
    """Validate a v2 trace against exact request/resource bytes; never launch-ready."""
    try:
        trace = _parse_trace(trace_json)
        digest = _register_trace(trace, registry)
        _check_binding(trace, projection)
        _check_resources(trace, registry)
        _check_segments(trace, registry)
        _check_media(trace, projection)
        _check_patches(trace, registry)
        _check_positions(trace, registry)
        _check_debug_request(trace, registry)
        _check_producer(trace, registry, producer)
    except (ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError) as error:
        return _failed_gate(error)
    return NativeTraceGate(
        trace_valid=True,
        reason=None,
        trace_sha256=digest,
        trace=trace,
        producer_kind=trace.producer.kind,
        declared_owned_capture=trace.producer.kind == "owned_backend_capture",
        blockers=_blockers(trace.producer.kind),
    )


def export_native_trace(
    producer: NativeTraceProducer,
    projection: RequestProjection,
    registry: EvidenceRegistry,
) -> NativeTraceGate:
    """Explicit adapter boundary: exported bytes are re-validated, not trusted."""
    try:
        payload = producer.export()
    except Exception as error:
        return _failed_gate(ValueError(f"native trace export failed: {error}"))
    digest = sha256_bytes(payload)
    if registry.files.get(digest) != payload:
        return _failed_gate(ValueError("exported trace bytes are not registered exactly"))
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        return _failed_gate(ValueError(f"native trace export is not UTF-8: {exc}"))
    gate = inspect_native_trace(projection, text, registry, producer=producer)
    if gate.trace_sha256 is not None and gate.trace_sha256 != digest:
        return _failed_gate(
            ValueError("exported trace bytes are not the canonical registered trace")
        )
    return gate


def require_authentic_producer(gate: NativeTraceGate) -> NoReturn:
    """Refuse to treat any offline trace as native truth or launch clearance."""
    if not gate.trace_valid or gate.trace is None:
        raise ValueError(gate.reason or "native v2 trace is not valid")
    if not gate.declared_owned_capture:
        raise ValueError(
            "authored or undeclared capture is not native truth: " + "; ".join(gate.blockers)
        )
    raise ValueError(
        "a declared owned capture is not independently attested or launch clearance: "
        + "; ".join(gate.blockers)
    )
