"""Exact quote binding preserves every existing date/source/scope check."""

import hashlib
import json
import runpy
import signal
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from congressional_globe.quote_dates import (
    QuoteDateResult,
    bind_quote_date_result,
    quote_date_schema,
    source_mapped_quote_dates,
)
from congressional_globe.role_provider import specialize_schema
from congressional_globe.role_runner import execute
from congressional_globe.scoped_dates import text_hash, validate_date_result

ARTIFACTS = Path(__file__).parents[1] / "artifacts"
LIVE = ARTIFACTS / "metadata-live-20261026-01"
HELPERS = runpy.run_path(str(Path(__file__).with_name("test_metadata_runner.py")))
RECOVERY = runpy.run_path(str(Path(__file__).with_name("test_metadata_recovery.py")))


def _quotes(result):
    """Make explicitly new offline fixtures; never rewrite a stored model reply."""
    copied = deepcopy(result)
    for item in copied["dates"]:
        _drop_offsets(item["evidence"])
        for alternative in item["alternatives"]:
            _drop_offsets(alternative["evidence"])
    return copied


def _drop_offsets(evidence):
    for item in evidence:
        item.pop("start", None)
        item.pop("end", None)


def _one(text, quote="January 2, 1900"):
    packet = {
        "window_id": "synthetic-quote-test",
        "paragraphs": [
            {
                "alias": "P1",
                "source_paragraph_id": "synthetic::p1",
                "item_identifier": "synthetic",
                "scan_leaf": 0,
                "raw_text": text,
                "raw_sha256": text_hash(text),
                "region_id": "r1",
            }
        ],
        "scope_basis": "Synthetic quote-binding test, no historical judgment",
        "scope_evidence_sha256": "0" * 64,
    }
    result = {
        "dates": [
            {
                "target_ids": ["P1"],
                "value": {
                    "start": "1900-01-02",
                    "end": "1900-01-02",
                    "precision": "day",
                    "extent": "point",
                },
                "date_kind": "explicit",
                "context_kind": "mentioned",
                "status": "proposed",
                "method": "explicit_text",
                "evidence": [{"paragraph_id": "P1", "raw_sha256": text_hash(text), "quote": quote}],
                "alternatives": [],
                "unknowns": [],
                "basis": "Synthetic explicitly mentioned date",
            }
        ]
    }
    return packet, result


def test_existing_frozen_cases_derive_identical_v1_results_without_mutating():
    cases = HELPERS["_date_cases"]()
    for case in cases:
        original = deepcopy(case)
        result = _quotes(case["result"])
        assert bind_quote_date_result(result, case["packet"]) == case["result"]
        assert case == original
        mapped = source_mapped_quote_dates(result, case["packet"])
        assert mapped["dates"] == case["mapped"]["dates"]
        assert mapped["sources"] == case["mapped"]["sources"]
        assert mapped["model_proposals"] == result
        assert mapped["coordinate_binding"] == "host_unique_exact_quote_in_declared_raw_paragraph"
        assert mapped["historical_status"] == "proposal_only_not_human_reviewed"


def test_unicode_offsets_are_original_codepoints_not_bytes_or_normalized_text():
    packet, result = _one("🙂 e\u0301 — January 2, 1900.")
    evidence = bind_quote_date_result(result, packet)["dates"][0]["evidence"][0]
    assert evidence["start"] == 7
    assert evidence["end"] == 22
    text = packet["paragraphs"][0]["raw_text"]
    assert text[7:22] == evidence["quote"]
    assert len(text[:7].encode()) > 7


@pytest.mark.parametrize(
    "text,quote,error",
    [
        ("January 2, 1900", "January 3, 1900", "not found"),
        ("January 2, 1900", "January 2,1900", "not found"),
        ("JANUARY 2, 1900", "January 2, 1900", "not found"),
        ("January 2, 1900 and January 2, 1900", "January 2, 1900", "ambiguous"),
        ("aaaa", "aaa", "ambiguous"),
    ],
)
def test_missing_repeated_and_overlapping_quotes_are_not_guessed(text, quote, error):
    packet, result = _one(text, quote)
    with pytest.raises(ValueError, match=error):
        bind_quote_date_result(result, packet)


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("paragraph_id", "P99", "unknown quote evidence"),
        ("raw_sha256", "0" * 64, "raw hash mismatch"),
        ("quote", "", "at least 1 character"),
        ("start", 0, "Extra inputs"),
        ("end", 15, "Extra inputs"),
    ],
)
def test_bad_reference_hash_empty_quote_and_model_positions_rejected(field, value, error):
    packet, result = _one("January 2, 1900")
    result["dates"][0]["evidence"][0][field] = value
    with pytest.raises(ValueError, match=error):
        bind_quote_date_result(result, packet)


