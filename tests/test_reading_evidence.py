"""Portable pickup acceptance proof using synthetic sources, images and journals."""

import argparse
import json
import socket
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest
from test_reading_dispatch import _reply
from test_reading_images import _fake_download, fixture

from congressional_globe import reading_images as images
from congressional_globe import reading_requests as requests
from congressional_globe.reading_budget_audit import _unique_attempts, audit_budget
from congressional_globe.reading_cli import (
    _load_run_snapshot,
    _reading_status,
    _reading_verify,
    _review_state,
    run_reading,
)
from congressional_globe.reading_evidence import (
    InspectionEvidence,
    _check_count,
    _one_request,
    binary_binding,
    file_hash,
)
from congressional_globe.reading_quote_expansion import task_id
from congressional_globe.reading_run_store import ReadingRunStore


def _ref(path):
    return {"path": str(path), "sha256": file_hash(path)}


def _write(path, value):
    path.write_text(json.dumps(value))
    return _ref(path)


def _store(path, record, config):
    store = ReadingRunStore(
        path / "attempts.sqlite",
        config,
        [
            dict(
                task_id=task_id(record),
                request_sha256=record["request_sha256"],
                model_digest=record["model_digest"],
            )
        ],
    )
    attempt = store.claim(task_id(record), json.loads(requests.materialize_record(record)))
    store.record_reply(attempt, _reply(record), {"prompt_eval_count": 12, "eval_count": 8})
    store.record_elapsed(attempt, 1)
    store.complete(attempt, "valid")
    store.close()
    return _load_run_snapshot(path)


def _source_fixture(tmp_path, monkeypatch):
    unit, plan = fixture()
    monkeypatch.setattr(images.scan_fetch, "download", _fake_download(plan, []))
    binding = images.fetch_plan(tmp_path, plan, images.TransferBudget(tmp_path))
    index = _write(tmp_path / "index.json", {"bindings": [binding], "reused": []})
    candidates = tmp_path / "candidates.jsonl"
    candidates.write_text(unit.model_dump_json() + "\n")
    image = requests.ImageInput(
        id=plan.id,
        path=Path(binding["directory"]) / "crop.jpg",
        sha256=file_hash(Path(binding["directory"]) / "crop.jpg"),
        sources=[s.model_dump() for s in images.evidence_coverage(plan, unit)],
    )
    model = next(iter(requests.SUPPORTED_MODELS))
    record = requests.describe_request(
        unit, [image], model, "current prompt", {"type": "object"}, requests.RequestOptions()
    )
    prior = requests.describe_request(
        unit, [image], model, "prior prompt", {"type": "object"}, requests.RequestOptions()
    )
    return record, prior, index, _ref(candidates)


def _prior_fixture(tmp_path, prior):
    run = tmp_path / "prior"
    snapshot = _store(run, prior, {"call_seconds": 10})
    manifest = _write(tmp_path / "prior-requests.json", {"requests": [prior]})
    row = snapshot["rows"][0]
    exported = {**row, "request_sha256": prior["request_sha256"]}
    export = _write(tmp_path / "prior-export.json", {"attempts": [exported]})
    attempt = {
        key: row[key]
        for key in (
            "attempt_id",
            "task_id",
            "status",
            "started_at",
            "finished_at",
            "elapsed_seconds",
        )
    }
    reuse = _write(
        tmp_path / "reuse.json",
        {
            "requests": [dict(attempt=attempt, request=prior)],
            "source_manifest": manifest,
            "source_attempt_export": export,
        },
    )
    return snapshot, reuse, run


def _protocol_fixture(tmp_path, manifest):
    observations = _write(tmp_path / "observations.json", {"synthetic": True})
    review = _write(tmp_path / "review.json", {"answer": "Use the 10-minute review plan"})
    protocol = _write(
        tmp_path / "protocol.json",
        {
            "source_expectations_frozen": True,
            "source_expectations": observations,
            "evidence": {manifest["path"]: manifest["sha256"], review["path"]: review["sha256"]},
        },
    )
    return protocol, review


