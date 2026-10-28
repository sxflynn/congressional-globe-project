"""Offline request schema/projection, fit gate, and host export checks."""

import base64
import hashlib
import io
import json
import runpy
from pathlib import Path

import pytest
from PIL import Image

from congressional_globe.productive_ocr_export import export_reply, export_transport_failure
from congressional_globe.productive_ocr_fit import (
    FitEvidence,
    ImageSchedule,
    NativeObservation,
    TileObservation,
    TokenIdTrace,
    inspect_fit_evidence,
    prepare_owned_job,
)
from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
from congressional_globe.productive_ocr_projection import (
    compile_request_projection,
    derive_reply_schema,
)
from congressional_globe.productive_ocr_reply import Reply


def _host_and_projection():
    helpers = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_host.py")))
    host, registry = helpers["_packet"]({})
    payload = host["payload"]
    artifact = derive_reply_schema(host)
    schema_bytes = artifact.schema_text.encode("utf-8")
    payload["response_schema_sha256"] = artifact.schema_sha256
    registry.files[artifact.schema_sha256] = schema_bytes
    prompt = "Frozen synthetic prompt for schema tests."
    payload["prompt_sha256"] = hashlib.sha256(prompt.encode()).hexdigest()
    registry.files[payload["prompt_sha256"]] = prompt.encode()
    helpers["_rehash"](host)
    projection, schema = compile_request_projection(host, registry, prompt, "fixture-model")
    return host, registry, prompt, projection, schema


def _valid_reply(host: dict) -> str:
    raw = host["payload"]["paragraphs"][0]["raw"]["text"]
    checks = [
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
    reply = {
        "contract": "ocr-productive-repair-reply-v2",
        "unit_id": host["payload"]["unit_id"],
        "role": host["payload"]["role"],
        "status": "no_finding",
        "inspections": [
            {
                "paragraph_alias": "P1",
                "image_alias": "I1",
                "completeness": "complete",
                "image_suitability": "clear",
                "reason": None,
            }
        ],
        "findings": [],
        "patches": [],
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
        ],
        "self_check": [
            {
                "paragraph_alias": "P1",
                "coverage": "complete",
                "checked_content": checks,
                "remaining_concerns": [],
            }
        ],
    }
    return json.dumps(reply)