def test_changed_source_cannot_be_bound_using_an_old_hash():
    packet, result = _one("January 2, 1900")
    packet["paragraphs"][0]["raw_text"] += " changed"
    with pytest.raises(ValueError, match="paragraph raw hash mismatch"):
        bind_quote_date_result(result, packet)


def test_date_value_still_needs_support_in_exact_quote():
    packet, result = _one("January 2, 1900")
    result["dates"][0]["value"].update(start="1901-01-02", end="1901-01-02")
    with pytest.raises(ValueError, match="not explicitly supported"):
        bind_quote_date_result(result, packet)


def test_a_quote_in_another_paragraph_is_not_silently_used():
    packet, result = _one("No date is supplied here.")
    second = deepcopy(packet["paragraphs"][0])
    second.update(
        alias="P2",
        source_paragraph_id="synthetic::p2",
        raw_text="January 2, 1900",
        raw_sha256=text_hash("January 2, 1900"),
    )
    packet["paragraphs"].append(second)
    with pytest.raises(ValueError, match="not found"):
        bind_quote_date_result(result, packet)


def test_host_binding_does_not_cross_chamber_or_backward_boundary():
    case = HELPERS["_date_cases"]()[1]
    result = _quotes(case["result"])
    result["dates"][1]["target_ids"] = [p["alias"] for p in case["packet"]["paragraphs"]]
    with pytest.raises(ValueError, match="boundary"):
        bind_quote_date_result(result, case["packet"])
    result["dates"][1]["target_ids"] = ["P1"]
    for paragraph in case["packet"]["paragraphs"]:
        paragraph["region_id"] = "one-region"
    with pytest.raises(ValueError, match="backward"):
        bind_quote_date_result(result, case["packet"])


@pytest.mark.parametrize(
    "mutation,error", [("missing", "each input paragraph"), ("overlap", "overlapping assignments")]
)
def test_target_coverage_is_still_required(mutation, error):
    case = HELPERS["_date_cases"]()[1]
    result = _quotes(case["result"])
    if mutation == "missing":
        result["dates"][1]["target_ids"].remove("P6")
    else:
        result["dates"].append(deepcopy(result["dates"][1]))
    with pytest.raises(ValueError, match=error):
        bind_quote_date_result(result, case["packet"])


def test_alternatives_are_bound_and_keep_conflicting_status():
    packet, result = _one("January 2, 1900 or January 3, 1900")
    item = result["dates"][0]
    value = {**item["value"], "start": "1900-01-03", "end": "1900-01-03"}
    alternative = {
        "value": value,
        "evidence": [{**item["evidence"][0], "quote": "January 3, 1900"}],
        "basis": "Conflicting synthetic date",
    }
    item.update(status="mixed", alternatives=[alternative])
    bound = bind_quote_date_result(result, packet)
    assert bound["dates"][0]["status"] == "mixed"
    assert bound["dates"][0]["alternatives"][0]["evidence"][0]["start"] == 19
    item["alternatives"][0]["evidence"][0]["start"] = 19
    with pytest.raises(ValueError, match="Extra inputs"):
        bind_quote_date_result(result, packet)


def test_new_schema_specializes_paragraph_aliases_and_forbids_offsets():
    packet, result = _one("January 2, 1900")
    original = quote_date_schema()
    schema = specialize_schema(original, packet)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(result)
    properties = schema["$defs"]["QuoteDateEvidence"]["properties"]
    assert properties["paragraph_id"]["enum"] == ["P1"]
    assert set(properties) == {"paragraph_id", "raw_sha256", "quote"}
    assert original == quote_date_schema()
    invalid = deepcopy(result)
    invalid["dates"][0]["evidence"][0]["start"] = 0
    assert not Draft202012Validator(schema).is_valid(invalid)


