"""Focused tests for offline productive OCR packet validation and projection."""

import hashlib
import io
import json

import pytest
from PIL import Image

from congressional_globe.productive_ocr_host import (
    EvidenceRecord,
    EvidenceRegistry,
    canonical_json,
    project_provider,
    sha256_bytes,
    text_sha256,
    validate_host,
)


def _packet(
    registry_files: dict[str, bytes], *, with_context: bool = False
) -> tuple[dict, EvidenceRegistry]:
    raw = "By Mr. Example."
    img = Image.new("RGB", (40, 30), "white")
    stream = io.BytesIO()
    img.save(stream, format="PNG")
    image_bytes = stream.getvalue()
    image_hash = sha256_bytes(image_bytes)
    hocr_data, page_data, rule_data, lexicon_data = b"hocr", b"page-map", b"rule", b"lexicon"
    hashes = list(map(sha256_bytes, (hocr_data, page_data, rule_data, lexicon_data)))
    registry_files.update(
        dict(zip(hashes, (hocr_data, page_data, rule_data, lexicon_data), strict=True))
    )
    expected_identity = {
        "sha256": image_hash,
        "source_item_identifier": "item-1",
        "source_scan_leaf": 2,
        "hocr_sha256": hashes[0],
        "page_map_sha256": hashes[1],
        "width": 40,
        "height": 30,
    }
    target_box = {"left": 1, "top": 2, "right": 30, "bottom": 20}
    context_box = {"left": 2, "top": 21, "right": 30, "bottom": 29}
    paragraph_boxes = {"P1": target_box}
    raw_layer = {"text": raw, "sha256": text_sha256(raw)}
    static = {
        "text": raw,
        "sha256": text_sha256(raw),
        "edits": [],
        "rule_sha256": hashes[2],
        "lexicon_sha256": hashes[3],
    }
    paragraphs = [
        {
            "alias": "P1",
            "source_id": "item-1:2:p1",
            "part_number": 1,
            "scan_leaf": 2,
            "role": "target",
            "raw": raw_layer,
            "static": static,
        }
    ]
    bindings = [
        {
            "paragraph_alias": "P1",
            "raw_sha256": text_sha256(raw),
            "raw_start": 0,
            "raw_end": len(raw),
            "crop_region": target_box,
        }
    ]
    if with_context:
        context = "Adjacent context."
        context_layer = {"text": context, "sha256": text_sha256(context)}
        context_static = {**static, "text": context, "sha256": text_sha256(context)}
        paragraphs.append(
            {
                "alias": "P2",
                "source_id": "item-1:2:p2",
                "part_number": 2,
                "scan_leaf": 2,
                "role": "context",
                "raw": context_layer,
                "static": context_static,
            }
        )
        bindings.append(
            {
                "paragraph_alias": "P2",
                "raw_sha256": text_sha256(context),
                "raw_start": 0,
                "raw_end": len(context),
                "crop_region": context_box,
            }
        )
        paragraph_boxes["P2"] = context_box
    paragraph_bindings = {
        item["paragraph_alias"]: {
            "raw_sha256": item["raw_sha256"],
            "raw_start": item["raw_start"],
            "raw_end": item["raw_end"],
        }
        for item in bindings
    }
    binding_record = {
        **expected_identity,
        "paragraph_boxes": paragraph_boxes,
        "paragraph_bindings": paragraph_bindings,
        "paragraph_order": list(paragraph_boxes),
    }
    legibility_record = {
        "image_sha256": image_hash,
        "source_item_identifier": "item-1",
        "source_scan_leaf": 2,
        "status": "checked",
        "scope": "whole_registered_crop",
        "method": "synthetic software fixture metadata",
        "notes": "White test image only; this does not establish print legibility.",
    }
    legibility_data = canonical_json(legibility_record)
    legibility_hash = sha256_bytes(legibility_data)
    registry_files[legibility_hash] = legibility_data
    registration_record = {
        **expected_identity,
        "paragraph_boxes": paragraph_boxes,
        "paragraph_order": list(paragraph_boxes),
        "legibility_evidence_sha256": legibility_hash,
    }
    binding_data, registration_data = map(canonical_json, (binding_record, registration_record))
    binding_hash, registration_hash = map(sha256_bytes, (binding_data, registration_data))
    registry_files[binding_hash] = binding_data
    registry_files[registration_hash] = registration_data
    payload = {
        "contract": "ocr-productive-repair-host-input-v2",
        "role": "productive_repair_and_self_check",
        "unit_id": "U1",
        "paragraphs": paragraphs,
        "image": {
            "alias": "I1",
            "sha256": image_hash,
            "mime": "image/png",
            "width": 40,
            "height": 30,
            "bindings": bindings,
            "registration_status": "verified",
            "legibility_status": "checked",
            "source_item_identifier": "item-1",
            "source_scan_leaf": 2,
            "hocr_sha256": hashes[0],
            "page_map_sha256": hashes[1],
            "binding_manifest_sha256": binding_hash,
            "registration_evidence_sha256": registration_hash,
        },
        "diagnostics": {
            "status": "frozen",
            "detector_sha256": sha256_bytes(b"detector"),
            "configuration_sha256": sha256_bytes(b"config"),
            "signals": [],
            "negative_targets": ["P1"],
        },
        "saved_proposal": None,
        "prompt_sha256": sha256_bytes(b"prompt"),
        "response_schema_sha256": sha256_bytes(b"schema"),
        "code_sha256": sha256_bytes(b"code"),
        "model_digest": sha256_bytes(b"model"),
        "sampling_manifest_sha256": sha256_bytes(b"sampling"),
        "bounds_sha256": sha256_bytes(b"bounds"),
    }
    for content in (
        b"prompt",
        b"schema",
        b"code",
        b"model",
        b"sampling",
        b"bounds",
        b"detector",
        b"config",
    ):
        registry_files[sha256_bytes(content)] = content
    registry_records = {
        binding_hash: EvidenceRecord(binding_record, binding_data),
        registration_hash: EvidenceRecord(registration_record, registration_data),
    }
    packet = {"packet_sha256": sha256_bytes(canonical_json(payload)), "payload": payload}
    return packet, EvidenceRegistry({image_hash: image_bytes}, registry_records, registry_files)


