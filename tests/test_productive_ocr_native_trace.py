"""Strict v2 native-fit trace contract: authored fixtures only, never readiness."""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from congressional_globe.productive_ocr_host import (
    EvidenceRegistry,
    canonical_json,
    sha256_bytes,
)
from congressional_globe.productive_ocr_native_trace import (
    CAPTURE_BLOCKER,
    FIXTURE_BLOCKER,
    MAX_PATCH_ELEMENTS,
    OWNED_CAPTURE_BLOCKER,
    AuthoredFixtureProducer,
    CaptureReceipt,
    NativeTraceGate,
    ProducerIdentity,
    export_native_trace,
    freeze_projection,
    inspect_native_trace,
    require_authentic_producer,
)
from congressional_globe.productive_ocr_projection import RequestProjection

MODEL_NAME = "qwen3.8:27b-mlx"


def _sha(label: bytes) -> str:
    return sha256_bytes(label)


def _build_fixture() -> tuple[RequestProjection, EvidenceRegistry, dict]:
    bindings = [
        {
            "paragraph_alias": "P1",
            "crop_region": {"left": 0, "top": 0, "right": 16, "bottom": 16},
        }
    ]
    body = {"model": MODEL_NAME, "options": {"num_predict": 1500}, "messages": []}
    projection = freeze_projection(
        host_packet_sha256=_sha(b"host"),
        body=body,
        schema_sha256=_sha(b"schema"),
        prompt_sha256=_sha(b"prompt"),
        model_name=MODEL_NAME,
        model_digest=_sha(b"model"),
        image_sha256=_sha(b"image"),
        source_layers_sha256=_sha(b"layers"),
        image_bindings=bindings,
        diagnostics_sha256=_sha(b"diagnostics"),
    )
    rendered = b"Person speaks."
    rows, features = 4, 12
    values = [index / 64 for index in range(rows * features)]
    patch_bytes = struct.pack(f"<{rows * features}f", *values)
    position_bytes = struct.pack("<6i", *range(6))
    files = {
        "tokenizer": b"tokenizer-bytes",
        "preprocessor": b"preprocessor-bytes",
        "renderer": b"renderer-bytes",
    }
    registry = EvidenceRegistry(
        image_bytes={},
        records={},
        files={
            **{sha256_bytes(blob): blob for blob in files.values()},
            sha256_bytes(rendered): rendered,
            sha256_bytes(patch_bytes): patch_bytes,
            sha256_bytes(position_bytes): position_bytes,
        },
    )
    trace = {
        "contract": "productive-ocr-native-fit-trace-v2",
        "scope": "preprocessing_only",
        "launch_clearance": False,
        "request_projection_sha256": sha256_bytes(
            canonical_json(projection.model_dump(mode="json"))
        ),
        "host_packet_sha256": projection.host_packet_sha256,
        "body_sha256": projection.body_sha256,
        "image_sha256": projection.image_sha256,
        "image_bindings_sha256": projection.image_bindings_sha256,
        "diagnostics_sha256": projection.diagnostics_sha256,
        "saved_proposal_sha256": None,
        "model_name": MODEL_NAME,
        "model_digest": projection.model_digest,
        "tokenizer_sha256": _sha(b"tokenizer-bytes"),
        "preprocessor_sha256": _sha(b"preprocessor-bytes"),
        "renderer_sha256": _sha(b"renderer-bytes"),
        "rendered_text_sha256": _sha(rendered),
        "rendered_text_length": len(rendered),
        "input_tokens": 6,
        "text_tokens": 3,
        "image_tokens": 3,
        "output_token_limit": 1500,
        "segments": [
            {
                "index": 0,
                "kind": "text",
                "token_ids": [11, 12],
                "text_start": 0,
                "text_end": 7,
            },
            {
                "index": 1,
                "kind": "media",
                "token_ids": [21, 22, 23],
                "text_start": None,
                "text_end": None,
            },
            {
                "index": 2,
                "kind": "text",
                "token_ids": [31],
                "text_start": 7,
                "text_end": len(rendered),
            },
        ],
        "media": [
            {
                "image_index": 0,
                "segment_index": 1,
                "token_start": 2,
                "token_end": 5,
                "boundary_token_count": 2,
                "patch_token_count": 1,
                "paragraph_aliases": ("P1",),
                "crop_regions": ({"left": 0, "top": 0, "right": 16, "bottom": 16},),
            }
        ],
        "patches": [
            {
                "image_index": 0,
                "dtype": "float32",
                "byte_order": "little",
                "channels": 3,
                "patch_size": 2,
                "temporal": 1,
                "grid_height": 2,
                "grid_width": 2,
                "merge_size": 2,
                "rows": rows,
                "features": features,
                "element_count": rows * features,
                "byte_length": len(patch_bytes),
                "data_sha256": _sha(patch_bytes),
                "min_value": 0.0,
                "max_value": 47 / 64,
            }
        ],
        "positions": {
            "dtype": "int32",
            "byte_order": "little",
            "entry_width": 1,
            "entry_count": 6,
            "byte_length": len(position_bytes),
            "data_sha256": _sha(position_bytes),
        },
        "producer": {
            "kind": "authored_fixture",
            "producer_id": "authored-fixture-v2",
            "executable_sha256": None,
            "capture_receipt_sha256": None,
        },
        "debug_request": None,
    }
    return projection, registry, trace