def test_old_actual_failure_remains_invalid_not_reinterpreted():
    packet = json.loads((LIVE / "compatibility/prepared/provider-inputs.jsonl").read_text())
    path = LIVE / "compatibility/run/summary.json"
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    saved = json.loads(path.read_text())["results"][0]["result"]
    raw = json.loads(saved["output_text"])
    with pytest.raises(ValueError, match="quote/offset mismatch"):
        validate_date_result(raw, packet)
    with pytest.raises(ValueError, match="Extra inputs"):
        QuoteDateResult.model_validate(raw)
    fixture = _quotes(raw)
    assert bind_quote_date_result(fixture, packet)["dates"][0]["evidence"][0]["start"] == 53
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert json.loads(path.read_text())["results"][0]["status"] == "invalid"


def test_existing_runner_saves_offset_free_reply_and_separate_host_coordinates(tmp_path):
    case = HELPERS["_date_cases"]()[1]
    options = HELPERS["_prepared"](tmp_path, "scoped-date-quotes-v1", [case["packet"]])
    reply = HELPERS["_response"](_quotes(case["result"]))
    sent = []

    def caller(*args):
        sent.append(1)
        return reply

    first = execute(options, live=True, caller=caller)
    execute(options, live=True, caller=caller)
    assert sent == [1]
    saved = first["results"][0]["result"]
    assert saved["output_text"] == reply["output_text"]
    mapped = saved["source_mapped_proposals"]
    assert mapped["model_contract"] == "scoped-date-quotes-v1"
    assert mapped["dates"] == case["result"]["dates"]
    assert mapped["model_proposals"] == json.loads(reply["output_text"])


def test_quote_contract_recovers_saved_reply_in_a_fresh_process(tmp_path):
    cases = HELPERS["_date_cases"]()
    options = HELPERS["_prepared"](tmp_path, "scoped-date-quotes-v1", [c["packet"] for c in cases])
    (tmp_path / "options.json").write_text(options.model_dump_json())
    replies = {c["case_id"]: HELPERS["_response"](_quotes(c["result"])) for c in cases}
    (tmp_path / "replies.json").write_text(json.dumps(replies))
    assert RECOVERY["_process"](tmp_path, "saved_reply").returncode == -signal.SIGKILL
    resumed = RECOVERY["_process"](tmp_path, "resume")
    assert resumed.returncode == 0, resumed.stderr
    assert len(RECOVERY["_sent"](tmp_path)) == 2
    summary = json.loads((tmp_path / "result.json").read_text())
    assert summary["statuses"]["valid"] == 2
    assert (
        summary["results"][1]["result"]["source_mapped_proposals"]["model_contract"]
        == "scoped-date-quotes-v1"
    )


def test_unicode_normalization_is_not_an_exact_match():
    packet, result = _one("e\u0301 January 2, 1900", quote="é January 2, 1900")
    with pytest.raises(ValueError, match="not found"):
        bind_quote_date_result(result, packet)


def test_uniqueness_is_within_declared_paragraph_not_whole_window():
    packet, result = _one("January 2, 1900")
    second = {**packet["paragraphs"][0], "alias": "P2", "source_paragraph_id": "synthetic::p2"}
    packet["paragraphs"].append(second)
    item = deepcopy(result["dates"][0])
    item["target_ids"] = ["P2"]
    item["evidence"][0]["paragraph_id"] = "P2"
    result["dates"].append(item)
    assert len(bind_quote_date_result(result, packet)["dates"]) == 2


@pytest.mark.parametrize("provider", ["openai", "ollama"])
def test_quote_contract_uses_existing_fake_client_transport(monkeypatch, provider):
    from contextlib import nullcontext
    from types import SimpleNamespace as NS

    from congressional_globe import role_provider

    packet, result = _one("January 2, 1900")
    output = json.dumps(result)
    captured = {}
    response = NS(
        id="offline-only",
        status="completed",
        output_text=output,
        output=[],
        usage=None,
        incomplete_details=None,
        choices=[NS(message=NS(content=output, refusal=None), finish_reason="stop")],
    )
    response.model_dump = lambda mode: {"id": "offline-only", "output_text": output}

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
    adapter = role_provider.RoleProvider(provider, "offline-model", base_url="http://localhost:1")
    reply = adapter.call(packet, "Quote-only date protocol", quote_date_schema())
    assert bind_quote_date_result(json.loads(reply["output_text"]), packet)
    instruction = (
        captured["instructions"] if provider == "openai" else captured["messages"][0]["content"]
    )
    assert "Do not include start/end in evidence objects" in instruction
    assert "Keep value.start/value.end dates" in instruction