def _rehash(packet: dict) -> None:
    packet["packet_sha256"] = sha256_bytes(canonical_json(packet["payload"]))


def test_valid_host_packet_projects_exact_provider_shape() -> None:
    packet, registry = _packet({})
    validated = validate_host(packet, registry)
    projection = project_provider(validated)
    assert set(projection) == {
        "contract",
        "reply_contract",
        "unit_id",
        "role",
        "image_alias",
        "target_regions",
        "context_regions",
        "paragraphs",
        "diagnostics",
        "saved_proposal",
    }
    assert projection["paragraphs"][0]["raw_text"] == "By Mr. Example."
    assert projection["target_regions"][0]["paragraph_alias"] == "P1"


def test_packet_hash_binds_payload_and_image_bytes_are_verified() -> None:
    packet, registry = _packet({})
    packet["payload"]["unit_id"] = "changed"
    with pytest.raises(ValueError, match="packet hash"):
        validate_host(packet, registry)

    packet, registry = _packet({})
    image_hash = packet["payload"]["image"]["sha256"]
    registry.image_bytes[image_hash] = b"not an image"
    with pytest.raises(ValueError, match="image bytes"):
        validate_host(packet, registry)


def test_raw_hash_and_geometry_proof_are_not_status_only() -> None:
    packet, registry = _packet({})
    packet["payload"]["paragraphs"][0]["raw"]["sha256"] = hashlib.sha256(b"wrong").hexdigest()
    packet["packet_sha256"] = sha256_bytes(canonical_json(packet["payload"]))
    with pytest.raises(ValueError, match="raw text hash"):
        validate_host(packet, registry)


def test_context_geometry_remains_context_in_provider_projection() -> None:
    packet, registry = _packet({}, with_context=True)
    projected = project_provider(validate_host(packet, registry))
    assert [x["paragraph_alias"] for x in projected["target_regions"]] == ["P1"]
    assert [x["paragraph_alias"] for x in projected["context_regions"]] == ["P2"]
    assert [x["role"] for x in projected["paragraphs"]] == ["target", "context"]


