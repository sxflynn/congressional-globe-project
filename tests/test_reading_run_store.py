import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Literal, cast

import pytest

from congressional_globe.reading_run_store import ReadingRunStore


def _store(path, config=None, tasks=None):
    return ReadingRunStore(
        path,
        config or {"model": "fixture", "prompt_version": 1},
        tasks
        or [{"task_id": "a", "text": "synthetic"}, {"task_id": "b", "text": "also synthetic"}],
    )


def test_request_and_raw_reply_are_durable_before_terminal_parse(tmp_path):
    path = tmp_path / "reading.sqlite"
    store = _store(path)
    request = {"messages": [{"role": "user", "content": "synthetic"}], "max_tokens": 8}
    attempt_id = store.claim("a", request)
    assert store.attempt(attempt_id)["request"] == request
    store.record_reply(attempt_id, "not parsed yet", {"input_tokens": 3, "output_tokens": 2})
    store.close()

    resumed = _store(path)
    attempt = resumed.attempt(attempt_id)
    assert attempt["status"] == "inflight"
    assert attempt["raw_reply"] == "not parsed yet"
    assert attempt["usage"] == {"input_tokens": 3, "output_tokens": 2}
    with pytest.raises(ValueError, match="unresolved"):
        resumed.claim("b", {"fixture": True})
    resumed.reconcile(attempt_id, "timeout", "operator confirmed interrupted request")
    assert resumed.next_pending() == {"task_id": "b", "text": "also synthetic"}
    resumed.close()


def test_reply_is_write_once_with_identical_idempotent_save(tmp_path):
    store = _store(tmp_path / "reading.sqlite")
    attempt = store.claim("a", {"prompt": "fixed"})
    usage = {"input_tokens": 3}
    store.record_reply(attempt, "raw", usage)
    store.record_reply(attempt, "raw", usage)
    with pytest.raises(ValueError, match="immutable"):
        store.record_reply(attempt, "changed", usage)
    with pytest.raises(ValueError, match="immutable"):
        store.record_reply(attempt, "raw", {"input_tokens": 4})
    assert store.attempt(attempt)["raw_reply"] == "raw"
    assert store.attempt(attempt)["usage"] == usage
    store.close()


def test_completion_requires_raw_reply(tmp_path):
    store = _store(tmp_path / "reading.sqlite")
    attempt = store.claim("a", {"prompt": "fixed"})
    with pytest.raises(ValueError, match="before raw reply"):
        store.complete(attempt, "valid")
    assert store.attempt(attempt)["status"] == "inflight"
    store.close()


def test_reconcile_rejects_non_failure_status_at_runtime(tmp_path):
    store = _store(tmp_path / "reading.sqlite")
    attempt = store.claim("a", {"prompt": "fixed"})
    with pytest.raises(ValueError, match="reconciliation status"):
        store.reconcile(attempt, cast(Literal["failed", "timeout"], "valid"), "not a failure")
    assert store.attempt(attempt)["status"] == "inflight"
    store.close()


@pytest.mark.parametrize("status", ["valid", "invalid", "failed", "timeout"])
def test_terminal_statuses_replay_without_reclaim(status, tmp_path):
    path = tmp_path / "run.sqlite"
    store = _store(path)
    attempt = store.claim("a", {"prompt": "fixed"})
    store.record_reply(attempt, "{}", {"total_tokens": 1})
    if status in {"valid", "invalid"}:
        store.complete(attempt, status)
    else:
        store.fail(attempt, status, "fixture")
    store.close()
    resumed = _store(path)
    assert resumed.attempt(attempt)["status"] == status
    assert resumed.attempt(attempt)["usage"] == {"total_tokens": 1}
    assert resumed.next_pending()["task_id"] == "b"
    resumed.close()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"config": {"model": "different", "prompt_version": 1}},
        {
            "tasks": [
                {"task_id": "a", "text": "changed"},
                {"task_id": "b", "text": "also synthetic"},
            ]
        },
    ],
)
def test_incompatible_reuse_is_rejected(tmp_path, kwargs):
    path = tmp_path / "run.sqlite"
    _store(path).close()
    with pytest.raises(ValueError, match="identity"):
        _store(path, **kwargs).close()


def test_abrupt_subprocess_leaves_unknown_attempt_and_blocks_other_process(tmp_path):
    path = tmp_path / "run.sqlite"
    _store(path).close()
    script = "\n".join(
        [
            "import os, sys",
            "from pathlib import Path",
            "from congressional_globe.reading_run_store import ReadingRunStore",
            "config = {'model': 'fixture', 'prompt_version': 1}",
            "tasks = [{'task_id': 'a', 'text': 'synthetic'},",
            "         {'task_id': 'b', 'text': 'also synthetic'}]",
            "store = ReadingRunStore(Path(sys.argv[1]), config, tasks)",
            "attempt = store.claim('a', {'body': 'exact request'})",
            "os._exit(23)",
        ]
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")
    child = subprocess.run([sys.executable, "-c", script, str(path)], env=env, check=False)
    assert child.returncode == 23

    second = _store(path)
    row = second._db.execute("SELECT attempt_id FROM attempts").fetchone()
    attempt = second.attempt(row["attempt_id"])
    assert attempt["status"] == "inflight"
    assert attempt["request"] == {"body": "exact request"}
    assert attempt["raw_reply"] is None
    assert attempt["usage"] is None
    with pytest.raises(ValueError, match="unresolved"):
        second.claim("b", {"body": "must not dispatch"})
    second.close()


def test_concurrent_connections_cannot_claim_two_tasks(tmp_path):
    path = tmp_path / "run.sqlite"
    _store(path).close()
    barrier = Barrier(2)

    def attempt_claim(task_id):
        store = _store(path)
        barrier.wait()
        try:
            return store.claim(task_id, {"task": task_id})
        except ValueError:
            return None
        finally:
            store.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            pool.submit(attempt_claim, "a"),
            pool.submit(attempt_claim, "b"),
        ]
        outcomes = [future.result() for future in results]
    assert sum(outcome is not None for outcome in outcomes) == 1
