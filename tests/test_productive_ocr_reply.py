"""Source binding and replay checks for productive OCR v2 replies."""

import hashlib
import json

import pytest

from congressional_globe.productive_ocr_reply import validate_reply


def _host(raw: str, *, static: str | None = None, with_context: bool = False) -> dict:
    raw_hash = hashlib.sha256(raw.encode()).hexdigest()
    static = raw if static is None else static
    paragraphs = [
        {
            "alias": "P1",
            "source_id": "fixture:1:paragraph-1",
            "part_number": 1,
            "scan_leaf": 1,
            "role": "target",
            "raw": {"text": raw, "sha256": raw_hash},
            "static": {
                "text": static,
                "sha256": hashlib.sha256(static.encode()).hexdigest(),
                "edits": [],
            },
        }
    ]
    image_bindings = [
        {
            "paragraph_alias": "P1",
            "raw_sha256": raw_hash,
            "raw_start": 0,
            "raw_end": len(raw),
            "crop_region": {"left": 0, "top": 0, "right": 100, "bottom": 100},
        }
    ]
    if with_context:
        context = "Adjacent context."
        context_hash = hashlib.sha256(context.encode()).hexdigest()
        paragraphs.append(
            {
                "alias": "P2",
                "source_id": "fixture:1:context",
                "part_number": 1,
                "scan_leaf": 1,
                "role": "context",
                "raw": {"text": context, "sha256": context_hash},
                "static": {"text": context, "sha256": context_hash, "edits": []},
            }
        )
        image_bindings.append(
            {
                "paragraph_alias": "P2",
                "raw_sha256": context_hash,
                "raw_start": 0,
                "raw_end": len(context),
                "crop_region": {"left": 0, "top": 0, "right": 100, "bottom": 100},
            }
        )
    return {
        "packet_sha256": "a" * 64,
        "payload": {
            "contract": "ocr-productive-repair-host-input-v2",
            "role": "productive_repair_and_self_check",
            "unit_id": "unit-1",
            "paragraphs": paragraphs,
            "image": {
                "alias": "I1",
                "sha256": "1" * 64,
                "mime": "image/png",
                "width": 100,
                "height": 100,
                "bindings": image_bindings,
                "registration_status": "verified",
                "legibility_status": "checked",
                "source_item_identifier": "fixture",
                "source_scan_leaf": 1,
                "hocr_sha256": "2" * 64,
                "page_map_sha256": "3" * 64,
                "binding_manifest_sha256": "4" * 64,
                "registration_evidence_sha256": "5" * 64,
            },
            "diagnostics": {},
            "saved_proposal": None,
            "prompt_sha256": "b" * 64,
            "response_schema_sha256": "c" * 64,
            "code_sha256": "d" * 64,
            "model_digest": "e" * 64,
            "sampling_manifest_sha256": "f" * 64,
            "bounds_sha256": "0" * 64,
        },
    }


def _reply(raw: str, *, status="no_finding", findings=None, patches=None, reading=None):
    checked = [
        "all_words",
        "names_places",
        "numbers",
        "punctuation",
        "printed_repetition",
        "bracketed_cues",
        "target_context_boundaries",
        "unflagged_text",
        "static_edits",
    ]
    return {
        "contract": "ocr-productive-repair-reply-v2",
        "unit_id": "unit-1",
        "role": "productive_repair_and_self_check",
        "status": status,
        "inspections": [
            {
                "paragraph_alias": "P1",
                "image_alias": "I1",
                "completeness": "complete",
                "image_suitability": "clear",
                "reason": None,
            }
        ],
        "findings": findings or [],
        "patches": patches or [],
        "reason": None,
        "target_readings": [
            {
                "paragraph_alias": "P1",
                "image_alias": "I1",
                "reading_status": "unchanged",
                "proposed_text": raw,
                "uncertainties": [],
                "reason": None,
            }
        ]
        if reading is None
        else reading,
        "self_check": [
            {
                "paragraph_alias": "P1",
                "coverage": "complete",
                "checked_content": checked,
                "remaining_concerns": [],
            }
        ],
    }