def test_incomplete_draft_cannot_be_projected_for_dispatch() -> None:
    packet, registry = _packet({})
    packet["payload"]["diagnostics"] = {
        "status": "not_run",
        "detector_sha256": None,
        "configuration_sha256": None,
        "signals": [],
        "negative_targets": [],
    }
    _rehash(packet)
    assert validate_host(packet, registry)
    with pytest.raises(ValueError, match="diagnostics must be frozen"):
        project_provider(validate_host(packet, registry))


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("image", "sha256"), "0" * 64, "image bytes"),
        (("image", "width"), 39, "dimensions"),
        (("image", "registration_status"), "unknown", "registration"),
    ],
)
def test_image_identity_dimensions_and_status_are_verified(path, value, message) -> None:
    packet, registry = _packet({})
    packet["payload"][path[0]][path[1]] = value
    _rehash(packet)
    with pytest.raises(ValueError, match=message):
        validate_host(packet, registry)


def test_unknown_static_resource_and_broken_edit_replay_fail() -> None:
    packet, registry = _packet({})
    packet["payload"]["paragraphs"][0]["static"]["rule_sha256"] = "0" * 64
    _rehash(packet)
    with pytest.raises(ValueError, match="static rule"):
        validate_host(packet, registry)

    packet, registry = _packet({})
    layer = packet["payload"]["paragraphs"][0]["static"]
    layer["edits"] = [
        {
            "edit_id": "E1",
            "raw_start": 0,
            "raw_end": 2,
            "expected": "XX",
            "replacement": "By",
            "reason": "test",
        }
    ]
    _rehash(packet)
    with pytest.raises(ValueError, match="exact raw quote"):
        validate_host(packet, registry)


def test_diagnostics_require_full_target_coverage_and_exact_raw_quote() -> None:
    packet, registry = _packet({})
    diag = packet["payload"]["diagnostics"]
    diag.update(
        status="frozen",
        detector_sha256=sha256_bytes(b"detector"),
        configuration_sha256=sha256_bytes(b"config"),
        negative_targets=[],
    )
    registry.files[diag["detector_sha256"]] = b"detector"
    registry.files[diag["configuration_sha256"]] = b"config"
    _rehash(packet)
    with pytest.raises(ValueError, match="signals or explicit detector-negative"):
        validate_host(packet, registry)

    diag["signals"] = [
        {
            "signal_id": "S1",
            "paragraph_alias": "P1",
            "raw_start": 0,
            "raw_end": 2,
            "raw_quote": "XX",
            "category": "word",
            "flags": [],
            "route_reason": "test",
        }
    ]
    _rehash(packet)
    with pytest.raises(ValueError, match="quote does not bind"):
        validate_host(packet, registry)

    diag["signals"] = []
    diag["negative_targets"] = ["P1"]
    _rehash(packet)
    assert validate_host(packet, registry)
    diag["negative_targets"] = ["P2"]
    _rehash(packet)
    with pytest.raises(ValueError, match="uniquely name declared targets"):
        validate_host(packet, registry)


def test_registered_source_item_leaf_and_geometry_proof_must_match() -> None:
    packet, registry = _packet({})
    packet["payload"]["image"]["source_scan_leaf"] = 9
    _rehash(packet)
    with pytest.raises(ValueError, match="source identity mismatch"):
        validate_host(packet, registry)

    packet, registry = _packet({})
    packet["payload"]["image"]["bindings"].append(packet["payload"]["image"]["bindings"][0])
    _rehash(packet)
    with pytest.raises(ValueError, match="bindings must cover"):
        validate_host(packet, registry)


