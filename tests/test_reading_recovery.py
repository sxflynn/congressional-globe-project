"""Bounded SIGKILL and fresh-process proofs; all transports and sources are synthetic."""

from __future__ import annotations

import json
import os
import selectors
import signal
import sqlite3
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from test_reading_dispatch import _other_request, _reply, _setup

from congressional_globe.reading_cli import _load_run_snapshot
from congressional_globe.reading_evidence import file_hash
from congressional_globe.reading_requests import materialize_record
from congressional_globe.reading_run_store import ReadingRunStore

WORKER = Path(__file__).with_name("reading_recovery_worker.py").resolve()
REPO = WORKER.parents[1]


def prepare_fixture(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    seed = root / "builder"
    seed.mkdir()
    unit, first, ready, runtime, store = _setup(seed)
    store.close()
    second = _other_request(seed, unit, first)
    second.update(token_fit="verified", launch_ready=True)
    paragraph = unit.target[0].model_copy(update={"paragraph_id": "unrelated-source"})
    other = unit.model_copy(update={"id": second["unit_id"], "target": [paragraph]})
    second_ready = ready.model_copy(update={"request_sha256": second["request_sha256"]})
    records = [first, second]
    tasks = [_task(record) for record in records]
    fixture = dict(
        fixture_config=dict(
            run_id="synthetic-recovery-v1",
            max_calls=2,
            total_seconds=60,
            per_model_seconds=60,
            call_seconds=10,
        ),
        tasks=tasks,
        records=records,
        units=[unit.model_dump(mode="json"), other.model_dump(mode="json")],
        readiness={
            tasks[0]["task_id"]: ready.model_dump(mode="json"),
            tasks[1]["task_id"]: second_ready.model_dump(mode="json"),
        },
        runtime=runtime.model_dump(mode="json"),
        raw_replies={record["request_sha256"]: _reply(record) for record in records},
    )
    (root / "fixture.json").write_text(json.dumps(fixture, sort_keys=True))
    return fixture


def _task(record: dict) -> dict:
    return dict(
        task_id=f"{record['model']}::{record['unit_id']}",
        request_sha256=record["request_sha256"],
        model_digest=record["model_digest"],
    )


def _environment() -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO / "src"), str(REPO / "tests"), env.get("PYTHONPATH", "")]
    )
    return env


def _command(root: Path, mode: str, phase: str) -> list[str]:
    return [sys.executable, str(WORKER), str(root), mode, phase]


def _process_identity(pid: int) -> dict:
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "pid=,lstart=,command="],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"state": "observation_unknown", "pid_start_command": None}
    return {
        "state": "observed" if result.returncode == 0 else "observation_unknown",
        "pid_start_command": result.stdout.strip(),
    }


def kill_at_checkpoint(root: Path, phase: str) -> dict:
    command = _command(root, "interrupt", phase)
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_environment(),
    )
    try:
        checkpoint = _checkpoint(process)
        assert checkpoint == {"checkpoint": phase, "pid": process.pid}
        identity = _process_identity(process.pid)
        process.kill()
        _, errors = process.communicate(timeout=10)
        assert process.returncode == -signal.SIGKILL, errors
        return {
            "command": command,
            "pid": process.pid,
            "checkpoint": phase,
            "returncode": process.returncode,
            "os_observation": identity,
        }
    finally:
        _cleanup(process)


def _checkpoint(process) -> dict:
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        if not selector.select(timeout=10):
            raise TimeoutError("synthetic worker did not reach checkpoint within10seconds")
        line = process.stdout.readline()
    if not line:
        raise AssertionError("synthetic worker exited before checkpoint: " + process.stderr.read())
    return json.loads(line)


def _cleanup(process) -> None:
    if process.poll() is None:
        process.kill()
        process.communicate(timeout=10)