def test_unchanged_full_reading_is_explicitly_proposal_only():
    raw = "Mr. Fessenden spoke. [Laughter.]"
    mapped = validate_reply(json.dumps(_reply(raw)), _host(raw))
    assert mapped["proposed_readings"]["P1"]["text"] == raw
    assert mapped["historical_status"] == "proposal_only_not_human_reviewed"
    assert mapped["proposed_readings"]["P1"]["bracket_concern"]["status"] == "same_literal_sequence"


def test_exact_patch_replays_from_raw_and_maps_support():
    raw = "The year was 1866."
    finding = {
        "finding_id": "F1",
        "anchor": {"paragraph_alias": "P1", "scope": "quote", "raw_quote": raw},
        "affected_layer": "raw",
        "affected_quote": raw,
        "category": "number_concern",
        "resolution": "proposed",
        "proposed_reading": "The year was 1865.",
        "image_alias": "I1",
        "basis": "visible_print",
        "explanation": "Visible print appears to read 1865.",
    }
    patch = {
        "finding_id": "F1",
        "paragraph_alias": "P1",
        "raw_quote": "1866",
        "replacement": "1865",
        "image_alias": "I1",
        "reason": "Visible print appears to read 1865.",
    }
    reading = [
        {
            "paragraph_alias": "P1",
            "image_alias": "I1",
            "reading_status": "proposed",
            "proposed_text": "The year was 1865.",
            "uncertainties": [],
            "reason": None,
        }
    ]
    out = validate_reply(
        json.dumps(
            _reply(raw, status="findings", findings=[finding], patches=[patch], reading=reading)
        ),
        _host(raw),
    )
    assert out["proposed_readings"]["P1"]["text"] == "The year was 1865."
    assert out["proposed_readings"]["P1"]["patches"][0]["start"] == 13


def test_repeated_quote_is_not_guessed():
    raw = "a word and a word"
    finding = {
        "finding_id": "F1",
        "anchor": {"paragraph_alias": "P1", "scope": "quote", "raw_quote": "word"},
        "affected_layer": "raw",
        "affected_quote": "word",
        "category": "other_damage",
        "resolution": "unresolved",
        "proposed_reading": None,
        "image_alias": "I1",
        "basis": "image_unclear",
        "explanation": "The repeated occurrence is ambiguous.",
    }
    with pytest.raises(ValueError, match="exactly once"):
        validate_reply(json.dumps(_reply(raw, status="unresolved", findings=[finding])), _host(raw))


def test_replayed_text_must_equal_full_reading():
    raw = "The year was 1866."
    finding = {
        "finding_id": "F1",
        "anchor": {"paragraph_alias": "P1", "scope": "quote", "raw_quote": "1866"},
        "affected_layer": "raw",
        "affected_quote": "1866",
        "category": "number_concern",
        "resolution": "proposed",
        "proposed_reading": "1865",
        "image_alias": "I1",
        "basis": "visible_print",
        "explanation": "Visible print appears different.",
    }
    patch = {
        "finding_id": "F1",
        "paragraph_alias": "P1",
        "raw_quote": "1866",
        "replacement": "1865",
        "image_alias": "I1",
        "reason": "Visible print appears different.",
    }
    reading = [
        {
            "paragraph_alias": "P1",
            "image_alias": "I1",
            "reading_status": "proposed",
            "proposed_text": "The year was 1864.",
            "uncertainties": [],
            "reason": None,
        }
    ]
    with pytest.raises(ValueError, match="does not exactly replay"):
        validate_reply(
            json.dumps(
                _reply(raw, status="findings", findings=[finding], patches=[patch], reading=reading)
            ),
            _host(raw),
        )


def test_derived_quote_inverse_map_requires_exact_layer_replay():
    from congressional_globe.deterministic_models import ExactEdit
    from congressional_globe.productive_ocr_binding import inverse_quote_support

    raw = "A well- known rule."
    edit = ExactEdit(start=6, end=8, raw_quote="- ", replacement="", rule_id="fixture")
    assert inverse_quote_support(raw, "A wellknown rule.", "wellknown", (edit,)) == (
        2,
        11,
        2,
        13,
    )
    with pytest.raises(ValueError, match="does not replay"):
        inverse_quote_support(raw, "A well-known rule.", "well-known", (edit,))


