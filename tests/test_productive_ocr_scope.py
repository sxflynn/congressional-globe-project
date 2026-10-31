"""Actual T102 neighbouring-copy failure and source-derived target/context boundaries."""

import copy
import json
from functools import lru_cache
from pathlib import Path

import pytest

from congressional_globe.productive_ocr_host import (
    canonical_json,
    project_provider,
    sha256_bytes,
    validate_host,
)
from congressional_globe.productive_ocr_measurement_inputs import load_s5_conformance_inputs
from congressional_globe.productive_ocr_projection import compile_request_projection
from congressional_globe.productive_ocr_scope import (
    SCOPE_INSTRUCTION,
    _paragraphs,
    _rebind_geometry,
    _verify_context_budget,
    _verify_one_context,
    _visible_line,
    prepare_source_scope,
)
from congressional_globe.productive_ocr_text_reply import export_text_reply, validate_text_reply

BASE = Path("artifacts/s5-conformance-verification-20261030-01")
BUNDLE = Path("artifacts/ocr-live-readiness-20261028-01/images/S5/bundle.json")
CONTEXT = ("congressionalglo7395unit:529:par_000529_000007", "line_000529_000019")
EXPECTED = "The Committee on Appropriations recommended non-concurrence."
NEIGHBOUR = "The amendment was non-concurred in."


@lru_cache(maxsize=1)
def _case():
    legacy, _, registry = load_s5_conformance_inputs(Path("."))
    scoped = prepare_source_scope(legacy, registry, BUNDLE.read_bytes(), [CONTEXT])
    prompt = registry.files[scoped["payload"]["prompt_sha256"]].decode()
    projection, _schema = compile_request_projection(
        scoped, registry, prompt, "qwen3.8:27b-mlx", conformance_v4=True
    )
    return legacy, scoped, registry, projection


def _copy_case():
    legacy, scoped, registry, projection = _case()
    return legacy, copy.deepcopy(scoped), copy.deepcopy(registry), projection


def _actual():
    return json.loads((BASE / "run/result.json").read_bytes())["output_text"]


def _reply(text=EXPECTED):
    reply = json.loads(_actual())
    reply["readings"][0]["corrected_text"] = text
    return json.dumps(reply)


def _bind(host):
    host["packet_sha256"] = sha256_bytes(canonical_json(host["payload"]))


def _reprove_scope(host, registry):
    boxes = {
        entry["paragraph_alias"]: entry["crop_region"]
        for entry in host["payload"]["image"]["bindings"]
    }
    _rebind_geometry(host["payload"], registry, boxes)
    _bind(host)


def test_exact_target_roi_and_partial_context_use_original_pixels_and_parent_identity():
    legacy, host, registry, projection = _case()
    image = host["payload"]["image"]
    assert image["sha256"] == legacy["payload"]["image"]["sha256"]
    assert image["bindings"][0]["crop_region"] == dict(left=64, top=64, right=935, bottom=142)
    context = image["scope"]["visible_context"][0]
    assert context["source_id"] == CONTEXT[0]
    assert context["line_id"] == CONTEXT[1]
    assert context["text"] == NEIGHBOUR
    assert (context["raw_start"], context["raw_end"]) == (0, len(NEIGHBOUR))
    assert context["parent_visibility"] == "partial"
    assert context["crop_region"] == dict(left=105, top=149, right=842, bottom=184)
    assert host["payload"]["paragraphs"] == legacy["payload"]["paragraphs"]
    assert SCOPE_INSTRUCTION in registry.files[host["payload"]["prompt_sha256"]].decode()
    assert json.loads(projection.body_utf8)["messages"][1]["images"]


def test_provider_gets_only_visible_context_not_hidden_parent_remainder():
    _legacy, host, _, _ = _case()
    provider = project_provider(host)
    assert provider["contract"] == "ocr-productive-repair-input-v4"
    assert provider["image_frame"] == dict(
        width=999, height=206, coordinates="pixels; origin top-left; right/bottom exclusive"
    )
    assert provider["visible_context_spans"][0]["text"] == NEIGHBOUR
    assert "Twenty-sixth" not in json.dumps(provider)
    assert provider["target_regions"][0]["crop_region"] == dict(
        left=64, top=64, right=935, bottom=142
    )
    assert len(provider["paragraphs"]) == 1