@dataclass
class Fixture:
    projection: RequestProjection
    registry: EvidenceRegistry
    trace: dict

    def register(self) -> Fixture:
        raw = canonical_json(self.trace)
        self.registry.files[sha256_bytes(raw)] = raw
        return self

    def json(self) -> str:
        return json.dumps(self.trace)

    def gate(self) -> NativeTraceGate:
        self.register()
        return inspect_native_trace(self.projection, self.json(), self.registry)


def _fixture() -> Fixture:
    projection, registry, trace = _build_fixture()
    return Fixture(projection=projection, registry=registry, trace=trace).register()


def _default_patch_values(count: int) -> list[float]:
    return [index / 64 for index in range(count)]


def _finite_range(data: bytes, endian: str) -> tuple[float, float] | None:
    count = len(data) // 4
    unpacked = struct.unpack(f"{endian}{count}f", data)
    finite = [value for value in unpacked if math.isfinite(value)]
    if not finite:
        return None
    return float(min(finite)), float(max(finite))


def _write_patch(
    fixture: Fixture,
    *,
    grid_height: int = 2,
    grid_width: int = 2,
    merge_size: int = 2,
    endian: str = "<",
    values: list[float] | None = None,
) -> dict:
    rows = grid_height * grid_width
    features = 3 * 2 * 2
    count = rows * features
    chosen = values if values is not None else _default_patch_values(count)
    data = struct.pack(f"{endian}{count}f", *chosen)
    patch = fixture.trace["patches"][0]
    patch.update(
        {
            "grid_height": grid_height,
            "grid_width": grid_width,
            "merge_size": merge_size,
            "rows": rows,
            "features": features,
            "element_count": count,
            "byte_length": len(data),
            "data_sha256": sha256_bytes(data),
        }
    )
    declared = _finite_range(data, endian)
    if declared is not None:
        patch["min_value"], patch["max_value"] = declared
    fixture.registry.files[sha256_bytes(data)] = data
    return patch


def _assert_invalid(fixture: Fixture, fragment: str) -> None:
    gate = fixture.gate()
    assert gate.trace_valid is False
    assert gate.trace is None
    assert gate.launch_ready is False
    assert fragment in (gate.reason or "")