def test_overlapping_occurrences_are_ambiguous():
    from congressional_globe.productive_ocr_binding import unique_quote_span

    with pytest.raises(ValueError, match="exactly once"):
        unique_quote_span("aaaa", "aaa")


def _example_host(case: dict) -> dict:
    raw = case["raw_text"]
    static = case["static_text"]
    raw_hash = hashlib.sha256(raw.encode()).hexdigest()
    static_edits = []
    if raw != static:
        old = "- "
        start = raw.index(old)
        static_edits = [
            {
                "edit_id": "static-1",
                "raw_start": start,
                "raw_end": start + 2,
                "expected": old,
                "replacement": "",
                "reason": "Synthetic fixture layer.",
            }
        ]
    alias = "P1"
    paragraph = {
        "alias": alias,
        "source_id": f"fixture:1:{case['id']}",
        "part_number": 1,
        "scan_leaf": 1,
        "role": "target",
        "raw": {"text": raw, "sha256": raw_hash},
        "static": {
            "text": static,
            "sha256": hashlib.sha256(static.encode()).hexdigest(),
            "edits": static_edits,
        },
    }
    image = None
    if case["id"] != "EX4":
        image = {
            "alias": "I1",
            "sha256": "1" * 64,
            "mime": "image/png",
            "width": 100,
            "height": 100,
            "bindings": [
                {
                    "paragraph_alias": alias,
                    "raw_sha256": raw_hash,
                    "raw_start": 0,
                    "raw_end": len(raw),
                    "crop_region": {"left": 0, "top": 0, "right": 100, "bottom": 100},
                }
            ],
            "registration_status": "verified",
            "legibility_status": "checked",
            "source_item_identifier": "fixture",
            "source_scan_leaf": 1,
            "hocr_sha256": "2" * 64,
            "page_map_sha256": "3" * 64,
            "binding_manifest_sha256": "4" * 64,
            "registration_evidence_sha256": "5" * 64,
        }
    role = case["provider_reply"]["role"]
    saved = None
    if role == "audit_saved_proposal":
        proposal_text = "We know that is correct."
        deletion = raw.rfind("that ")
        saved = {
            "record_sha256": "6" * 64,
            "prior_request_sha256": "7" * 64,
            "prior_raw_reply_sha256": "8" * 64,
            "review_state": "unreviewed_model_proposal",
            "paragraphs": [
                {
                    "paragraph_alias": alias,
                    "text": proposal_text,
                    "sha256": hashlib.sha256(proposal_text.encode()).hexdigest(),
                    "raw_edits": [
                        {
                            "edit_id": "saved-1",
                            "raw_start": deletion,
                            "raw_end": deletion + 5,
                            "expected": "that ",
                            "replacement": "",
                            "reason": "Synthetic saved proposal.",
                        }
                    ],
                }
            ],
        }
    payload = {
        "contract": "ocr-productive-repair-host-input-v2",
        "role": role,
        "unit_id": case["id"],
        "paragraphs": [paragraph],
        "image": image,
        "diagnostics": {
            "status": "not_run",
            "detector_sha256": None,
            "configuration_sha256": None,
            "signals": [],
            "negative_targets": [],
        },
        "saved_proposal": saved,
        "prompt_sha256": "a" * 64,
        "response_schema_sha256": "b" * 64,
        "code_sha256": "c" * 64,
        "model_digest": "d" * 64,
        "sampling_manifest_sha256": "e" * 64,
        "bounds_sha256": "f" * 64,
    }
    return {"packet_sha256": "0" * 64, "payload": payload}


def _check_example(case: dict) -> None:
    result = validate_reply(json.dumps(case["provider_reply"]), _example_host(case))
    assert result["model_proposal"]["unit_id"] == case["id"]
    assert result["historical_status"] == "proposal_only_not_human_reviewed"
    assert result["quality_status"] == "not_established_by_structural_validation"
    if case["provider_reply"]["role"] == "productive_repair_and_self_check":
        assert set(result["proposed_readings"]) == {"P1"}
        _check_example_reading(case, result)


