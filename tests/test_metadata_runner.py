"""The existing bounded runner consumes exact role/date sources without a network."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from congressional_globe.metadata_results import metadata_schema
from congressional_globe.role_aliases import prepare_aliases
from congressional_globe.role_run_io import RunOptions
from congressional_globe.role_runner import execute

ARTIFACTS = Path(__file__).parents[1] / "artifacts"
DATES = ARTIFACTS / "scoped-date-contract-20261026-01/fixtures.json"
ROLES = ARTIFACTS / "role-alias-preparation-20261023-02/frozen-inputs.jsonl"


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n")


def _prepared(tmp_path, contract, sources):
    path = tmp_path / "prepared"
    path.mkdir()
    packets = sources
    if contract != "scoped-date-v1":
        packets = [prepare_aliases(source)["input"] for source in sources]
    _write_jsonl(path / "provider-inputs.jsonl", packets)
    _write_jsonl(path / "frozen-inputs.jsonl", sources)
    (path / "prompt.txt").write_text("Offline integration fixture; preserve unsupported unknowns.")
    _write(path / "output.schema.json", metadata_schema(contract))
    _write(path / "source-review.json", {"status": "test fixture, not human-reviewed"})
    _write(path / "checks.json", {"source_review_sha256": _hash(path / "source-review.json")})
    names = ["provider-inputs.jsonl", "frozen-inputs.jsonl", "prompt.txt", "output.schema.json"]
    _write(path / "manifest.json", {"files_sha256": {name: _hash(path / name) for name in names}})
    return RunOptions(
        prepared=path,
        output=tmp_path / "run",
        provider="openai",
        model="gpt-5.4-mini",
        base_url="https://example.invalid/v1",
        contract=contract,
        timeout=1,
        max_seconds=30,
    )


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def _response(result):
    return {
        "raw_response": json.dumps({"fixture_output": result}),
        "output_text": json.dumps(result),
        "status": "completed",
        "finish_reason": None,
        "usage": None,
        "provider_request_id": "offline-fixture",
    }


def _date_cases():
    return json.loads(DATES.read_text())["cases"]


def _role_source():
    return next(json.loads(line) for line in ROLES.read_text().splitlines())


def test_two_date_packets_export_exact_evidence_and_unknowns_then_reuse(tmp_path):
    cases = _date_cases()
    options = _prepared(tmp_path, "scoped-date-v1", [c["packet"] for c in cases])
    replies = {c["case_id"]: _response(c["result"]) for c in cases}
    sent = []

    def caller(packet, prompt, schema):
        sent.append(packet["window_id"])
        assert schema == metadata_schema("scoped-date-v1")
        return replies[packet["window_id"]]

    first = execute(options, live=True, caller=caller)
    second = execute(options, live=True, caller=caller)
    assert sent == [c["case_id"] for c in cases]
    assert first["statuses"]["valid"] == second["statuses"]["valid"] == 2
    report = json.loads((options.output / "proposals.json").read_text())
    assert report["historical_status"] == "proposal_only_not_human_reviewed"
    for row, case in zip(report["results"], cases, strict=True):
        assert row["source_mapped_proposals"] == case["mapped"]
    assert first["results"][0]["result"]["usage"] is None
    assert first["api_cost_usd_estimate"] is None


def test_role_v2_paragraph_evidence_unknown_stays_unknown_and_unannotated_visible(tmp_path):
    source = _role_source()
    options = _prepared(tmp_path, "role-v2", [source])
    result = {
        "speaker_roles": [
            {
                "candidate_id": None,
                "evidence_ids": ["P1"],
                "target_ids": ["P1"],
                "role": "other",
                "status": "unknown",
                "basis": "No supported identity in this fixture.",
            }
        ]
    }
    summary = execute(options, live=True, caller=lambda *args: _response(result))
    assert summary["statuses"]["valid"] == 1
    mapped = summary["results"][0]["result"]["source_mapped_proposals"]
    assert mapped["speaker_roles"] == result["speaker_roles"]
    assert mapped["raw_text"] == source["raw_text"]
    assert mapped["raw_sha256"] == source["raw_sha256"]
    assert mapped["source_anchor"] == source["source_anchor"]
    assert mapped["unannotated_target_ids"]
    span = mapped["spans"][0]
    assert span["source_paragraph_id"] == source["spans"][0]["source_paragraph_id"]
    assert mapped["raw_text"][span["start"] : span["end"]] == span["text"]


def test_role_v1_does_not_silently_gain_v2_unknown_rules(tmp_path):
    options = _prepared(tmp_path, "role-v1", [_role_source()])
    result = {
        "speaker_roles": [
            {
                "candidate_id": None,
                "evidence_ids": ["P1"],
                "target_ids": ["P1"],
                "role": "other",
                "status": "unknown",
                "basis": "Unknown fixture.",
            }
        ]
    }
    summary = execute(options, live=True, caller=lambda *args: _response(result))
    assert summary["statuses"]["invalid"] == 1
    assert summary["results"][0]["result"]["raw_response"] == _response(result)["raw_response"]


def test_date_boundary_failure_keeps_raw_reply_and_exports_no_proposal(tmp_path):
    case = _date_cases()[1]
    options = _prepared(tmp_path, "scoped-date-v1", [case["packet"]])
    bad = deepcopy(case["result"])
    bad["dates"][1]["target_ids"] = [p["alias"] for p in case["packet"]["paragraphs"]]
    response = _response(bad)
    summary = execute(options, live=True, caller=lambda *args: response)
    saved = summary["results"][0]["result"]
    assert summary["statuses"]["invalid"] == 1
    assert "boundary" in saved["validation_error"]
    assert saved["raw_response"] == response["raw_response"]
    report = json.loads((options.output / "proposals.json").read_text())
    assert report["results"][0]["source_mapped_proposals"] is None


@pytest.mark.parametrize("contract", ["role-v2", "scoped-date-v1"])
def test_schema_mismatch_refuses_before_output_or_caller(tmp_path, contract):
    sources = [_role_source()] if contract == "role-v2" else [_date_cases()[1]["packet"]]
    options = _prepared(tmp_path, contract, sources)
    wrong = options.model_copy(update={"contract": "role-v1"})
    calls = []
    with pytest.raises(ValueError):
        execute(wrong, live=True, caller=lambda *args: calls.append(args) or {})
    assert not calls
    assert not options.output.exists()


def test_frozen_source_tampering_refuses_even_with_refreshed_file_hash(tmp_path):
    options = _prepared(tmp_path, "scoped-date-v1", [_date_cases()[1]["packet"]])
    path = options.prepared / "frozen-inputs.jsonl"
    source = json.loads(path.read_text())
    source["paragraphs"][0]["raw_text"] += " changed"
    _write(path, source)
    manifest_path = options.prepared / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files_sha256"][path.name] = _hash(path)
    _write(manifest_path, manifest)
    with pytest.raises(ValueError, match="hash mismatch"):
        execute(options)
    assert not options.output.exists()


def test_missing_required_manifest_binding_is_rejected(tmp_path):
    options = _prepared(tmp_path, "scoped-date-v1", [_date_cases()[1]["packet"]])
    path = options.prepared / "manifest.json"
    manifest = json.loads(path.read_text())
    del manifest["files_sha256"]["provider-inputs.jsonl"]
    _write(path, manifest)
    with pytest.raises(ValueError, match="required file hashes"):
        execute(options)


def test_changed_contract_rejects_completed_journal_reuse(tmp_path):
    source = _role_source()
    options = _prepared(tmp_path, "role-v1", [source])
    result = {"speaker_roles": []}
    execute(options, live=True, caller=lambda *args: _response(result))
    schema_path = options.prepared / "output.schema.json"
    _write(schema_path, metadata_schema("role-v2"))
    manifest_path = options.prepared / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files_sha256"][schema_path.name] = _hash(schema_path)
    _write(manifest_path, manifest)
    with pytest.raises(ValueError, match="identity"):
        execute(
            options.model_copy(update={"contract": "role-v2"}),
            live=True,
            caller=lambda *args: pytest.fail("incompatible result must not be resent"),
        )