def test_authored_fixture_validates_but_is_not_native_truth() -> None:
    fixture = _fixture()
    gate = fixture.gate()

    assert gate.trace_valid is True
    assert gate.declared_owned_capture is False
    assert gate.authentic_capture is False
    assert gate.producer_kind == "authored_fixture"
    assert gate.exact_build_parity is False
    assert gate.launch_ready is False
    assert FIXTURE_BLOCKER in gate.blockers
    assert CAPTURE_BLOCKER in gate.blockers
    with pytest.raises(ValueError, match="not native truth"):
        require_authentic_producer(gate)


def test_launch_clearance_true_cannot_be_constructed() -> None:
    fixture = _fixture()
    fixture.trace["launch_clearance"] = True

    _assert_invalid(fixture, "launch_clearance")


def test_export_adapter_rechecks_bytes_and_producer_identity() -> None:
    fixture = _fixture()
    identity = ProducerIdentity.model_validate(fixture.trace["producer"])
    producer = AuthoredFixtureProducer(producer=identity, payload=canonical_json(fixture.trace))
    fixture.register()

    gate = export_native_trace(producer, fixture.projection, fixture.registry)
    assert gate.trace_valid is True
    assert gate.launch_ready is False

    other = AuthoredFixtureProducer(
        producer=identity.model_copy(update={"producer_id": "different-producer"}),
        payload=canonical_json(fixture.trace),
    )
    refused = export_native_trace(other, fixture.projection, fixture.registry)
    assert refused.trace_valid is False
    assert "identity differs" in (refused.reason or "")


def test_non_finite_float_patch_value_is_rejected() -> None:
    fixture = _fixture()
    values = [index / 64 for index in range(48)]
    values[0] = math.nan
    _write_patch(fixture, values=values)

    _assert_invalid(fixture, "non-finite")


def test_infinite_float_patch_value_is_rejected() -> None:
    fixture = _fixture()
    values = [index / 64 for index in range(48)]
    values[7] = math.inf
    _write_patch(fixture, values=values)

    _assert_invalid(fixture, "non-finite")


def test_declared_float_range_must_match_bytes() -> None:
    fixture = _fixture()
    fixture.trace["patches"][0]["max_value"] = 0.75

    _assert_invalid(fixture, "declared min/max")


def test_little_endian_declaration_with_swapped_bytes_is_rejected() -> None:
    fixture = _fixture()
    _write_patch(fixture, endian=">")

    _assert_invalid(fixture, "declared min/max")


def test_big_endian_float_patch_order_is_not_accepted() -> None:
    fixture = _fixture()
    fixture.trace["patches"][0]["byte_order"] = "big"

    _assert_invalid(fixture, "byte_order")


def test_patch_bytes_shorter_than_declared_shape_are_rejected() -> None:
    fixture = _fixture()
    data = struct.pack("<44f", *[0.0] * 44)
    fixture.trace["patches"][0]["data_sha256"] = sha256_bytes(data)
    fixture.registry.files[sha256_bytes(data)] = data

    _assert_invalid(fixture, "declared shape")


def test_patch_element_overflow_is_rejected() -> None:
    fixture = _fixture()
    fixture.trace["patches"][0]["element_count"] = MAX_PATCH_ELEMENTS + 1

    _assert_invalid(fixture, "element_count")


def test_patch_grid_must_equal_media_patch_token_count() -> None:
    fixture = _fixture()
    _write_patch(fixture, grid_height=4, grid_width=2)

    _assert_invalid(fixture, "patch-token count")


def test_media_block_must_cover_its_whole_token_segment() -> None:
    fixture = _fixture()
    fixture.trace["media"][0]["token_start"] = 3
    fixture.trace["media"][0]["token_end"] = 6

    _assert_invalid(fixture, "whole expanded segment")


def test_media_block_must_match_frozen_paragraph_alias() -> None:
    fixture = _fixture()
    fixture.trace["media"][0]["paragraph_aliases"] = ("P2",)

    _assert_invalid(fixture, "paragraph aliases")


def test_segment_token_total_must_equal_expanded_stream() -> None:
    fixture = _fixture()
    fixture.trace["segments"][1]["token_ids"] = [21, 22]

    _assert_invalid(fixture, "token counts")