def _check_example_reading(case: dict, result: dict) -> None:
    if case["provider_reply"]["status"] in {"incomplete", "unresolved"}:
        assert result["proposed_readings"]["P1"] == {}


def test_all_t69_authored_examples_bind_and_replay_structurally():
    from pathlib import Path

    cases = json.loads(
        Path("artifacts/ocr-productive-repair-contract-20261027-01/examples.json").read_text()
    )["cases"]
    for case in cases:
        _check_example(case)


def test_duplicate_or_foreign_reply_aliases_fail_closed():
    raw = "A short line."
    for field in ("inspections", "self_check", "target_readings"):
        reply = _reply(raw)
        reply[field].append(dict(reply[field][0]))
        with pytest.raises(ValueError, match="exactly once"):
            validate_reply(json.dumps(reply), _host(raw))
        reply = _reply(raw)
        reply[field][0]["paragraph_alias"] = "P2"
        with pytest.raises(ValueError, match="exactly once"):
            validate_reply(json.dumps(reply), _host(raw))


def test_withheld_unresolved_preserves_bound_uncertainty_without_partial_reading():
    raw = "The amount is $10,000."
    reply = _reply(raw, status="unresolved")
    reply["reason"] = "Image unavailable."
    reply["inspections"][0].update(completeness="not_inspected", image_suitability="missing")
    reply["target_readings"] = [
        {
            "paragraph_alias": "P1",
            "image_alias": "I1",
            "reading_status": "withheld",
            "proposed_text": None,
            "uncertainties": [{"raw_quote": "$10,000", "reason": "Unreadable."}],
            "reason": "Image unavailable.",
        }
    ]
    result = validate_reply(json.dumps(reply), _host(raw))
    assert result["proposed_readings"] == {"P1": {}}


def test_complete_target_reply_accepts_registered_context_binding():
    raw = "A short line."
    mapped = validate_reply(json.dumps(_reply(raw)), _host(raw, with_context=True))
    assert mapped["proposed_readings"]["P1"]["text"] == raw


def test_withheld_unresolved_allows_paragraph_wide_uncertainty():
    raw = "The amount is $10,000."
    reply = _reply(raw, status="unresolved")
    reply["reason"] = "The full line is unreadable."
    reply["inspections"][0].update(completeness="not_inspected", image_suitability="missing")
    reply["target_readings"] = [
        {
            "paragraph_alias": "P1",
            "image_alias": "I1",
            "reading_status": "withheld",
            "proposed_text": None,
            "uncertainties": [{"raw_quote": None, "reason": "Full-line uncertainty."}],
            "reason": "The full line is unreadable.",
        }
    ]
    result = validate_reply(json.dumps(reply), _host(raw))
    assert result["proposed_readings"]["P1"] == {}


def test_audit_complete_status_requires_full_inspection_and_self_check():
    from pathlib import Path

    cases = json.loads(
        Path("artifacts/ocr-productive-repair-contract-20261027-01/examples.json").read_text()
    )["cases"]
    case = next(item for item in cases if item["id"] == "EX5")
    reply = case["provider_reply"]
    reply["self_check"][0]["checked_content"].pop()
    with pytest.raises(ValueError, match="full inspection"):
        validate_reply(json.dumps(reply), _example_host(case))


def test_no_finding_cannot_hide_self_check_concerns():
    raw = "A short line."
    reply = _reply(raw)
    reply["self_check"][0]["remaining_concerns"] = ["A word may be wrong."]
    with pytest.raises(ValueError, match="complete inspection"):
        validate_reply(json.dumps(reply), _host(raw))