def test_legibility_requires_hash_bound_whole_crop_evidence() -> None:
    packet, registry = _packet({})
    image = packet["payload"]["image"]
    registration_hash = image["registration_evidence_sha256"]
    registration = registry.records[registration_hash]
    legibility_hash = registration.record["legibility_evidence_sha256"]
    legibility_bytes = registry.files.pop(legibility_hash)
    with pytest.raises(ValueError, match="legibility evidence resource missing"):
        validate_host(packet, registry)
    registry.files[legibility_hash] = legibility_bytes

    wrong_proof = json.loads(legibility_bytes)
    wrong_proof["image_sha256"] = "0" * 64
    wrong_bytes = canonical_json(wrong_proof)
    wrong_hash = sha256_bytes(wrong_bytes)
    registry.files[wrong_hash] = wrong_bytes
    wrong_registration_record = {
        **registration.record,
        "legibility_evidence_sha256": wrong_hash,
    }
    wrong_registration_bytes = canonical_json(wrong_registration_record)
    wrong_registration_hash = sha256_bytes(wrong_registration_bytes)
    registry.files[wrong_registration_hash] = wrong_registration_bytes
    registry.records[wrong_registration_hash] = EvidenceRecord(
        wrong_registration_record, wrong_registration_bytes
    )
    image["registration_evidence_sha256"] = wrong_registration_hash
    _rehash(packet)
    with pytest.raises(ValueError, match="legibility evidence source identity mismatch"):
        validate_host(packet, registry)


def test_schema_rejects_missing_and_extra_nested_fields() -> None:
    packet, registry = _packet({})
    del packet["payload"]["paragraphs"][0]["static"]["lexicon_sha256"]
    _rehash(packet)
    with pytest.raises(ValueError):
        validate_host(packet, registry)


def test_saved_proposal_record_bytes_bind_exact_proposal_fields() -> None:
    packet, registry = _packet({})
    payload = packet["payload"]
    payload["role"] = "audit_saved_proposal"
    request, raw_reply = b"frozen previous request", b"frozen previous reply"
    prior_request_hash, prior_reply_hash = sha256_bytes(request), sha256_bytes(raw_reply)
    registry.files[prior_request_hash] = request
    registry.files[prior_reply_hash] = raw_reply
    raw = payload["paragraphs"][0]["raw"]["text"]
    paragraph = {
        "paragraph_alias": "P1",
        "text": "By Mr. Changed.",
        "sha256": text_sha256("By Mr. Changed."),
        "raw_edits": [
            {
                "edit_id": "E1",
                "raw_start": 7,
                "raw_end": 14,
                "expected": "Example",
                "replacement": "Changed",
                "reason": "saved proposal",
            }
        ],
    }
    assert _replay_for_test(raw, paragraph["raw_edits"]) == paragraph["text"]
    saved = {
        "prior_request_sha256": prior_request_hash,
        "prior_raw_reply_sha256": prior_reply_hash,
        "paragraphs": [paragraph],
        "review_state": "unreviewed_model_proposal",
    }
    record_bytes = canonical_json(saved)
    record_hash = sha256_bytes(record_bytes)
    registry.files[record_hash] = record_bytes
    payload["saved_proposal"] = {"record_sha256": record_hash, **saved}
    _rehash(packet)
    assert validate_host(packet, registry)

    changed = payload["saved_proposal"]["paragraphs"][0]
    changed["text"] = "By Mr. Replaced."
    changed["sha256"] = text_sha256(changed["text"])
    changed["raw_edits"][0]["replacement"] = "Replaced"
    _rehash(packet)
    with pytest.raises(ValueError, match="canonical proposal content"):
        validate_host(packet, registry)


def _replay_for_test(raw: str, edits: list[dict]) -> str:
    cursor, output = 0, []
    for edit in edits:
        assert raw[edit["raw_start"] : edit["raw_end"]] == edit["expected"]
        output.extend((raw[cursor : edit["raw_start"]], edit["replacement"]))
        cursor = edit["raw_end"]
    output.append(raw[cursor:])
    return "".join(output)

    packet, registry = _packet({})
    packet["payload"]["paragraphs"][0]["raw"]["unexpected"] = True
    _rehash(packet)
    with pytest.raises(ValueError):
        validate_host(packet, registry)


def test_saved_layers_reject_out_of_order_and_noop_edits():
    from congressional_globe.productive_ocr_host import _replay

    first = {"edit_id": "A", "raw_start": 0, "raw_end": 1, "expected": "a", "replacement": "A"}
    second = {"edit_id": "B", "raw_start": 2, "raw_end": 3, "expected": "b", "replacement": "B"}
    assert _replay("a b", [first, second], "fixture") == "A B"
    with pytest.raises(ValueError, match="ordered"):
        _replay("a b", [second, first], "fixture")
    with pytest.raises(ValueError, match="no-op"):
        _replay("a b", [{**first, "replacement": "a"}], "fixture")