def test_token_stream_overflow_is_rejected() -> None:
    fixture = _fixture()
    fixture.trace["input_tokens"] = 6001
    fixture.trace["segments"][0]["token_ids"] = list(range(6001))

    _assert_invalid(fixture, "6001")


def test_text_segments_must_tile_rendered_text() -> None:
    fixture = _fixture()
    fixture.trace["segments"][0]["text_end"] = 6

    _assert_invalid(fixture, "tile")


def test_rendered_text_must_be_exact_utf8() -> None:
    fixture = _fixture()
    rendered = b"\xff\xfe"
    fixture.trace["rendered_text_sha256"] = sha256_bytes(rendered)
    fixture.trace["rendered_text_length"] = len(rendered)
    fixture.registry.files[sha256_bytes(rendered)] = rendered

    _assert_invalid(fixture, "UTF-8")


def test_request_binding_mismatch_is_rejected() -> None:
    fixture = _fixture()
    fixture.trace["body_sha256"] = _sha(b"other-body")

    _assert_invalid(fixture, "exact request projection")


def test_missing_pinned_resource_is_rejected() -> None:
    fixture = _fixture()
    del fixture.registry.files[fixture.trace["tokenizer_sha256"]]

    _assert_invalid(fixture, "tokenizer")


def test_unregistered_trace_bytes_are_rejected() -> None:
    fixture = _fixture()
    del fixture.registry.files[sha256_bytes(canonical_json(fixture.trace))]

    gate = inspect_native_trace(fixture.projection, fixture.json(), fixture.registry)
    assert gate.trace_valid is False
    assert "not registered" in (gate.reason or "")


def test_output_token_overflow_is_rejected() -> None:
    fixture = _fixture()
    fixture.trace["output_token_limit"] = 1501

    _assert_invalid(fixture, "output_token_limit")


def test_positions_must_cover_the_expanded_token_stream() -> None:
    fixture = _fixture()
    data = struct.pack("<5i", *range(5))
    fixture.trace["positions"]["entry_count"] = 5
    fixture.trace["positions"]["byte_length"] = len(data)
    fixture.trace["positions"]["data_sha256"] = sha256_bytes(data)
    fixture.registry.files[sha256_bytes(data)] = data

    _assert_invalid(fixture, "positional layout")


def test_debug_request_transform_must_bind_the_intended_body() -> None:
    fixture = _fixture()
    debug = b'{"model":"qwen3.8:27b-mlx","debug":"render"}'
    transform = {
        "contract": "productive-ocr-debug-transform-v1",
        "intended_body_sha256": _sha(b"wrong-body"),
        "output_body_sha256": sha256_bytes(debug),
        "method": "debug-render-only",
        "steps": ("set debug.render",),
    }
    fixture.registry.files[sha256_bytes(debug)] = debug
    fixture.registry.files[sha256_bytes(canonical_json(transform))] = canonical_json(transform)
    fixture.trace["debug_request"] = {
        "debug_body_sha256": sha256_bytes(debug),
        "transform_sha256": sha256_bytes(canonical_json(transform)),
    }

    _assert_invalid(fixture, "debug request transform")


def test_debug_request_must_be_separate_from_the_study_request() -> None:
    fixture = _fixture()
    intended = fixture.projection.body_utf8.encode()
    transform = {
        "contract": "productive-ocr-debug-transform-v1",
        "intended_body_sha256": sha256_bytes(intended),
        "output_body_sha256": sha256_bytes(intended),
        "method": "debug-render-only",
        "steps": ("set debug.render",),
    }
    fixture.registry.files[sha256_bytes(canonical_json(transform))] = canonical_json(transform)
    fixture.trace["debug_request"] = {
        "debug_body_sha256": sha256_bytes(intended),
        "transform_sha256": sha256_bytes(canonical_json(transform)),
    }

    _assert_invalid(fixture, "separate bytes")