def _counts_fixture(tmp_path, record, manifest):
    runtime, counter = tmp_path / "runtime", tmp_path / "counter"
    runtime.write_bytes(b"synthetic runtime")
    counter.write_bytes(b"different synthetic counter")
    row = dict(
        request_sha256=record["request_sha256"],
        model=record["model"],
        model_digest=record["model_digest"],
        unit_id=record["unit_id"],
        text_tokens=10,
        image_tokens=2,
        total_input_tokens=12,
        images=[{k: image[k] for k in ("id", "path", "sha256")} for image in record["images"]],
        requested_num_ctx=16384,
        requested_num_predict=4096,
    )
    counts = _write(
        tmp_path / "counts.json",
        dict(
            request_manifest=manifest,
            counts=[row],
            runtime_binary_sha256=file_hash(runtime),
            counter_binary_sha256=file_hash(counter),
        ),
    )
    return counts, runtime, counter


@pytest.fixture
def inspection(tmp_path, monkeypatch):
    record, prior, index, candidates = _source_fixture(tmp_path, monkeypatch)
    snapshot, reuse, prior_run = _prior_fixture(tmp_path, prior)
    manifest = _write(
        tmp_path / "requests.json", {"requests": [record], "reused_requests": [prior]}
    )
    protocol, review = _protocol_fixture(tmp_path, manifest)
    counts, runtime, counter = _counts_fixture(tmp_path, record, manifest)
    budget = _write(
        tmp_path / "budget.json",
        dict(
            approved_bounds=dict(
                max_calls=5, max_total_seconds=100, max_model_seconds=100, max_call_seconds=10
            ),
            prior_usage=dict(
                calls=1,
                total_seconds=1,
                by_model={prior["model"]: {"conservative_total_seconds": 1}},
            ),
            sources={str(prior_run / "attempts.sqlite"): file_hash(prior_run / "attempts.sqlite")},
        ),
    )
    roles = dict(
        requests=manifest,
        counts=counts,
        protocol=protocol,
        review=review,
        candidates=candidates,
        images=index,
    )
    config = dict(
        files={ref["path"]: ref["sha256"] for ref in roles.values()},
        call_seconds=10,
        max_calls=4,
        total_seconds=100,
        per_model_seconds=100,
    )
    run = tmp_path / "current"
    current = _store(run, record, config)
    spec = dict(
        schema_version="reading-inspection-v1",
        config_sha256=current["config_sha256"],
        **roles,
        reuse=reuse,
        budget=budget,
        prior_runs=[dict(run_dir=str(prior_run), config_sha256=snapshot["config_sha256"])],
        runtime_binary=str(runtime),
        counter_binary=str(counter),
        review_database=None,
    )
    path = tmp_path / "inspection.json"
    _write(path, spec)
    return dict(run=run, path=path, spec=spec, record=record, prior=prior, tmp=tmp_path)


def _save_spec(fixture):
    _write(fixture["path"], fixture["spec"])


def _rewrite_role(fixture, role, transform):
    spec = fixture["spec"]
    path = Path(spec[role]["path"])
    data = json.loads(path.read_text())
    transform(data)
    spec[role] = _write(path, data)
    _save_spec(fixture)


def test_complete_synthetic_evidence_passes_without_launch_permission(inspection):
    report = _reading_verify(inspection["run"], inspection["path"])
    assert report["ok"] is True
    assert report["launch_ready"] is False
    assert report["source_fidelity"] == "not_assessed"
    assert report["evidence"]["budget"]["cumulative"]["calls"] == 2
    assert report["evidence"]["bindings"]["reused_requests"] == 1
    assert all(item["ok"] for item in report["evidence"]["binaries"])


def test_duplicate_prior_references_do_not_double_charge(inspection):
    inspection["spec"]["prior_runs"] *= 2
    _save_spec(inspection)
    report = _reading_verify(inspection["run"], inspection["path"])
    assert report["ok"] is True
    budget = report["evidence"]["budget"]
    assert budget["cumulative"]["calls"] == 2
    assert budget["deduplicated_attempt_references"] == 1


@pytest.mark.parametrize(
    "role", ["requests", "counts", "protocol", "review", "candidates", "images", "reuse", "budget"]
)
def test_missing_evidence_cannot_pass(inspection, role):
    Path(inspection["spec"][role]["path"]).unlink()
    assert _reading_verify(inspection["run"], inspection["path"])["ok"] is False