def test_saved_actual_copy_is_rejected_on_new_input_without_rewriting_old_result():
    legacy, host, _, _ = _case()
    actual = _actual()
    assert validate_text_reply(actual, legacy)["proposal_status"] == "findings"
    with pytest.raises(ValueError, match="visible neighbouring"):
        validate_text_reply(actual, host)
    assert json.loads((BASE / "run/result.json").read_bytes())["measurement_status"] == "unresolved"


@pytest.mark.parametrize(
    "text",
    [
        EXPECTED + " " + NEIGHBOUR,
        NEIGHBOUR + " " + EXPECTED,
        EXPECTED + "\nThe amendment was non concurred in.",
        EXPECTED + " THE AMENDMENT WAS NON-CONCURRED IN!",
        EXPECTED + " " + NEIGHBOUR + " " + NEIGHBOUR,
    ],
)
def test_copied_visible_context_rejects_placement_spacing_case_and_hyphen_variants(text):
    _, host, _, _ = _case()
    with pytest.raises(ValueError, match="visible neighbouring"):
        validate_text_reply(_reply(text), host)


@pytest.mark.parametrize(
    "text", [EXPECTED, "The Committee on- Appropriations recom- mended non-concurrence."]
)
def test_valid_whole_target_and_unchanged_audit_preserve_genuine_hyphen_and_provenance(text):
    _, host, _, projection = _case()
    exported = export_text_reply(host, projection.body_utf8, _reply(text))
    assert exported.outcome["derived_proposals"][0]["text"] == text
    assert "non-concurrence." in text
    assert exported.model_dump()["boundary_scope"] == host["payload"]["image"]["scope"]
    assert (
        exported.model_dump()["boundary_check"]
        == "visible_context_exclusion_not_full_source_fidelity"
    )
    assert exported.acceptance == "unreviewed_ai_evidence"


def test_uncertain_target_withholds_text_without_a_scope_claim():
    _, host, _, _ = _case()
    reply = json.loads(_reply())
    reply["readings"][0].update(
        coverage="incomplete", corrected_text=None, reason="Target extent cannot be determined."
    )
    checked = validate_text_reply(json.dumps(reply), host)
    assert checked["proposal_status"] == "unresolved"
    assert checked["derived_proposals"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("text", "The Senate was non-concurred in."),
        ("paragraph_sha256", "a" * 64),
        ("raw_start", 1),
        ("raw_end", 3),
        ("parent_visibility", "complete"),
        ("crop_region", dict(left=0, top=0, right=999, bottom=206)),
        ("source_id", "congressionalglo7395unit:530:par_000529_000007"),
    ],
)
def test_even_self_consistent_hashes_cannot_forge_context_source_or_visibility(field, value):
    _, host, registry, _ = _copy_case()
    host["payload"]["image"]["scope"]["visible_context"][0][field] = value
    _reprove_scope(host, registry)
    with pytest.raises(ValueError):
        validate_host(host, registry)


def test_legacy_whole_crop_geometry_cannot_be_reintroduced_with_new_manifest_hashes():
    _, host, registry, _ = _copy_case()
    host["payload"]["image"]["bindings"][0]["crop_region"] = dict(
        left=0, top=0, right=999, bottom=206
    )
    _reprove_scope(host, registry)
    with pytest.raises(ValueError, match="exact source paragraph geometry"):
        validate_host(host, registry)


def test_context_line_that_extends_outside_crop_is_not_silently_clipped():
    legacy, _, registry, _ = _copy_case()
    with pytest.raises(ValueError, match="not fully visible"):
        prepare_source_scope(
            legacy, registry, BUNDLE.read_bytes(), [(CONTEXT[0], "line_000529_000020")]
        )


def test_duplicate_context_and_target_disguised_as_context_fail_closed():
    legacy, _, registry, _ = _copy_case()
    with pytest.raises(ValueError, match="duplicate visible"):
        prepare_source_scope(legacy, registry, BUNDLE.read_bytes(), [CONTEXT, CONTEXT])
    with pytest.raises(ValueError, match="masquerade"):
        prepare_source_scope(
            legacy,
            registry,
            BUNDLE.read_bytes(),
            [("congressionalglo7395unit:529:par_000529_000006", "line_000529_000017")],
        )


