"""Exact frozen cases and adversarial date/source/boundary contracts."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from congressional_globe.role_provider import specialize_schema
from congressional_globe.role_v2 import role_result_schema
from congressional_globe.scoped_dates import (
    DatePacket,
    DateValue,
    date_result_schema,
    source_mapped_dates,
    text_hash,
    validate_date_result,
)

ARTIFACT = Path("artifacts/scoped-date-contract-20261026-01")


@pytest.fixture
def cases():
    return json.loads((ARTIFACT / "fixtures.json").read_text())["cases"]


def test_frozen_cases_validate_with_schema_and_host(cases):
    schema = date_result_schema()
    Draft202012Validator.check_schema(schema)
    assert json.loads((ARTIFACT / "schema.json").read_text()) == schema
    for case in cases:
        Draft202012Validator(schema).validate(case["result"])
        assert validate_date_result(case["result"], case["packet"])
        assert source_mapped_dates(case["result"], case["packet"]) == case["mapped"]


def test_frozen_fixture_hashes_match_exact_preparation(cases):
    report = json.loads((ARTIFACT / "fixtures.json").read_text())
    path = Path(report["preparation_path"])
    assert text_hash(path.read_text()) == report["preparation_sha256"]
    prep = json.loads(path.read_text())
    negative = json.loads(prep["cases"][0]["provider_input_json_exact"])
    spans = {s["id"]: s["text"] for s in negative["spans"]}
    assert all(p["raw_text"] == spans[p["alias"]] for p in cases[0]["packet"]["paragraphs"])
    expected = prep["cases"][1]["paragraphs_in_reading_order"]
    assert [p["raw_text"] for p in cases[1]["packet"]["paragraphs"]] == [
        p["raw_text"] for p in expected
    ]


def test_may_as_verb_cannot_supply_a_date(cases):
    packet = cases[0]["packet"]
    result = cases[0]["result"]
    row = result["dates"][1]
    positive = deepcopy(cases[1]["result"]["dates"][1])
    positive["target_ids"] = ["P2"]
    paragraph = packet["paragraphs"][1]
    start = paragraph["raw_text"].index("may")
    positive["evidence"] = [
        dict(
            paragraph_id="P2",
            raw_sha256=paragraph["raw_sha256"],
            start=start,
            end=start + 3,
            quote="may",
        )
    ]
    result["dates"][1] = positive
    with pytest.raises(ValueError, match="not explicitly supported"):
        validate_date_result(result, packet)
    assert row["value"] is None


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("raw_sha256", "0" * 64, "hash mismatch"),
        ("quote", "December 4, 1866", "quote/offset mismatch"),
        ("start", 0, "quote/offset mismatch"),
        ("end", 999999, "quote/offset mismatch"),
        ("paragraph_id", "P99", "unknown evidence"),
    ],
)
def test_evidence_tampering_rejected(cases, field, value, message):
    case = cases[1]
    case["result"]["dates"][1]["evidence"][0][field] = value
    with pytest.raises(ValueError, match=message):
        validate_date_result(case["result"], case["packet"])


def test_house_date_cannot_cross_back_into_senate(cases):
    case = cases[1]
    row = case["result"]["dates"][1]
    row["target_ids"] = ["P1", "P2", "P3", "P4", "P5", "P6"]
    with pytest.raises(ValueError, match="boundary"):
        validate_date_result(case["result"], case["packet"])


def test_same_region_still_cannot_date_earlier_passage(cases):
    case = cases[1]
    for p in case["packet"]["paragraphs"]:
        p["region_id"] = "single-region"
    row = case["result"]["dates"][1]
    row["target_ids"] = ["P1", "P2", "P3", "P4", "P5", "P6"]
    with pytest.raises(ValueError, match="backward"):
        validate_date_result(case["result"], case["packet"])


def test_continuation_requires_scoped_method_and_source(cases):
    case = cases[1]
    row = case["result"]["dates"].pop()
    continued = deepcopy(row)
    row["target_ids"] = ["P3"]
    continued.update(
        target_ids=["P4", "P5", "P6"], date_kind="implicit", method="scoped_continuation"
    )
    case["result"]["dates"].extend([row, continued])
    assert validate_date_result(case["result"], case["packet"])
    continued["evidence"] = []
    with pytest.raises(ValueError, match="value and evidence"):
        validate_date_result(case["result"], case["packet"])


@pytest.mark.parametrize(
    "targets", [["P3", "P5", "P6"], ["P4", "P3", "P5", "P6"], ["P3", "P3"], ["P99"]]
)
def test_wrong_target_scope_rejected(cases, targets):
    case = cases[1]
    case["result"]["dates"][1]["target_ids"] = targets
    with pytest.raises(ValueError):
        validate_date_result(case["result"], case["packet"])


@pytest.mark.parametrize(
    "change", ["omit", "overlap", "date_unknown", "human_status", "catalog_method"]
)
def test_omission_overlap_and_unearned_certainty_rejected(cases, change):
    case = cases[1]
    rows = case["result"]["dates"]
    if change == "omit":
        rows.pop(0)
    elif change == "overlap":
        rows.append(deepcopy(rows[1]))
    elif change == "date_unknown":
        rows[0]["value"] = deepcopy(rows[1]["value"])
    elif change == "human_status":
        rows[1]["status"] = "human_reviewed"
    else:
        rows[1]["method"] = "catalog_context"
    with pytest.raises(ValueError):
        validate_date_result(case["result"], case["packet"])


@pytest.mark.parametrize(
    "value,precision",
    [("1865-02-30", "day"), ("1865-13", "month"), ("0000", "year"), ("1865", "day")],
)
def test_impossible_dates_and_overstated_precision_rejected(value, precision):
    with pytest.raises(ValueError):
        DateValue(start=value, end=value, precision=precision, extent="point")


def _synthetic(text, value):
    paragraph = dict(
        alias="P1",
        source_paragraph_id="source-1",
        item_identifier="synthetic",
        scan_leaf=1,
        raw_text=text,
        raw_sha256=text_hash(text),
        region_id="r1",
    )
    packet = dict(
        window_id="synthetic",
        paragraphs=[paragraph],
        scope_basis="Synthetic contract case",
        scope_evidence_sha256="0" * 64,
    )
    row = dict(
        target_ids=["P1"],
        value=value,
        date_kind="explicit",
        context_kind="mentioned",
        status="proposed",
        method="explicit_text",
        evidence=[
            dict(paragraph_id="P1", raw_sha256=text_hash(text), start=0, end=len(text), quote=text)
        ],
        alternatives=[],
        unknowns=[],
        basis="Synthetic supported date mention",
    )
    return packet, {"dates": [row]}


@pytest.mark.parametrize(
    "text,start,end,precision,extent",
    [
        ("December 4, 1865 to December 6, 1865", "1865-12-04", "1865-12-06", "day", "range"),
        ("december 1865", "1865-12", "1865-12", "month", "point"),
        ("1865", "1865", "1865", "year", "point"),
    ],
)
def test_supported_points_ranges_and_partial_precision(text, start, end, precision, extent):
    packet, result = _synthetic(
        text, dict(start=start, end=end, precision=precision, extent=extent)
    )
    assert validate_date_result(result, packet)


def test_conflicting_alternative_remains_unresolved_and_source_bound():
    value = dict(start="1865", end="1865", precision="year", extent="point")
    packet, result = _synthetic("1865 or 1866", value)
    row = result["dates"][0]
    alt = deepcopy(value)
    alt.update(start="1866", end="1866")
    row.update(
        status="mixed",
        alternatives=[
            dict(value=alt, evidence=deepcopy(row["evidence"]), basis="Conflicting printed years")
        ],
    )
    assert validate_date_result(result, packet)
    row["alternatives"][0]["value"].update(start="1867", end="1867")
    with pytest.raises(ValueError, match="not explicitly supported"):
        validate_date_result(result, packet)


def test_packet_rejects_changed_raw_text_and_repeated_region(cases):
    packet = cases[1]["packet"]
    packet["paragraphs"][0]["raw_text"] += "changed"
    with pytest.raises(ValueError, match="hash mismatch"):
        DatePacket.model_validate(packet)
    packet["paragraphs"][0]["raw_sha256"] = text_hash(packet["paragraphs"][0]["raw_text"])
    packet["paragraphs"][-1]["region_id"] = "senate-ending"
    with pytest.raises(ValueError, match="contiguous"):
        DatePacket.model_validate(packet)


def test_generic_schema_does_not_claim_source_semantic_validation(cases):
    result = cases[1]["result"]
    result["dates"][1]["evidence"][0]["quote"] = "may"
    assert Draft202012Validator(date_result_schema()).is_valid(result)
    with pytest.raises(ValueError):
        validate_date_result(result, cases[1]["packet"])


def test_date_transport_specialization_binds_aliases_without_mutation(cases):
    original = date_result_schema()
    schema = specialize_schema(original, cases[1]["packet"])
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(cases[1]["result"])
    aliases = [p["alias"] for p in cases[1]["packet"]["paragraphs"]]
    assert schema["$defs"]["DateEvidence"]["properties"]["paragraph_id"]["enum"] == aliases
    assert original == date_result_schema()
    invalid = deepcopy(cases[1]["result"])
    invalid["dates"][1]["target_ids"] = ["P99"]
    assert not Draft202012Validator(schema).is_valid(invalid)


def test_role_v2_transport_specialization_no_longer_raises():
    original = role_result_schema()
    packet = {
        "spans": [{"id": "P1", "kind": "paragraph"}],
        "controlled_role_ids": ["floor_speaker"],
        "statuses": ["unknown"],
    }
    schema = specialize_schema(original, packet)
    assert schema["properties"]["speaker_roles"]["items"]["oneOf"]
    assert original == role_result_schema()


@pytest.mark.parametrize("provider", ["ollama", "openai"])
def test_date_request_through_existing_adapter_with_fake_client(cases, monkeypatch, provider):
    from contextlib import nullcontext
    from types import SimpleNamespace as NS

    from congressional_globe import role_provider

    captured = {}
    case = cases[1]
    output = json.dumps(case["result"])
    response = NS(
        id="synthetic-response",
        status="completed",
        output_text=output,
        output=[],
        usage=None,
        incomplete_details=None,
        choices=[NS(message=NS(content=output, refusal=None), finish_reason="stop")],
    )
    response.model_dump = lambda mode: {"id": "synthetic-response", "output_text": output}

    def create(**kwargs):
        captured.update(kwargs)
        return response

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["max_retries"] == 0
            self.responses = NS(create=create)
            self.chat = NS(completions=NS(create=create))

    monkeypatch.setattr(role_provider, "OpenAI", FakeClient)
    monkeypatch.setattr(role_provider, "_ollama_request_lock", nullcontext)
    adapter = role_provider.RoleProvider(provider, "synthetic-model", base_url="http://localhost:1")
    result = adapter.call(case["packet"], "Date contract test", date_result_schema())
    assert validate_date_result(json.loads(result["output_text"]), case["packet"])
    assert result["usage"]["input_tokens"] is None
    if provider == "ollama":
        assert captured["response_format"] == {"type": "json_object"}
        assert '"$defs"' in captured["messages"][0]["content"]
        assert "candidate_id is a C alias" not in captured["messages"][0]["content"]
    else:
        schema = captured["text"]["format"]["schema"]
        Draft202012Validator(schema).validate(case["result"])
        assert captured["text"]["format"]["strict"] is True
