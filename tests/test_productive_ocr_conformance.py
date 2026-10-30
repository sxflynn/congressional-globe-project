"""Observed failure stays invalid; revised guidance supports honest complete/withheld replies."""

import copy
import json
import runpy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from congressional_globe.productive_ocr_measurement_inputs import load_s5_inputs
from congressional_globe.productive_ocr_projection import derive_reply_schema
from congressional_globe.productive_ocr_reply import validate_reply

ROOT = Path("artifacts/s5-conformance-20261029-01")
HELPERS = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_reply.py")))


def _complete():
    raw = "A re- port is on- file."
    reply = HELPERS["_reply"](raw, status="findings")
    for index, (quote, replacement) in enumerate((("re- port", "report"), ("on- file", "on file"))):
        fid = f"F{index}"
        reply["findings"].append(
            {
                "finding_id": fid,
                "anchor": {"paragraph_alias": "P1", "scope": "quote", "raw_quote": quote},
                "affected_layer": "raw",
                "affected_quote": quote,
                "category": "other_damage",
                "resolution": "proposed",
                "proposed_reading": replacement,
                "image_alias": "I1",
                "basis": "visible_print",
                "explanation": "Synthetic visible-print control.",
            }
        )
        reply["patches"].append(
            {
                "finding_id": fid,
                "paragraph_alias": "P1",
                "raw_quote": quote,
                "replacement": replacement,
                "image_alias": "I1",
                "reason": "Synthetic control.",
            }
        )
    reply["target_readings"][0].update(
        reading_status="proposed", proposed_text="A report is on file."
    )
    return HELPERS["_host"](raw, static="A report is on- file."), reply


def _schema(host):
    return json.loads(derive_reply_schema(host, conformance_v2=True).schema_text)


def test_actual_s5_failure_is_unchanged_and_rejected_by_host_and_new_schema():
    host, old_projection, _registry = load_s5_inputs(Path("."))
    result = json.loads(Path("artifacts/s5-measurement-20261029-01/run/result.json").read_text())
    with pytest.raises(ValueError, match="whole-paragraph anchor has no quote"):
        validate_reply(result["output_text"], host)
    assert not Draft202012Validator(_schema(host)).is_valid(json.loads(result["output_text"]))
    assert old_projection.body_sha256 == result["owned_local"]["request_sha256"]
    assert derive_reply_schema(host).contract == "productive-ocr-reply-schema-v1"


def test_complete_control_requires_both_raw_repairs_even_when_static_already_joined():
    host, reply = _complete()
    Draft202012Validator(_schema(host)).validate(reply)
    mapped = validate_reply(json.dumps(reply), host)
    assert mapped["proposed_readings"]["P1"]["text"] == "A report is on file."
    reply["patches"].pop(0)
    reply["findings"].pop(0)
    with pytest.raises(ValueError, match="does not exactly replay"):
        validate_reply(json.dumps(reply), host)


@pytest.mark.parametrize("status", ["incomplete", "unresolved"])
def test_honest_withheld_control_is_valid(status):
    host, reply = _complete()
    reply.update(status=status, reason="Synthetic unclear image.", findings=[], patches=[])
    reply["target_readings"][0].update(
        reading_status="withheld", proposed_text=None, reason="Unclear print."
    )
    reply["inspections"][0].update(completeness="partial", image_suitability="unclear")
    reply["self_check"][0].update(
        coverage="partial", checked_content=["all_words"], remaining_concerns=["Unclear print."]
    )
    reply["findings"] = [
        {
            "finding_id": "U1",
            "anchor": {"paragraph_alias": "P1", "scope": "whole_paragraph", "raw_quote": None},
            "affected_layer": "raw",
            "affected_quote": None,
            "category": "source_uncertainty",
            "resolution": "unresolved",
            "proposed_reading": None,
            "image_alias": "I1",
            "basis": "image_unclear",
            "explanation": "Synthetic unclear whole paragraph.",
        }
    ]
    Draft202012Validator(_schema(host)).validate(reply)
    assert validate_reply(json.dumps(reply), host)["proposed_readings"] == {"P1": {}}


@pytest.mark.parametrize("mutation", ["anchor", "basis", "status", "checks", "concerns"])
def test_observed_semantic_failure_families_remain_rejected(mutation):
    host, reply = _complete()
    if mutation == "anchor":
        reply["findings"][0]["anchor"]["scope"] = "whole_paragraph"
    if mutation == "basis":
        reply["findings"][0]["basis"] = "image_unclear"
    if mutation == "status":
        reply["status"] = "no_finding"
    if mutation == "checks":
        reply["self_check"][0]["checked_content"].remove("all_words")
    if mutation == "concerns":
        reply["self_check"][0]["remaining_concerns"] = ["Unresolved print."]
    with pytest.raises(ValueError):
        validate_reply(json.dumps(reply), host)


def test_whole_paragraph_and_no_finding_controls():
    host, reply = _complete()
    finding = copy.deepcopy(reply["findings"][0])
    raw = host["payload"]["paragraphs"][0]["raw"]["text"]
    finding.update(affected_quote=raw, proposed_reading="A report is on file.")
    finding["anchor"].update(scope="whole_paragraph", raw_quote=None)
    reply["findings"] = [finding]
    for patch in reply["patches"]:
        patch["finding_id"] = finding["finding_id"]
    Draft202012Validator(_schema(host)).validate(reply)
    validate_reply(json.dumps(reply), host)
    unchanged = HELPERS["_reply"](raw)
    Draft202012Validator(_schema(host)).validate(unchanged)
    validate_reply(json.dumps(unchanged), host)


def test_candidate_projection_requires_explicit_v2_and_rebound_prompt_schema():
    from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
    from congressional_globe.productive_ocr_projection import compile_request_projection

    host, old, registry = load_s5_inputs(Path("."))
    schema = derive_reply_schema(host, conformance_v2=True)
    prompt = (ROOT / "prompt.txt").read_text()
    with pytest.raises(ValueError, match="derived per-request reply schema"):
        compile_request_projection(host, registry, prompt, old.model_name, conformance_v2=True)
    resources = {
        "response_schema_sha256": schema.schema_text.encode(),
        "prompt_sha256": prompt.encode(),
        # Reproduce the immutable historical candidate with its recorded implementation.
        "code_sha256": (ROOT / "code-identity.json").read_bytes(),
    }
    for key, data in resources.items():
        digest = sha256_bytes(data)
        registry.files[digest] = data
        host["payload"][key] = digest
    host["packet_sha256"] = sha256_bytes(canonical_json(host["payload"]))
    with pytest.raises(ValueError, match="derived per-request reply schema"):
        compile_request_projection(host, registry, prompt, old.model_name)
    candidate, _ = compile_request_projection(
        host, registry, prompt, old.model_name, conformance_v2=True
    )
    assert candidate.body_sha256 != old.body_sha256
    assert candidate.source_layers_sha256 == old.source_layers_sha256
    assert candidate.image_sha256 == old.image_sha256
    assert candidate.diagnostics_sha256 == old.diagnostics_sha256
    assert json.loads((ROOT / "host.json").read_text()) == host
    assert json.loads((ROOT / "projection.json").read_text()) == candidate.model_dump(mode="json")
    assert (ROOT / "request.json").read_bytes() == candidate.body_utf8.encode()


@pytest.mark.parametrize("field,value", [("affected_quote", None), ("basis", "image_unclear")])
def test_schema_rejects_locally_inconsistent_proposed_findings(field, value):
    host, reply = _complete()
    reply["findings"][0][field] = value
    assert not Draft202012Validator(_schema(host)).is_valid(reply)