def test_patch_cannot_exceed_broad_finding_proposed_reading():
    raw = "The public doubt remains."
    finding = {
        "finding_id": "F1",
        "anchor": {"paragraph_alias": "P1", "scope": "whole_paragraph", "raw_quote": None},
        "affected_layer": "raw",
        "affected_quote": None,
        "category": "source_uncertainty",
        "resolution": "unresolved",
        "proposed_reading": None,
        "image_alias": "I1",
        "basis": "image_unclear",
        "explanation": "The target is unclear.",
    }
    patch = {
        "finding_id": "F1",
        "paragraph_alias": "P1",
        "raw_quote": "doubt",
        "replacement": "debt",
        "image_alias": "I1",
        "reason": "Looks different.",
    }
    reply = _reply(
        raw,
        status="findings",
        findings=[finding],
        patches=[patch],
        reading=[
            {
                "paragraph_alias": "P1",
                "image_alias": "I1",
                "reading_status": "proposed",
                "proposed_text": "The public debt remains.",
                "uncertainties": [],
                "reason": None,
            }
        ],
    )
    with pytest.raises(ValueError, match="proposed visible-print"):
        validate_reply(json.dumps(reply), _host(raw))


def test_audit_role_cannot_return_repairs():
    raw = "A short line."
    host = _host(raw)
    host["payload"]["role"] = "audit_saved_proposal"
    host["payload"]["paragraphs"][0]["source_id"] = "fixture:1:audit"
    host["payload"]["saved_proposal"] = {
        "record_sha256": "6" * 64,
        "prior_request_sha256": "7" * 64,
        "prior_raw_reply_sha256": "8" * 64,
        "review_state": "unreviewed_model_proposal",
        "paragraphs": [
            {
                "paragraph_alias": "P1",
                "text": raw,
                "sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "raw_edits": [],
            }
        ],
    }
    reply = _reply(raw)
    reply["role"] = "audit_saved_proposal"
    reply["target_readings"] = []
    reply["patches"] = [
        {
            "finding_id": "F1",
            "paragraph_alias": "P1",
            "raw_quote": "short",
            "replacement": "brief",
            "image_alias": "I1",
            "reason": "Audit test.",
        }
    ]
    with pytest.raises(ValueError, match="cannot introduce readings or patches"):
        validate_reply(json.dumps(reply), host)


def test_missing_inspection_self_check_or_reading_is_rejected():
    raw = "A short line."
    for field in ("inspections", "self_check", "target_readings"):
        reply = _reply(raw)
        reply[field] = []
        with pytest.raises(ValueError, match=r"invalid productive OCR reply|exactly once"):
            validate_reply(json.dumps(reply), _host(raw))


def test_unsupported_derived_finding_quote_is_rejected():
    raw = "A well- known rule."
    static = "A wellknown rule."
    host = _host(raw, static=static)
    host["payload"]["paragraphs"][0]["static"]["edits"] = [
        {
            "edit_id": "static-1",
            "raw_start": 6,
            "raw_end": 8,
            "expected": "- ",
            "replacement": "",
            "reason": "Synthetic static edit.",
        }
    ]
    finding = {
        "finding_id": "F1",
        "anchor": {"paragraph_alias": "P1", "scope": "quote", "raw_quote": "well- known"},
        "affected_layer": "static",
        "affected_quote": "missing",
        "category": "incorrect_static_edit",
        "resolution": "proposed",
        "proposed_reading": "well- known",
        "image_alias": "I1",
        "basis": "visible_print",
        "explanation": "Synthetic fixture.",
    }
    reply = _reply(
        raw,
        status="findings",
        findings=[finding],
        reading=[
            {
                "paragraph_alias": "P1",
                "image_alias": "I1",
                "reading_status": "unchanged",
                "proposed_text": raw,
                "uncertainties": [],
                "reason": None,
            }
        ],
    )
    with pytest.raises(ValueError, match="exactly once"):
        validate_reply(json.dumps(reply), host)


def test_broader_finding_reading_must_reconcile_all_linked_patches():
    raw = "The public doubt remains."
    finding = {
        "finding_id": "F1",
        "anchor": {"paragraph_alias": "P1", "scope": "whole_paragraph", "raw_quote": None},
        "affected_layer": "raw",
        "affected_quote": raw,
        "category": "other_damage",
        "resolution": "proposed",
        "proposed_reading": "The public debt stays.",
        "image_alias": "I1",
        "basis": "visible_print",
        "explanation": "Synthetic broad anchor.",
    }
    patch = {
        "finding_id": "F1",
        "paragraph_alias": "P1",
        "raw_quote": "doubt",
        "replacement": "debt",
        "image_alias": "I1",
        "reason": "Synthetic patch.",
    }
    reply = _reply(
        raw,
        status="findings",
        findings=[finding],
        patches=[patch],
        reading=[
            {
                "paragraph_alias": "P1",
                "image_alias": "I1",
                "reading_status": "proposed",
                "proposed_text": "The public debt remains.",
                "uncertainties": [],
                "reason": None,
            }
        ],
    )
    with pytest.raises(ValueError, match="contradicts"):
        validate_reply(json.dumps(reply), _host(raw))