def test_debug_request_binding_accepts_a_registered_transform() -> None:
    fixture = _fixture()
    debug = b'{"model":"qwen3.8:27b-mlx","debug":"render"}'
    transform = {
        "contract": "productive-ocr-debug-transform-v1",
        "intended_body_sha256": fixture.projection.body_sha256,
        "output_body_sha256": sha256_bytes(debug),
        "method": "debug-render-only",
        "steps": ("set debug.render",),
    }
    fixture.registry.files[sha256_bytes(debug)] = debug
    fixture.registry.files[sha256_bytes(canonical_json(transform))] = canonical_json(transform)
    fixture.trace["debug_request"] = {
        "debug_body_sha256": sha256_bytes(debug),
        "transform_sha256": sha256_bytes(canonical_json(transform)),
    }

    gate = fixture.gate()
    assert gate.trace_valid is True
    assert gate.launch_ready is False


def test_owned_capture_requires_a_receipt_and_executable() -> None:
    fixture = _fixture()
    fixture.trace["producer"] = {
        "kind": "owned_backend_capture",
        "producer_id": "owned-capture",
        "executable_sha256": None,
        "capture_receipt_sha256": None,
    }

    _assert_invalid(fixture, "owned capture requires")


def test_owned_capture_with_receipt_stays_not_launch_ready() -> None:
    fixture = _fixture()
    executable = _sha(b"installed-executable")
    receipt = {
        "contract": "productive-ocr-native-capture-receipt-v1",
        "capture_method": "owned_backend_zero_generation_capture",
        "producer_id": "owned-capture",
        "body_sha256": fixture.projection.body_sha256,
        "rendered_text_sha256": fixture.trace["rendered_text_sha256"],
        "executable_sha256": executable,
        "model_digest": fixture.projection.model_digest,
        "build_revision": "f580b5484a58c8370c35d669555bf887783a3f68",
        "build_dirty": True,
    }
    receipt_bytes = canonical_json(receipt)
    fixture.registry.files[sha256_bytes(receipt_bytes)] = receipt_bytes
    fixture.trace["producer"] = ProducerIdentity(
        kind="owned_backend_capture",
        producer_id="owned-capture",
        executable_sha256=executable,
        capture_receipt_sha256=sha256_bytes(receipt_bytes),
    ).model_dump(mode="json")

    gate = fixture.gate()

    assert gate.trace_valid is True
    assert gate.declared_owned_capture is True
    assert gate.authentic_capture is False
    assert gate.producer_kind == "owned_backend_capture"
    assert gate.exact_build_parity is False
    assert gate.launch_ready is False
    assert FIXTURE_BLOCKER not in gate.blockers
    assert CAPTURE_BLOCKER in gate.blockers
    assert OWNED_CAPTURE_BLOCKER in gate.blockers
    with pytest.raises(ValueError, match="not independently attested"):
        require_authentic_producer(gate)


def test_capture_receipt_must_bind_exact_trace_identity() -> None:
    fixture = _fixture()
    executable = _sha(b"installed-executable")
    receipt = CaptureReceipt(
        contract="productive-ocr-native-capture-receipt-v1",
        capture_method="owned_backend_zero_generation_capture",
        producer_id="owned-capture",
        body_sha256=_sha(b"wrong-body"),
        rendered_text_sha256=fixture.trace["rendered_text_sha256"],
        executable_sha256=executable,
        model_digest=fixture.projection.model_digest,
        build_revision="f580b548",
        build_dirty=True,
    )
    receipt_bytes = canonical_json(receipt.model_dump(mode="json"))
    fixture.registry.files[sha256_bytes(receipt_bytes)] = receipt_bytes
    fixture.trace["producer"] = {
        "kind": "owned_backend_capture",
        "producer_id": "owned-capture",
        "executable_sha256": executable,
        "capture_receipt_sha256": sha256_bytes(receipt_bytes),
    }

    _assert_invalid(fixture, "capture receipt")