@pytest.mark.parametrize("field", ["runtime_binary", "counter_binary"])
def test_each_binary_checked_against_its_own_hash(inspection, field):
    Path(inspection["spec"][field]).write_bytes(b"changed")
    report = _reading_verify(inspection["run"], inspection["path"])
    assert f"{field}_hash_missing_or_mismatch" in report["errors"]
    checked = {item["artifact"]: item for item in report["evidence"]["binaries"]}
    assert checked[field]["actual_sha256"] != checked[field]["expected_sha256"]
    assert sum(item["ok"] for item in checked.values()) == 1


def test_wrong_run_recipe_rejected(inspection):
    inspection["spec"]["config_sha256"] = "0" * 64
    _save_spec(inspection)
    with pytest.raises(ValueError, match="different run config"):
        _reading_verify(inspection["run"], inspection["path"])


def test_stale_prior_narrative_is_detected(inspection):
    _rewrite_role(inspection, "budget", lambda data: data["prior_usage"].update(total_seconds=0))
    report = _reading_verify(inspection["run"], inspection["path"])
    assert "prior_seconds_narrative_mismatch" in report["errors"]


def test_cumulative_budget_overrun_detected(inspection):
    _rewrite_role(inspection, "budget", lambda data: data["approved_bounds"].update(max_calls=1))
    assert (
        "cumulative_max_calls_exceeded"
        in _reading_verify(inspection["run"], inspection["path"])["errors"]
    )


def test_reuse_must_match_saved_attempt(inspection):
    _rewrite_role(
        inspection, "reuse", lambda data: data["requests"][0]["attempt"].update(status="timeout")
    )
    report = _reading_verify(inspection["run"], inspection["path"])
    assert "cross_run_budget:ValueError" in report["errors"]


def test_changed_context_or_control_cannot_rebind_to_target(inspection):
    record = deepcopy(inspection["record"])
    source = json.loads(record["messages_without_image_payloads"][1]["content"])
    source["target"][0]["raw"] = "fabricated source"
    record["messages_without_image_payloads"][1]["content"] = json.dumps(source)
    from congressional_globe.reading_evidence import _units

    spec = InspectionEvidence.model_validate(inspection["spec"])
    with pytest.raises(ValueError, match="source_or_context"):
        _one_request(record, _units(spec))
    record = deepcopy(inspection["record"])
    record["control_kind"] = "unrelated_image"
    with pytest.raises(ValueError, match="separate source"):
        _one_request(record, _units(spec))


def test_token_count_arithmetic_and_identity_fail(inspection):
    record = inspection["record"]
    count = json.loads(Path(inspection["spec"]["counts"]["path"]).read_text())["counts"][0]
    count["total_input_tokens"] = 11
    with pytest.raises(ValueError, match="sum_mismatch"):
        _check_count(record, count)
    count["model_digest"] = "0" * 64
    with pytest.raises(ValueError, match="model_or_unit"):
        _check_count(record, count)


def test_unknown_elapsed_and_tokens_reserve_full_call_cap(inspection):
    current = _load_run_snapshot(inspection["run"])
    row = current["rows"][0]
    row.update(elapsed_seconds=None, usage_json=None, raw_reply=None, status="timeout")
    spec = InspectionEvidence.model_validate(inspection["spec"])
    assert spec.reuse is not None
    reuse = json.loads(Path(spec.reuse.path).read_text())
    report = audit_budget(spec, current, reuse, _load_run_snapshot)
    assert report["cumulative"]["conservative_seconds"] == 11
    assert report["cumulative"]["unknown_elapsed_attempts"] == 1
    assert report["cumulative"]["unknown_token_usage_attempts"] == 1
    assert report["cumulative"]["known_input_tokens"] == 12
    current["config"].pop("call_seconds")
    with pytest.raises(ValueError, match="reservation"):
        audit_budget(spec, current, reuse, _load_run_snapshot)


def test_conflicting_duplicate_attempt_id_is_rejected(inspection):
    current = _load_run_snapshot(inspection["run"])
    changed = deepcopy(current)
    changed["rows"][0]["elapsed_seconds"] = 5
    with pytest.raises(ValueError, match="conflicting"):
        _unique_attempts([current, changed])