def test_structural_pass_does_not_claim_a_wrong_name_is_image_correct():
    raw = "Mr. Fessenden spoke."
    finding = {
        "finding_id": "F1",
        "anchor": {"paragraph_alias": "P1", "scope": "quote", "raw_quote": "Fessenden"},
        "affected_layer": "raw",
        "affected_quote": "Fessenden",
        "category": "name_place_concern",
        "resolution": "proposed",
        "proposed_reading": "Fessendcn",
        "image_alias": "I1",
        "basis": "visible_print",
        "explanation": "Synthetic intentionally incorrect visual claim.",
    }
    patch = {
        "finding_id": "F1",
        "paragraph_alias": "P1",
        "raw_quote": "Fessenden",
        "replacement": "Fessendcn",
        "image_alias": "I1",
        "reason": "Synthetic claim.",
    }
    reply = _reply(
        raw,
        status="findings",
        findings=[finding],
        patches=[patch],
        reading=[
            {
                "paragraph_alias": "P1",
                "image_alias": "I1",
                "reading_status": "proposed",
                "proposed_text": "Mr. Fessendcn spoke.",
                "uncertainties": [],
                "reason": None,
            }
        ],
    )
    result = validate_reply(json.dumps(reply), _host(raw))
    assert result["proposed_readings"]["P1"]["text"] == "Mr. Fessendcn spoke."
    assert result["quality_status"] == "not_established_by_structural_validation"


def test_null_affected_quote_requires_unresolved_whole_paragraph_anchor():
    raw = "A repeated word."
    finding = {
        "finding_id": "F1",
        "anchor": {"paragraph_alias": "P1", "scope": "quote", "raw_quote": "repeated"},
        "affected_layer": "raw",
        "affected_quote": None,
        "category": "source_uncertainty",
        "resolution": "unresolved",
        "proposed_reading": None,
        "image_alias": "I1",
        "basis": "image_unclear",
        "explanation": "Synthetic uncertainty.",
    }
    reply = _reply(raw, status="unresolved", findings=[finding])
    reply["reason"] = "The quote is unclear."
    reply["target_readings"] = [
        {
            "paragraph_alias": "P1",
            "image_alias": "I1",
            "reading_status": "withheld",
            "proposed_text": None,
            "uncertainties": [],
            "reason": "The quote is unclear.",
        }
    ]
    with pytest.raises(ValueError, match="null affected quote"):
        validate_reply(json.dumps(reply), _host(raw))


def test_patch_with_dangling_finding_id_is_rejected():
    raw = "A short line."
    reply = _reply(
        raw,
        status="findings",
        findings=[
            {
                "finding_id": "F1",
                "anchor": {"paragraph_alias": "P1", "scope": "quote", "raw_quote": "short"},
                "affected_layer": "raw",
                "affected_quote": "short",
                "category": "other_damage",
                "resolution": "proposed",
                "proposed_reading": "brief",
                "image_alias": "I1",
                "basis": "visible_print",
                "explanation": "Synthetic finding.",
            }
        ],
        patches=[
            {
                "finding_id": "F2",
                "paragraph_alias": "P1",
                "raw_quote": "short",
                "replacement": "brief",
                "image_alias": "I1",
                "reason": "Synthetic patch.",
            }
        ],
        reading=[
            {
                "paragraph_alias": "P1",
                "image_alias": "I1",
                "reading_status": "proposed",
                "proposed_text": "A brief line.",
                "uncertainties": [],
                "reason": None,
            }
        ],
    )
    with pytest.raises(ValueError, match="dangling finding"):
        validate_reply(json.dumps(reply), _host(raw))