def run_peer(root: Path, mode="resume", phase="normal", *, check=True):
    result = subprocess.run(
        _command(root, mode, phase),
        env=_environment(),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if check:
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    return result


def fake_calls(root: Path) -> list:
    path = root / "fake-transport.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def _snapshot(root: Path) -> dict:
    return _load_run_snapshot(root)


@pytest.mark.parametrize(
    "phase", ["claim", "reply", "completion", "transport_error", "invalid_reply", "http_failure"]
)
def test_forced_kill_then_separate_process_preserves_and_never_repeats(root_case, phase):
    root, fixture = root_case
    frozen = file_hash(root / "fixture.json")
    stopped = kill_at_checkpoint(root, phase)
    saved = _snapshot(root)["rows"][0]
    assert saved["request_json"] == materialize_record(fixture["records"][0]).decode()
    resumed = run_peer(root)
    assert resumed["pid"] != stopped["pid"]
    assert resumed["attempts"][0] == saved
    _assert_resume_outcome(root, phase, resumed)
    assert file_hash(root / "fixture.json") == frozen


def _assert_resume_outcome(root: Path, phase: str, resumed: dict) -> None:
    if phase in {"claim", "reply", "transport_error"}:
        assert resumed["outcome"]["state"] == "blocked"
        assert "unresolved" in resumed["outcome"]["reason"]
        assert len(resumed["attempts"]) == 1
        assert len(fake_calls(root)) == (0 if phase == "claim" else 1)
        return
    assert resumed["outcome"]["state"] == "returned"
    assert len(fake_calls(root)) == 2
    assert len({call["request_sha256"] for call in fake_calls(root)}) == 2
    repeated = run_peer(root)
    assert repeated["outcome"]["result_task_ids"] == []
    assert repeated["attempts"] == resumed["attempts"]
    assert len(fake_calls(root)) == 2


@pytest.fixture
def root_case(tmp_path):
    return tmp_path, prepare_fixture(tmp_path)


def test_saved_reply_replays_offline_without_resending_and_unknown_time_stays_unknown(root_case):
    root, fixture = root_case
    kill_at_checkpoint(root, "reply")
    saved = _snapshot(root)["rows"][0]
    assert saved["elapsed_seconds"] is None
    assert saved["usage_json"] is not None
    recovered = run_peer(root, "recover_reply")
    row = recovered["attempts"][0]
    assert row["status"] == "valid"
    assert row["raw_reply"] == fixture["raw_replies"][fixture["records"][0]["request_sha256"]]
    assert row["usage_json"] == saved["usage_json"]
    assert row["elapsed_seconds"] is None
    blocked = run_peer(root)
    assert "time is unknown" in blocked["outcome"]["reason"]
    assert len(fake_calls(root)) == 1


def test_reconciliation_keeps_unknown_usage_and_elapsed_in_new_process(root_case):
    root, _ = root_case
    kill_at_checkpoint(root, "claim")
    reconciled = run_peer(root, "reconcile")
    row = reconciled["attempts"][0]
    assert row["status"] == "timeout"
    assert row["usage_json"] is None
    assert row["elapsed_seconds"] is None
    blocked = run_peer(root)
    assert "time is unknown" in blocked["outcome"]["reason"]
    assert not fake_calls(root)


@pytest.mark.parametrize("change", ["config", "task", "request"])
def test_new_process_rejects_incompatible_inputs_before_fake_transport(root_case, change):
    root, fixture = root_case
    ReadingRunStore(root / "attempts.sqlite", fixture["fixture_config"], fixture["tasks"]).close()
    saved = _snapshot(root)
    changed = deepcopy(fixture)
    _alter_fixture(changed, change)
    (root / "fixture.json").write_text(json.dumps(changed))
    result = run_peer(root, check=False)
    _assert_rejected(result, change)
    assert _snapshot(root) == saved
    assert not fake_calls(root)


def _alter_fixture(fixture: dict, change: str) -> None:
    if change == "config":
        fixture["fixture_config"]["run_id"] = "different"
    elif change == "task":
        fixture["tasks"][0]["request_sha256"] = "0" * 64
    else:
        fixture["records"][0]["options"]["num_predict"] = 1


def _assert_rejected(result, change: str) -> None:
    if change == "request":
        assert result.returncode == 0
        assert json.loads(result.stdout)["outcome"]["state"] == "blocked"
    else:
        assert result.returncode != 0
        assert "identity does not match" in result.stderr


def test_direct_claim_rejects_changed_frozen_request(root_case):
    root, fixture = root_case
    store = ReadingRunStore(root / "attempts.sqlite", fixture["fixture_config"], fixture["tasks"])
    request = json.loads(materialize_record(fixture["records"][0]))
    request["model"] = "different-model"
    with pytest.raises(ValueError, match="frozen task request_sha256"):
        store.claim(fixture["tasks"][0]["task_id"], request)
    assert store.summary()["pending"] == 2
    assert store.timing_summary()["calls"] == 0
    store.close()


def _legacy(root: Path, fixture: dict) -> dict:
    store = ReadingRunStore(root / "attempts.sqlite", fixture["fixture_config"], fixture["tasks"])
    record = fixture["records"][0]
    aid = store.claim(fixture["tasks"][0]["task_id"], json.loads(materialize_record(record)))
    store.record_reply(aid, fixture["raw_replies"][record["request_sha256"]], None)
    store.complete(aid, "valid")
    store.close()
    with sqlite3.connect(root / "attempts.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("ALTER TABLE attempts DROP COLUMN elapsed_seconds")
        return dict(conn.execute("SELECT * FROM attempts").fetchone())


def test_compatible_legacy_migration_preserves_reply_and_unknown_usage(root_case):
    root, fixture = root_case
    legacy = _legacy(root, fixture)
    resumed = run_peer(root)
    row = resumed["attempts"][0]
    assert {key: row[key] for key in legacy} == legacy
    assert row["elapsed_seconds"] is None
    assert row["usage_json"] is None
    assert "time is unknown" in resumed["outcome"]["reason"]
    assert not fake_calls(root)


def test_incompatible_legacy_open_does_not_migrate_or_mutate_data(root_case):
    root, fixture = root_case
    _legacy(root, fixture)
    before = file_hash(root / "attempts.sqlite")
    fixture["fixture_config"]["run_id"] = "wrong"
    (root / "fixture.json").write_text(json.dumps(fixture))
    result = run_peer(root, check=False)
    assert result.returncode != 0
    assert "identity does not match" in result.stderr
    assert file_hash(root / "attempts.sqlite") == before
    with sqlite3.connect(root / "attempts.sqlite") as conn:
        assert "elapsed_seconds" not in {
            row[1] for row in conn.execute("PRAGMA table_info(attempts)")
        }


def test_future_schema_is_rejected_without_mutation(root_case):
    root, fixture = root_case
    ReadingRunStore(root / "attempts.sqlite", fixture["fixture_config"], fixture["tasks"]).close()
    with sqlite3.connect(root / "attempts.sqlite") as conn:
        conn.execute("PRAGMA user_version=999")
    before = file_hash(root / "attempts.sqlite")
    result = run_peer(root, check=False)
    assert result.returncode != 0
    assert "unsupported reading journal schema version" in result.stderr
    assert file_hash(root / "attempts.sqlite") == before
    assert not fake_calls(root)


@pytest.mark.parametrize("table", ["tasks", "attempts"])
def test_missing_journal_tables_are_not_silently_recreated(root_case, table):
    root, fixture = root_case
    ReadingRunStore(root / "attempts.sqlite", fixture["fixture_config"], fixture["tasks"]).close()
    with sqlite3.connect(root / "attempts.sqlite") as conn:
        conn.execute(f"DROP TABLE {table}")
    before = file_hash(root / "attempts.sqlite")
    result = run_peer(root, check=False)
    assert result.returncode != 0
    assert "incomplete reading journal schema" in result.stderr
    assert file_hash(root / "attempts.sqlite") == before
    assert not fake_calls(root)
