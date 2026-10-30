"""T99: advertise the same complete/uncertain shapes that the host already requires."""

import copy
import json
import runpy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes, validate_host
from congressional_globe.productive_ocr_projection import (
    compile_request_projection,
    derive_reply_schema,
)
from congressional_globe.productive_ocr_routing import (
    TEXT_PROMPT,
    TEXT_PROMPT_V4,
    prepare_text_host,
)
from congressional_globe.productive_ocr_text_reply import TextReply, validate_text_reply

HELPERS = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_text.py")))
ACTUAL = Path("artifacts/s5-text-measurement-20261030-01")
T97 = Path("artifacts/two-stage-integration-20261030-01")


def _actual_reply():
    return json.loads(json.loads((ACTUAL / "run/result.json").read_bytes())["output_text"])


def _new_case():
    old, registry, result, *_ = HELPERS["saved_case"]("S5")
    host, routes = prepare_text_host(
        old, registry, {"P1": result}, HELPERS["saved_resources"](result), conformance_v4=True
    )
    prompt = registry.files[host["payload"]["prompt_sha256"]].decode()
    projection, schema = compile_request_projection(
        host, registry, prompt, "qwen3.8:27b-mlx", conformance_v4=True
    )
    return old, host, registry, projection, schema, routes


def _host_accepts(reply):
    try:
        TextReply.model_validate_json(json.dumps(reply))
    except ValidationError:
        return False
    return True


@pytest.mark.parametrize(
    "coverage,text,reason,valid",
    [
        ("complete", "A complete sentence.", None, True),
        ("complete", "A complete sentence.", "No further action required.", False),
        ("complete", None, None, False),
        ("complete", "", None, False),
        ("incomplete", None, "Last word is unclear.", True),
        ("incomplete", "A guessed sentence.", "Last word is unclear.", False),
        ("incomplete", None, None, False),
        ("incomplete", None, "", False),
    ],
)
def test_schema_and_host_agree_on_complete_and_uncertain_shapes(coverage, text, reason, valid):
    _old, _host, _registry, _projection, schema, *_ = _new_case()
    reply = _actual_reply()
    reply["readings"][0].update(coverage=coverage, corrected_text=text, reason=reason)
    wire_accepts = Draft202012Validator(json.loads(schema.schema_text)).is_valid(reply)
    assert wire_accepts == _host_accepts(reply) == valid


def test_actual_failure_remains_invalid_but_new_schema_rejects_it_before_host():
    old, host, _registry, _projection, schema, *_ = _new_case()
    actual = _actual_reply()
    legacy = derive_reply_schema(old)
    Draft202012Validator(json.loads(legacy.schema_text)).validate(actual)
    assert not Draft202012Validator(json.loads(schema.schema_text)).is_valid(actual)
    with pytest.raises(ValueError, match="complete needs text/no reason"):
        validate_text_reply(json.dumps(actual), host)
    assert json.loads((ACTUAL / "run/result.json").read_bytes())["measurement_status"] == "invalid"


def test_correct_complete_and_withheld_examples_have_expected_source_bound_outcomes():
    _old, host, _registry, _projection, schema, *_ = _new_case()
    reply = _actual_reply()
    reply["readings"][0]["reason"] = None
    validator = Draft202012Validator(json.loads(schema.schema_text))
    validator.validate(reply)
    result = validate_text_reply(json.dumps(reply), host)
    assert result["proposal_status"] == "findings"
    assert result["derived_proposals"][0]["text"] == reply["readings"][0]["corrected_text"]
    reply["readings"][0].update(coverage="incomplete", corrected_text=None, reason="Image unclear.")
    validator.validate(reply)
    withheld = validate_text_reply(json.dumps(reply), host)
    assert withheld["proposal_status"] == "unresolved"
    assert withheld["derived_proposals"] == []


def test_new_schema_and_prompt_are_explicitly_selected_without_source_change():
    old, host, registry, projection, schema, routes = _new_case()
    assert schema.contract == "productive-ocr-reply-schema-v4"
    assert host["payload"]["image"] == old["payload"]["image"]
    assert host["payload"]["paragraphs"] == old["payload"]["paragraphs"]
    assert len(routes) == 1
    assert TEXT_PROMPT_V4.encode() == registry.files[host["payload"]["prompt_sha256"]]
    assert "reason to JSON null (not a string)" in TEXT_PROMPT_V4
    assert "corrected_text to JSON null" in TEXT_PROMPT_V4
    with pytest.raises(ValueError, match="derived per-request"):
        compile_request_projection(host, registry, TEXT_PROMPT_V4, "qwen3.8:27b-mlx")
    assert json.loads(projection.body_utf8)["format"] == json.loads(schema.schema_text)


@pytest.mark.parametrize("strict_prompt", [True, False])
def test_prompt_and_schema_conformance_cannot_be_mixed(strict_prompt):
    old, strict, registry, *_ = _new_case()
    mixed = copy.deepcopy(strict if strict_prompt else old)
    template = old if strict_prompt else strict
    mixed["payload"]["response_schema_sha256"] = template["payload"]["response_schema_sha256"]
    mixed["packet_sha256"] = sha256_bytes(canonical_json(mixed["payload"]))
    with pytest.raises(ValueError, match="prompt/schema conformance"):
        validate_host(mixed, registry)


def test_unrelated_or_mixed_response_modes_are_rejected():
    old, *_ = HELPERS["saved_case"]("S5")
    with pytest.raises(ValueError, match="v2 conformance"):
        derive_reply_schema(old, conformance_v2=True, conformance_v4=True)
    legacy = copy.deepcopy(old)
    legacy["payload"]["contract"] = "ocr-productive-repair-host-input-v2"
    with pytest.raises(ValueError, match="requires the lean text"):
        derive_reply_schema(legacy, conformance_v4=True)


def test_original_t97_prompt_schema_and_wire_body_reproduce_byte_for_byte():
    # Reconstruct using the recorded host/code identity, not today's implementation hash.
    from congressional_globe.productive_ocr_measurement_inputs import ASSEMBLY, _registry

    host = json.loads((T97 / "S5-host.json").read_bytes())
    registry = _registry(
        ASSEMBLY, host, json.loads((ASSEMBLY / "registry-index.json").read_bytes())
    )
    closure = json.loads((T97 / "registry-closure.json").read_bytes())
    for digest, record in closure["new_files"].items():
        registry.files[digest] = (T97 / record["path"]).read_bytes()
    prompt = (T97 / "S5-prompt.txt").read_text()
    assert prompt == TEXT_PROMPT
    projection, schema = compile_request_projection(host, registry, prompt, "offline-test-only")
    assert projection.body_utf8.encode() == (T97 / "S5-request.json").read_bytes()
    assert schema.schema_text.encode() == (T97 / "S5-schema.json").read_bytes()
