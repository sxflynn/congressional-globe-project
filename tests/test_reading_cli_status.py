"""Portable adversarial proofs for offline pickup inspection."""

import argparse
import hashlib
import json
import socket
import sqlite3
from pathlib import Path

import pytest

from congressional_globe import reading_cli
from congressional_globe.reading_run_store import ReadingRunStore, _hash


def _fixture(tmp_path, *, finish=True, elapsed=12):
    request = {"model": "fixture"}
    store = ReadingRunStore(
        tmp_path / "attempts.sqlite",
        {"max_calls": 1, "total_seconds": 1, "per_model_seconds": 2, "call_seconds": 3},
        [{"task_id": "fixture", "request_sha256": _hash(request)}],
    )
    attempt = store.claim("fixture", request)
    if elapsed is not None:
        store.record_elapsed(attempt, elapsed)
    if finish:
        store.fail(attempt, "timeout", "é" * 20000)
    store.close()
    return tmp_path


def _files(path):
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir() if p.is_file()
    }


def _run(path, action, capsys):
    args = argparse.Namespace(reading_action=action, run_dir=path, json_out=True)
    reading_cli.run_reading(args, Path("."))
    return json.loads(capsys.readouterr().out)


def test_status_counts_unknown_usage_without_dumping_details(tmp_path, capsys):
    _fixture(tmp_path)
    report = _run(tmp_path, "status", capsys)
    assert report["journal_counts"]["terminal"] == 1
    assert report["unknown_usage"]["unknown_token_usage_attempts"] == 1
    assert report["budget"]["remaining_allowance"] is None
    assert report["runtime"] == {"state": "observation_unknown", "launch_ready": False}
    assert "dispatch_next_pending" not in json.dumps(report["next_action"])
    assert len(json.dumps(report).encode()) < reading_cli.MAX_OUTPUT_BYTES


def test_time_overruns_fail_verification_and_cli_exit(tmp_path, capsys):
    _fixture(tmp_path)
    report = reading_cli._reading_verify(tmp_path)
    assert {"exceeds_total_seconds", "exceeds_per_model_seconds", "exceeds_call_seconds"} <= set(
        report["errors"]
    )
    with pytest.raises(SystemExit, match="1"):
        _run(tmp_path, "verify", capsys)
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_unresolved_bindings_prevent_false_success(tmp_path):
    _fixture(tmp_path, elapsed=0)
    report = reading_cli._reading_verify(tmp_path)
    assert report["journal_checks_ok"] is True
    assert report["ok"] is False
    assert report["unresolved"]
    assert report["historical_integrity"] == "not_fully_verified"
    assert report["launch_ready"] is False


@pytest.mark.parametrize(
    "sql,expected",
    [
        ("UPDATE run_identity SET config_sha256='bad'", "config_hash_mismatch"),
        ("UPDATE tasks SET task_sha256='bad'", "task_identity_mismatch"),
        ("UPDATE tasks SET status='pending'", "attempt_task_status_mismatch"),
        ("UPDATE attempts SET request_json='{}'", "request_hash_missing_or_mismatch"),
        ("DELETE FROM attempts", "claimed_task_without_attempt"),
    ],
)
def test_journal_tampering_is_rejected(tmp_path, sql, expected):
    _fixture(tmp_path, elapsed=0)
    with sqlite3.connect(tmp_path / "attempts.sqlite") as conn:
        conn.execute(sql)
    assert expected in reading_cli._reading_verify(tmp_path)["errors"]


def test_inflight_and_unknown_time_are_not_launch_permission(tmp_path):
    _fixture(tmp_path, finish=False, elapsed=None)
    report = reading_cli._reading_verify(tmp_path)
    assert report["timing"]["unknown_elapsed_attempts"] == 1
    assert "inflight_attempt_requires_reconciliation" in report["unresolved"]
    assert "unknown_elapsed_time_requires_conservative_reservation" in report["unresolved"]


def test_no_original_changes_store_constructor_or_network(tmp_path, monkeypatch):
    _fixture(tmp_path)
    before = _files(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected network/store initialization")

    monkeypatch.setattr(ReadingRunStore, "__init__", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    reading_cli._reading_status(tmp_path)
    reading_cli._reading_verify(tmp_path)
    assert _files(tmp_path) == before


def test_wal_snapshot_includes_committed_uncheckpointed_data(tmp_path):
    store = ReadingRunStore(tmp_path / "attempts.sqlite", {}, [{"task_id": "x"}])
    store.claim("x", {"model": "fixture"})
    before = _files(tmp_path)
    assert reading_cli._reading_status(tmp_path)["journal_counts"]["inflight"] == 1
    assert _files(tmp_path) == before
    store.close()


def test_snapshot_change_is_rejected(tmp_path, monkeypatch):
    _fixture(tmp_path)
    original = reading_cli._fingerprints
    calls = []

    def changed(paths):
        calls.append(1)
        return original(paths) if len(calls) == 1 else []

    monkeypatch.setattr(reading_cli, "_fingerprints", changed)
    with pytest.raises(ValueError, match="changed"):
        reading_cli._reading_status(tmp_path)


@pytest.mark.parametrize("action", ["status", "verify"])
def test_missing_run_does_not_create_files_and_exits_nonzero(tmp_path, action, capsys):
    missing = tmp_path / "absent"
    with pytest.raises(SystemExit, match="1"):
        _run(missing, action, capsys)
    assert not missing.exists()
    assert json.loads(capsys.readouterr().out)["error"] == "journal_inspection_failed"


def test_utf8_hard_cap_including_newline(capsys):
    with pytest.raises(SystemExit, match="1"):
        reading_cli._emit({"unexpected": "é" * 10000})
    output = capsys.readouterr().out
    assert len(output.encode()) <= reading_cli.MAX_OUTPUT_BYTES
    assert json.loads(output)["error"] == "output_limit_exceeded"


def test_status_next_action_matches_current_master(tmp_path):
    _fixture(tmp_path)
    state = reading_cli._reading_status(tmp_path)["next_action"]
    data = Path(state["path"]).read_bytes()
    assert state["sha256"] == hashlib.sha256(data).hexdigest()
    assert state["next_action"] in data.decode()


@pytest.mark.parametrize("value", ["NaN", "-1", "Infinity"])
def test_invalid_elapsed_never_becomes_budget_credit(tmp_path, value, capsys):
    _fixture(tmp_path)
    with sqlite3.connect(tmp_path / "attempts.sqlite") as conn:
        conn.execute("UPDATE attempts SET elapsed_seconds=?", (value,))
    with pytest.raises(SystemExit, match="1"):
        _run(tmp_path, "verify", capsys)
    assert json.loads(capsys.readouterr().out)["ok"] is False