def test_missing_target_only_prompt_and_detached_scope_record_are_rejected():
    _, host, registry, _ = _copy_case()
    host["payload"]["image"]["scope"]["visible_context"][0]["raw_end"] = 2
    _bind(host)
    with pytest.raises(ValueError, match=r"boundary scope|scope differs"):
        validate_host(host, registry)
    _, host, registry, _ = _copy_case()
    prompt = (
        registry.files[host["payload"]["prompt_sha256"]].decode().removesuffix(SCOPE_INSTRUCTION)
    )
    digest = sha256_bytes(prompt.encode())
    registry.files[digest] = prompt.encode()
    host["payload"]["prompt_sha256"] = digest
    _bind(host)
    with pytest.raises(ValueError, match="target-only"):
        validate_host(host, registry)


def _synthetic_records(repeated=True):
    raw = b"""<html><div class="ocr_page" id="page_0" title="ppageno 0">
    <p class="ocr_par" id="c" title="bbox 5 5 90 30">
    <span class="ocr_line" id="l1" title="bbox 5 5 90 15">
    <span class="ocrx_word">Repeated line.</span></span>
    <span class="ocr_line" id="l2" title="bbox 5 20 90 30">
    <span class="ocrx_word">Repeated line.</span></span>
    </p></div></html>"""
    if not repeated:
        raw = raw.replace(b"Repeated line.", b"Unique context.", 1)
    return _paragraphs(raw, ("c",), "page_0", 0)


def test_ambiguous_visible_text_mapping_is_withheld_not_guessed():
    image = dict(source_item_identifier="fixture", source_scan_leaf=0)
    frame = dict(left=0, top=0, right=100, bottom=100)
    with pytest.raises(ValueError, match="ambiguous source text mapping"):
        _visible_line("fixture:0:c", "l1", image, _synthetic_records(), frame)


def test_context_budget_includes_new_visible_spans():
    with pytest.raises(ValueError, match="aggregate context limit"):
        _verify_context_budget({"paragraphs": []}, [{"text": "x" * 1200}, {"text": "y" * 1200}])


def test_scope_context_does_not_invalidate_an_existing_baseline_occurrence():
    from congressional_globe.productive_ocr_scope import reject_context_copy

    target = {"raw": {"text": NEIGHBOUR}, "static": {"text": NEIGHBOUR}}
    scope = {"visible_context": [{"text": NEIGHBOUR}]}
    reject_context_copy(NEIGHBOUR, target, scope)
    with pytest.raises(ValueError, match="visible neighbouring"):
        reject_context_copy(NEIGHBOUR + " " + NEIGHBOUR, target, scope)


def test_overlapping_target_and_context_geometry_is_ambiguous():
    image = dict(source_item_identifier="fixture", source_scan_leaf=0)
    frame = dict(left=0, top=0, right=100, bottom=100)
    records = _synthetic_records(repeated=False)
    span = _visible_line("fixture:0:c", "l1", image, records, frame)
    with pytest.raises(ValueError, match="boundary is ambiguous"):
        _verify_one_context(span, image, records, frame, {"fixture:0:target"}, [frame])


def test_hocr_paragraph_cannot_be_relabelled_as_another_page():
    raw = (
        b'<html><div class="ocr_page" id="page_0" title="ppageno 0">'
        b'<p class="ocr_par" id="p">x</p></div></html>'
    )
    with pytest.raises(ValueError, match="different hOCR page"):
        _paragraphs(raw, ("p",), "page_wrong", 0)


def test_duplicate_source_paragraph_ids_are_not_resolved_by_first_match():
    raw = b"""<html><div class="ocr_page" id="page_0" title="ppageno 0">
    <p class="ocr_par" id="p">first</p><p class="ocr_par" id="p">second</p>
    </div></html>"""
    with pytest.raises(ValueError, match="duplicate source paragraph"):
        _paragraphs(raw, ("p",), "page_0", 0)


def test_context_budget_counts_both_transmitted_text_layers():
    payload = {
        "paragraphs": [
            {"role": "context", "raw": {"text": "x" * 1000}, "static": {"text": "y" * 1000}}
        ]
    }
    with pytest.raises(ValueError, match="aggregate context limit"):
        _verify_context_budget(payload, [{"text": "visible"}])