def _tree_hashes(root):
    return {str(p): file_hash(p) for p in root.rglob("*") if p.is_file()}


def test_no_network_or_original_writes_and_bounded_cli(inspection, monkeypatch, capsys):
    before = _tree_hashes(inspection["tmp"])

    def forbidden(*args, **kwargs):
        raise AssertionError("network/store initialization is forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(ReadingRunStore, "__init__", forbidden)
    for action in ("status", "verify"):
        run_reading(
            argparse.Namespace(
                reading_action=action,
                run_dir=inspection["run"],
                evidence=inspection["path"],
                json_out=True,
            ),
            Path("."),
        )
        output = capsys.readouterr().out
        assert len(output.encode()) <= 8192
        assert json.loads(output)
    assert _tree_hashes(inspection["tmp"]) == before


def test_review_database_is_copied_without_initializing_store(tmp_path):
    from congressional_globe.review_store import ReviewStore

    path = tmp_path / "reviews.sqlite"
    ReviewStore(path)
    before = file_hash(path)
    report = _review_state(str(path))
    assert report["pending_unapplied_submissions"] == 0
    assert report["packets_without_submission"] == 0
    assert file_hash(path) == before


def test_missing_binary_reports_expected_and_actual(tmp_path):
    report = binary_binding("counter_binary", str(tmp_path / "missing"), "a" * 64)
    assert report["ok"] is False
    assert report["expected_sha256"] == "a" * 64
    assert report["actual_sha256"] is None


def test_status_provenance_reports_unknown_process_age(inspection):
    report = _reading_status(inspection["run"], inspection["path"])
    assert report["runtime"]["state"] == "observation_unknown"
    assert report["next_action"]["checkpoint_age"].startswith("unknown")
    assert report["next_action"]["ownership"]
    assert report["budget"]["prior_usage"] == "recomputed_see_evidence_verification"


@pytest.mark.parametrize("status,ok", [("valid", False), ("invalid", True)])
def test_corrupt_valid_reply_fails_but_recorded_invalid_reply_is_preserved(inspection, status, ok):
    with sqlite3.connect(inspection["run"] / "attempts.sqlite") as conn:
        conn.execute("UPDATE attempts SET status=?, raw_reply='invalid saved reply'", (status,))
        conn.execute("UPDATE tasks SET status=?", (status,))
    assert _reading_verify(inspection["run"], inspection["path"])["ok"] is ok


def test_inflight_work_stays_unresolved_even_with_complete_evidence(inspection):
    with sqlite3.connect(inspection["run"] / "attempts.sqlite") as conn:
        conn.execute("UPDATE attempts SET status='inflight', elapsed_seconds=NULL, raw_reply=NULL")
        conn.execute("UPDATE tasks SET status='inflight'")
    report = _reading_verify(inspection["run"], inspection["path"])
    assert "inflight_attempt_requires_reconciliation" in report["unresolved"]
    assert report["evidence"]["budget"]["cumulative"]["conservative_seconds"] == 11
    assert report["ok"] is False


def test_failed_explicit_verification_returns_nonzero_json(inspection, capsys):
    Path(inspection["spec"]["counter_binary"]).unlink()
    args = argparse.Namespace(
        reading_action="verify",
        run_dir=inspection["run"],
        evidence=inspection["path"],
        json_out=True,
    )
    with pytest.raises(SystemExit, match="1"):
        run_reading(args, Path("."))
    output = capsys.readouterr().out
    assert len(output.encode()) <= 8192
    assert "counter_binary_hash_missing_or_mismatch" in json.loads(output)["errors"]


@pytest.mark.parametrize("change", ["boolean_calls", "missing_call_cap"])
def test_malformed_budget_authority_cannot_pass(inspection, change):
    def mutate(data):
        if change == "boolean_calls":
            data["approved_bounds"]["max_calls"] = True
        else:
            data["approved_bounds"].pop("max_call_seconds")

    _rewrite_role(inspection, "budget", mutate)
    assert _reading_verify(inspection["run"], inspection["path"])["ok"] is False