def test_media_boundary_tokens_are_required() -> None:
    fixture = _fixture()
    fixture.trace["media"][0]["boundary_token_count"] = 0
    fixture.trace["media"][0]["token_end"] = 3

    _assert_invalid(fixture, "boundary_token_count")


def test_media_counts_must_match_the_token_span() -> None:
    fixture = _fixture()
    fixture.trace["media"][0]["token_end"] = 6

    _assert_invalid(fixture, "boundary/patch counts")


def test_segment_kind_must_match_its_text_span() -> None:
    fixture = _fixture()
    fixture.trace["segments"][0]["text_start"] = None

    _assert_invalid(fixture, "kind disagrees")


def test_segment_indices_must_be_contiguous_and_ordered() -> None:
    fixture = _fixture()
    fixture.trace["segments"][2]["index"] = 5

    _assert_invalid(fixture, "contiguous and ordered")


def test_duplicate_media_segments_are_rejected() -> None:
    fixture = _fixture()
    fixture.trace["segments"][2]["kind"] = "media"
    fixture.trace["segments"][2]["text_start"] = None
    fixture.trace["segments"][2]["text_end"] = None

    _assert_invalid(fixture, "exactly one media segment")


def test_patch_grid_must_be_divisible_by_merge_size() -> None:
    fixture = _fixture()
    fixture.trace["patches"][0]["grid_width"] = 3

    _assert_invalid(fixture, "not divisible")


def test_patch_rows_must_match_the_temporal_grid() -> None:
    fixture = _fixture()
    fixture.trace["patches"][0]["rows"] = 6

    _assert_invalid(fixture, "rows disagree")


def test_patch_features_must_match_channels_and_patch_size() -> None:
    fixture = _fixture()
    fixture.trace["patches"][0]["features"] = 10

    _assert_invalid(fixture, "features disagree")


def test_patch_element_count_must_match_the_shape() -> None:
    fixture = _fixture()
    fixture.trace["patches"][0]["element_count"] = 40

    _assert_invalid(fixture, "element count disagrees")


def test_patch_byte_length_must_match_the_element_count() -> None:
    fixture = _fixture()
    fixture.trace["patches"][0]["byte_length"] = 191

    _assert_invalid(fixture, "byte length disagrees")


def test_position_width_must_match_the_declared_bytes() -> None:
    fixture = _fixture()
    fixture.trace["positions"]["entry_width"] = 2

    _assert_invalid(fixture, "positional-layout bytes disagree")


def test_projection_body_hash_must_be_internally_consistent() -> None:
    fixture = _fixture()
    fixture.projection = fixture.projection.model_copy(update={"body_sha256": _sha(b"drifted")})

    _assert_invalid(fixture, "internally inconsistent")


def test_exported_bytes_must_be_the_registered_canonical_trace() -> None:
    fixture = _fixture()
    identity = ProducerIdentity.model_validate(fixture.trace["producer"])
    payload = json.dumps(fixture.trace, indent=2).encode()
    producer = AuthoredFixtureProducer(producer=identity, payload=payload)
    fixture.register()

    gate = export_native_trace(producer, fixture.projection, fixture.registry)
    assert gate.trace_valid is False
    assert "not registered exactly" in (gate.reason or "")


def test_gate_cannot_disagree_with_its_trace() -> None:
    with pytest.raises(ValidationError, match="presence of a trace"):
        NativeTraceGate(
            trace_valid=True,
            reason=None,
            trace_sha256=None,
            trace=None,
            producer_kind=None,
            declared_owned_capture=False,
            blockers=(),
        )


def test_owned_capture_receipt_must_be_registered() -> None:
    fixture = _fixture()
    fixture.trace["producer"] = {
        "kind": "owned_backend_capture",
        "producer_id": "owned-capture",
        "executable_sha256": _sha(b"executable"),
        "capture_receipt_sha256": _sha(b"never-registered"),
    }

    _assert_invalid(fixture, "missing or changed")