def _offline_fit_bundle(
    projection, registry, capture_method="verified_offline_native_preprocessing"
):
    resources = [b"synthetic tokenizer", b"synthetic preprocessor", b"synthetic renderer"]
    hashes = [sha256_bytes(item) for item in resources]
    registry.files.update(dict(zip(hashes, resources, strict=True)))
    rendered = b"synthetic native rendering bound to body: " + projection.body_utf8.encode()
    rendered_hash = sha256_bytes(rendered)
    registry.files[rendered_hash] = rendered
    token_trace = TokenIdTrace(
        contract="productive-ocr-native-token-id-trace-v1",
        body_sha256=projection.body_sha256,
        rendered_text_sha256=rendered_hash,
        tokenizer_sha256=hashes[0],
        preprocessor_sha256=hashes[1],
        token_ids=(101, 102),
    )
    trace_bytes = canonical_json(token_trace.model_dump(mode="json"))
    trace_hash = sha256_bytes(trace_bytes)
    registry.files[trace_hash] = trace_bytes
    image = Image.new("RGB", (40, 30), "white")
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    tile_bytes = stream.getvalue()
    tile_hash = sha256_bytes(tile_bytes)
    registry.files[tile_hash] = tile_bytes
    regions = json.loads(projection.image_bindings_json)
    schedule = ImageSchedule(
        image_sha256=projection.image_sha256,
        paragraph_aliases=tuple(item["paragraph_alias"] for item in regions),
        crop_regions=tuple(item["crop_region"] for item in regions),
        rendered_width=40,
        rendered_height=30,
        tiles=(
            TileObservation(
                tile_sha256=tile_hash,
                left=0,
                top=0,
                width=40,
                height=30,
                token_count=4,
            ),
        ),
        image_tokens=4,
    )
    native = NativeObservation(
        contract="productive-ocr-native-fit-observation-v1",
        capture_method=capture_method,
        request_id="synthetic-offline-preflight",
        body_sha256=projection.body_sha256,
        image_bindings_sha256=projection.image_bindings_sha256,
        model_name=projection.model_name,
        model_digest=projection.model_digest,
        tokenizer_sha256=hashes[0],
        preprocessor_sha256=hashes[1],
        renderer_sha256=hashes[2],
        rendered_text_sha256=rendered_hash,
        token_id_trace_sha256=trace_hash,
        text_tokens=2,
        image_tokens=4,
        input_tokens=6,
        output_token_limit=1500,
        observed_output_tokens=None,
        image_schedule=(schedule,),
    )
    native_bytes = canonical_json(native.model_dump(mode="json"))
    native_hash = sha256_bytes(native_bytes)
    registry.files[native_hash] = native_bytes
    fit = FitEvidence(
        contract="productive-ocr-complete-fit-v1",
        evidence_scope="complete_native_backend",
        request_projection_sha256=sha256_bytes(canonical_json(projection.model_dump(mode="json"))),
        host_packet_sha256=projection.host_packet_sha256,
        body_sha256=projection.body_sha256,
        image_bindings_sha256=projection.image_bindings_sha256,
        model_name=projection.model_name,
        model_digest=projection.model_digest,
        tokenizer_sha256=hashes[0],
        preprocessor_sha256=hashes[1],
        renderer_sha256=hashes[2],
        rendered_text_sha256=rendered_hash,
        token_id_trace_sha256=trace_hash,
        source_layers_sha256=projection.source_layers_sha256,
        image_sha256=projection.image_sha256,
        diagnostics_sha256=projection.diagnostics_sha256,
        saved_proposal_sha256=projection.saved_proposal_sha256,
        text_tokens=2,
        image_tokens=4,
        input_tokens=6,
        output_token_limit=1500,
        observed_output_tokens=None,
        native_observation_sha256=native_hash,
    )
    fit_bytes = canonical_json(fit.model_dump(mode="json"))
    fit_hash = sha256_bytes(fit_bytes)
    registry.files[fit_hash] = fit_bytes
    return fit_bytes.decode("utf-8"), trace_hash


def test_schema_is_per_unit_and_does_not_mutate_generic_contract():
    before = Reply.model_json_schema()
    host, _registry, _prompt, _projection, schema = _host_and_projection()
    shaped = json.loads(schema.schema_text)
    assert shaped["properties"]["unit_id"] == {"const": host["payload"]["unit_id"]}
    assert shaped["properties"]["role"] == {"const": host["payload"]["role"]}
    assert shaped["$defs"]["Inspection"]["properties"]["paragraph_alias"]["enum"] == ["P1"]
    assert shaped["$defs"]["Anchor"]["properties"]["paragraph_alias"]["enum"] == ["P1"]
    assert hashlib.sha256(schema.schema_text.encode()).hexdigest() == schema.schema_sha256
    assert Reply.model_json_schema() == before


def test_audit_schema_forbids_repair_readings_and_patches():
    host = {
        "payload": {
            "unit_id": "audit-1",
            "role": "audit_saved_proposal",
            "paragraphs": [{"alias": "P4", "role": "target"}],
        }
    }
    schema = json.loads(derive_reply_schema(host).schema_text)
    assert schema["properties"]["target_readings"]["maxItems"] == 0
    assert schema["properties"]["patches"]["maxItems"] == 0
    assert schema["$defs"]["Patch"]["properties"]["paragraph_alias"]["enum"] == ["P4"]


def test_request_projection_binds_schema_prompt_and_exact_image_bytes():
    host, _registry, _prompt, projection, schema = _host_and_projection()
    body = json.loads(projection.body_utf8)
    image = base64.b64decode(body["messages"][1]["images"][0], validate=True)
    assert body["format"] == json.loads(schema.schema_text)
    assert body["messages"][1]["content"]
    assert hashlib.sha256(image).hexdigest() == host["payload"]["image"]["sha256"]
    assert projection.host_packet_sha256 == host["packet_sha256"]
    assert projection.body_sha256 == hashlib.sha256(projection.body_utf8.encode()).hexdigest()


