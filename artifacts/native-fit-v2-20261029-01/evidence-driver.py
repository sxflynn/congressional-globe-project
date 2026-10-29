"""Offline evidence for the v2 native-fit trace contract; no server or model."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import struct
from pathlib import Path

from congressional_globe.productive_ocr_host import EvidenceRegistry, canonical_json
from congressional_globe.productive_ocr_native_trace import (
    FIXTURE_BLOCKER,
    MAX_PATCH_ELEMENTS,
    AuthoredFixtureProducer,
    ProducerIdentity,
    export_native_trace,
    freeze_projection,
    inspect_native_trace,
    require_authentic_producer,
)

OUT = Path(__file__).resolve().parent
MODEL = "qwen3.8:27b-mlx"
BINDINGS = [
    {"paragraph_alias": "P1", "crop_region": {"left": 0, "top": 0, "right": 16, "bottom": 16}}
]
RENDERED = b"Person speaks."
PATCH_VALUES = [index / 64 for index in range(48)]
PATCH_BYTES = struct.pack(f"<{len(PATCH_VALUES)}f", *PATCH_VALUES)
POSITION_BYTES = struct.pack("<6i", *range(6))


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def make_projection():
    return freeze_projection(
        host_packet_sha256=_sha(b"host"),
        body={"model": MODEL, "options": {"num_predict": 1500}, "messages": []},
        schema_sha256=_sha(b"schema"),
        prompt_sha256=_sha(b"prompt"),
        model_name=MODEL,
        model_digest=_sha(b"model"),
        image_sha256=_sha(b"image"),
        source_layers_sha256=_sha(b"layers"),
        image_bindings=BINDINGS,
        diagnostics_sha256=_sha(b"diagnostics"),
    )


def make_trace(projection) -> dict:
    return {
        "contract": "productive-ocr-native-fit-trace-v2",
        "scope": "preprocessing_only",
        "launch_clearance": False,
        "request_projection_sha256": _sha(canonical_json(projection.model_dump(mode="json"))),
        "host_packet_sha256": projection.host_packet_sha256,
        "body_sha256": projection.body_sha256,
        "image_sha256": projection.image_sha256,
        "image_bindings_sha256": projection.image_bindings_sha256,
        "diagnostics_sha256": projection.diagnostics_sha256,
        "saved_proposal_sha256": None,
        "model_name": MODEL,
        "model_digest": projection.model_digest,
        "tokenizer_sha256": _sha(b"tokenizer-bytes"),
        "preprocessor_sha256": _sha(b"preprocessor-bytes"),
        "renderer_sha256": _sha(b"renderer-bytes"),
        "rendered_text_sha256": _sha(RENDERED),
        "rendered_text_length": len(RENDERED),
        "input_tokens": 6,
        "text_tokens": 3,
        "image_tokens": 3,
        "output_token_limit": 1500,
        "segments": [
            {"index": 0, "kind": "text", "token_ids": [11, 12], "text_start": 0, "text_end": 7},
            {
                "index": 1,
                "kind": "media",
                "token_ids": [21, 22, 23],
                "text_start": None,
                "text_end": None,
            },
            {"index": 2, "kind": "text", "token_ids": [31], "text_start": 7, "text_end": 14},
        ],
        "media": [
            {
                "image_index": 0,
                "segment_index": 1,
                "token_start": 2,
                "token_end": 5,
                "boundary_token_count": 2,
                "patch_token_count": 1,
                "paragraph_aliases": ["P1"],
                "crop_regions": [{"left": 0, "top": 0, "right": 16, "bottom": 16}],
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
                "rows": 4,
                "features": 12,
                "element_count": 48,
                "byte_length": len(PATCH_BYTES),
                "data_sha256": _sha(PATCH_BYTES),
                "min_value": 0.0,
                "max_value": 47 / 64,
            }
        ],
        "positions": {
            "dtype": "int32",
            "byte_order": "little",
            "entry_width": 1,
            "entry_count": 6,
            "byte_length": len(POSITION_BYTES),
            "data_sha256": _sha(POSITION_BYTES),
        },
        "producer": {
            "kind": "authored_fixture",
            "producer_id": "authored-fixture-v2",
            "executable_sha256": None,
            "capture_receipt_sha256": None,
        },
        "debug_request": None,
    }


def make_registry(trace: dict) -> EvidenceRegistry:
    blobs = [
        b"tokenizer-bytes",
        b"preprocessor-bytes",
        b"renderer-bytes",
        RENDERED,
        PATCH_BYTES,
        POSITION_BYTES,
        canonical_json(trace),
    ]
    return EvidenceRegistry(image_bytes={}, records={}, files={_sha(blob): blob for blob in blobs})


def run(projection, trace: dict, registry: EvidenceRegistry, mutate=None):
    candidate = copy.deepcopy(trace)
    if mutate is not None:
        mutate(candidate, registry)
    raw = canonical_json(candidate)
    registry.files[_sha(raw)] = raw
    gate = inspect_native_trace(projection, raw.decode("utf-8"), registry)
    return candidate, gate


def _swap_patch_bytes(candidate, registry):
    data = struct.pack("<48f", *([0.5] * 47 + [math.nan]))
    registry.files[_sha(data)] = data
    candidate["patches"][0]["data_sha256"] = _sha(data)


def _overflow_elements(candidate, registry):
    candidate["patches"][0]["element_count"] = MAX_PATCH_ELEMENTS + 1


def _swap_body(candidate, registry):
    candidate["body_sha256"] = _sha(b"other-body")


def _break_alias(candidate, registry):
    candidate["media"][0]["paragraph_aliases"] = ["P2"]


def _swap_byte_order(candidate, registry):
    candidate["patches"][0]["byte_order"] = "big"


def _break_geometry(candidate, registry):
    data = struct.pack("<96f", *([index / 64 for index in range(96)]))
    registry.files[_sha(data)] = data
    patch = candidate["patches"][0]
    patch.update(
        {
            "grid_height": 4,
            "rows": 8,
            "element_count": 96,
            "byte_length": len(data),
            "data_sha256": _sha(data),
            "max_value": 95 / 64,
        }
    )


SCENARIOS = [
    ("baseline_authored_fixture", None, None),
    ("nan_patch_value", _swap_patch_bytes, "non-finite"),
    ("patch_element_overflow", _overflow_elements, "element_count"),
    ("request_body_mismatch", _swap_body, "exact request projection"),
    ("media_alias_mismatch", _break_alias, "paragraph aliases"),
    ("big_endian_declaration", _swap_byte_order, "byte_order"),
    ("grid_token_mismatch", _break_geometry, "patch-token count"),
]


def main() -> int:
    projection = make_projection()
    trace = make_trace(projection)
    registry = make_registry(trace)
    raw = canonical_json(trace)
    registry.files[_sha(raw)] = raw

    gate = inspect_native_trace(projection, raw.decode("utf-8"), registry)
    identity = ProducerIdentity.model_validate(trace["producer"])
    producer = AuthoredFixtureProducer(producer=identity, payload=raw)
    exported = export_native_trace(producer, projection, registry)
    try:
        require_authentic_producer(gate)
        refusal = None
    except ValueError as error:
        refusal = str(error)

    results = []
    for name, mutate, fragment in SCENARIOS:
        _, scenario_gate = run(projection, trace, registry, mutate)
        expected_valid = mutate is None
        passed = scenario_gate.trace_valid is expected_valid
        if fragment is not None:
            passed = passed and fragment in (scenario_gate.reason or "")
        results.append(
            {
                "scenario": name,
                "expected_valid": expected_valid,
                "trace_valid": scenario_gate.trace_valid,
                "reason": scenario_gate.reason,
                "launch_ready": scenario_gate.launch_ready,
                "passed": passed,
            }
        )

    out = {
        "contract": "productive-ocr-native-fit-trace-v2",
        "evidence_scope": "offline_authored_fixture_only",
        "authentic_native_capture": False,
        "authentic_capture_is_literal_false": True,
        "exact_build_parity": False,
        "launch_ready": False,
        "baseline": {
            "trace_valid": gate.trace_valid,
            "trace_sha256": gate.trace_sha256,
            "producer_kind": gate.producer_kind,
            "declared_owned_capture": gate.declared_owned_capture,
            "authentic_capture": gate.authentic_capture,
            "blockers": list(gate.blockers),
            "fixture_blocker_present": FIXTURE_BLOCKER in gate.blockers,
            "export_adapter_trace_valid": exported.trace_valid,
            "require_authentic_producer_refusal": refusal,
        },
        "scenarios": results,
        "all_scenarios_passed": all(item["passed"] for item in results),
        "v1_preserved": [
            "src/congressional_globe/productive_ocr_fit.py unchanged",
            "artifacts/owned-ocr-transport-20261028-03 evidence unchanged",
            "artifacts/native-preprocessing-study-20261029-01 evidence unchanged",
        ],
        "caps_retained": {"input_tokens": 6000, "output_tokens": 1500, "requests": 7},
        "blockers": [
            "no authentic complete native preprocessing producer exists",
            "installed dirty-build source parity is unproved",
            "actual backend compatibility and stopping are unproved",
            "trusted T55 clearance is absent",
        ],
    }
    (OUT / "fixture-trace.json").write_bytes(raw)
    (OUT / "fixture-projection.json").write_bytes(
        canonical_json(projection.model_dump(mode="json"))
    )
    (OUT / "patch-tensor.bin").write_bytes(PATCH_BYTES)
    (OUT / "positions.bin").write_bytes(POSITION_BYTES)
    (OUT / "validation.json").write_bytes(canonical_json(out))
    print(json.dumps({"all_scenarios_passed": out["all_scenarios_passed"], "results": results}))
    return 0 if out["all_scenarios_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