def test_t55_text_only_counter_is_not_complete_multimodal_fit():
    host, registry, _prompt, projection, _schema = _host_and_projection()
    partial = Path("artifacts/ocr-live-readiness-20261028-01/token-capacity.json").read_text()
    gate = inspect_fit_evidence(projection, partial, registry)
    assert not gate.ready
    assert gate.reason
    assert "body_sha256" in gate.reason and "native_observation_sha256" in gate.reason
    with pytest.raises(ValueError, match="incomplete multimodal fit evidence"):
        prepare_owned_job(projection, host, registry, partial)


@pytest.mark.parametrize(
    "capture_method",
    ["owned_backend_dry_run", "verified_offline_native_preprocessing"],
)
def test_offline_native_preflight_prepares_job_without_claiming_output_usage(capture_method):
    host, registry, _prompt, projection, _schema = _host_and_projection()
    fit_json, trace_hash = _offline_fit_bundle(projection, registry, capture_method)
    gate = inspect_fit_evidence(projection, fit_json, registry)
    assert gate.ready
    assert gate.evidence is not None
    assert gate.evidence.output_token_limit == 1500
    assert gate.evidence.observed_output_tokens is None
    prepared = prepare_owned_job(projection, host, registry, fit_json)
    assert prepared.job.input_tokens == 6
    assert prepared.job.token_fit_sha256
    assert json.loads(prepared.token_fit_record_json)["output_tokens"] == 1500
    assert trace_hash in registry.files


def test_offline_preflight_rejects_changed_exact_rendered_text_bytes():
    _host, registry, _prompt, projection, _schema = _host_and_projection()
    fit_json, _trace_hash = _offline_fit_bundle(projection, registry)
    fit = json.loads(fit_json)
    registry.files[fit["rendered_text_sha256"]] = b"different native rendering"
    gate = inspect_fit_evidence(projection, fit_json, registry)
    assert not gate.ready
    assert gate.reason and "rendered-text bytes" in gate.reason


def test_token_id_trace_rejects_negative_ids_and_more_than_input_ceiling():
    with pytest.raises(ValueError):
        TokenIdTrace(
            contract="productive-ocr-native-token-id-trace-v1",
            body_sha256="a" * 64,
            rendered_text_sha256="b" * 64,
            tokenizer_sha256="c" * 64,
            preprocessor_sha256="d" * 64,
            token_ids=(101, -1),
        )
    with pytest.raises(ValueError):
        TokenIdTrace(
            contract="productive-ocr-native-token-id-trace-v1",
            body_sha256="a" * 64,
            rendered_text_sha256="b" * 64,
            tokenizer_sha256="c" * 64,
            preprocessor_sha256="d" * 64,
            token_ids=(1,) * 6001,
        )


def test_export_preserves_exact_request_reply_and_unreviewed_proposal_state():
    host, _registry, _prompt, projection, schema = _host_and_projection()
    reply = _valid_reply(host)
    usage = '{"prompt_eval_count":17,"eval_count":0}'
    exported = export_reply(
        host,
        projection.body_utf8,
        reply,
        host["payload"]["model_digest"],
        schema.schema_sha256,
        usage,
        0.25,
    )
    assert exported.outcome == "valid_no_finding"
    assert exported.raw_reply_text == reply
    assert exported.raw_reply_sha256 == hashlib.sha256(reply.encode()).hexdigest()
    assert exported.provider_request_sha256 == projection.body_sha256
    assert exported.provider_usage_json == usage
    assert exported.acceptance_state == "unreviewed_ai_evidence"
    assert len(exported.derived_proposals) == 1
    assert exported.derived_proposals[0].text == "By Mr. Example."
    assert exported.derived_proposals[0].state == "unreviewed_model_proposal"


def test_invalid_reply_export_keeps_raw_reply_and_rejection():
    host, _registry, _prompt, projection, schema = _host_and_projection()
    raw_reply = '{"status":"findings","broken":true}'
    exported = export_reply(
        host,
        projection.body_utf8,
        raw_reply,
        host["payload"]["model_digest"],
        schema.schema_sha256,
        '{"usage":"unknown"}',
        None,
    )
    assert exported.outcome == "invalid"
    assert exported.provider_reply is None
    assert exported.bindings == [] and exported.derived_proposals == []
    assert exported.raw_reply_text == raw_reply
    assert exported.rejection_reason
    assert exported.provider_usage_json == '{"usage":"unknown"}'


def test_transport_failure_export_preserves_exact_non_utf8_entity_bytes():
    host, _registry, _prompt, projection, schema = _host_and_projection()
    entity = b'{"message":"bad byte: \xff"}'
    raw_http = b"HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\n\xff"
    exported = export_transport_failure(
        host,
        projection.body_utf8,
        entity,
        hashlib.sha256(raw_http).hexdigest(),
        host["payload"]["model_digest"],
        "invalid UTF-8 response entity",
        {"input_tokens": 6, "output_tokens": 0},
        0.5,
    )
    record = exported.model_dump(mode="json")
    assert record["contract"] == "source-bound-productive-ocr-transport-failure-v1"
    assert record["raw_entity_sha256"] == hashlib.sha256(entity).hexdigest()
    assert base64.b64decode(record["raw_entity_base64"]) == entity
    assert record["raw_http_sha256"] == hashlib.sha256(raw_http).hexdigest()
    assert record["provider_request_sha256"] == projection.body_sha256
    assert record["model_name"] == projection.model_name
    assert record["response_schema_sha256"] == schema.schema_sha256
    assert record["model_reply_text"] is None
    assert record["model_reply_sha256"] is None
    assert record["acceptance_state"] == "unreviewed_ai_evidence"


def test_export_rejects_unbound_request_body_but_retains_response():
    host, _registry, _prompt, projection, schema = _host_and_projection()
    raw_reply = _valid_reply(host)
    body = json.loads(projection.body_utf8)
    body["messages"][1]["content"] = "different host projection"
    altered = canonical_json(body).decode()
    exported = export_reply(
        host, altered, raw_reply, host["payload"]["model_digest"], schema.schema_sha256
    )
    assert exported.outcome == "invalid"
    assert exported.rejection_reason is not None
    assert "projection differs" in exported.rejection_reason
    assert exported.raw_reply_text == raw_reply


def test_export_emits_source_positions_and_patch_replay_mapping():
    host, _registry, _prompt, projection, schema = _host_and_projection()
    reply = json.loads(_valid_reply(host))
    reply["status"] = "findings"
    reply["findings"] = [
        {
            "finding_id": "F1",
            "anchor": {"paragraph_alias": "P1", "scope": "quote", "raw_quote": "Mr."},
            "affected_layer": "raw",
            "affected_quote": "Mr.",
            "category": "other_damage",
            "resolution": "proposed",
            "proposed_reading": "Mr",
            "image_alias": "I1",
            "basis": "visible_print",
            "explanation": "Synthetic patch export fixture.",
        }
    ]
    reply["patches"] = [
        {
            "finding_id": "F1",
            "paragraph_alias": "P1",
            "raw_quote": "Mr.",
            "replacement": "Mr",
            "image_alias": "I1",
            "reason": "Synthetic patch.",
        }
    ]
    reply["target_readings"][0].update(reading_status="proposed", proposed_text="By Mr Example.")
    raw_reply = json.dumps(reply)
    exported = export_reply(
        host,
        projection.body_utf8,
        raw_reply,
        host["payload"]["model_digest"],
        schema.schema_sha256,
        None,
        1.0,
    )
    assert exported.outcome == "valid_findings"
    assert len(exported.bindings) == 2
    assert exported.bindings[0].raw_quote == "Mr."
    assert exported.bindings[1].finding_id == "F1"
    assert exported.derived_proposals[0].text == "By Mr Example."
    assert exported.derived_proposals[0].mapping[0].kind == "unchanged"
