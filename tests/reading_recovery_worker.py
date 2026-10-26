"""Test-only subprocess peer for synthetic reading recovery; never a user command."""

from __future__ import annotations

import io
import json
import os
import sys
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from pydantic import BaseModel, ConfigDict

from congressional_globe.reading_contracts import ReadingCandidate
from congressional_globe.reading_dispatch import (
    RequestReadiness,
    RuntimeCheck,
    _parse_and_derive,
    _task_id,
    dispatch,
)
from congressional_globe.reading_requests import digest
from congressional_globe.reading_run_store import ReadingRunStore


class RecoveryFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fixture_config: dict
    tasks: list[dict]
    records: list[dict]
    units: list[ReadingCandidate]
    readiness: dict[str, RequestReadiness]
    runtime: RuntimeCheck
    raw_replies: dict[str, str]


def _forbid_network(*args, **kwargs):
    raise AssertionError("synthetic recovery worker must never open a socket")


def _pause(phase: str) -> None:
    print(json.dumps({"checkpoint": phase, "pid": os.getpid()}), flush=True)
    sys.stdin.buffer.read(1)
    raise AssertionError("parent must kill this test worker at the committed checkpoint")


def _install_checkpoint(store: ReadingRunStore, phase: str) -> None:
    names = {
        "claim": "claim",
        "reply": "record_reply",
        "completion": "complete",
        "invalid_reply": "complete",
        "http_failure": "fail",
        "transport_error": "record_transport_error",
    }
    original = getattr(store, names[phase])

    def committed(*args, **kwargs):
        result = original(*args, **kwargs)
        _pause(phase)
        return result

    setattr(store, names[phase], committed)


def _timeout() -> io.BytesIO:
    raise TimeoutError("synthetic unknown transport outcome")


def _http_failure() -> io.BytesIO:
    raise HTTPError(
        "http://localhost/synthetic",
        503,
        "synthetic",
        Message(),
        io.BytesIO(b"synthetic service failure"),
    )


def _fake_response(phase: str, raw: str) -> io.BytesIO:
    handlers = {
        "transport_error": _timeout,
        "http_failure": _http_failure,
        "invalid_reply": lambda: io.BytesIO(b"not JSON; preserve exactly"),
    }
    return handlers.get(phase, lambda: io.BytesIO(raw.encode()))()


def _opener(root: Path, fixture: RecoveryFixture, phase: str):
    by_hash = {record["request_sha256"]: record for record in fixture.records}

    def open_fake(request, timeout):
        request_hash = digest(request.data)
        record = by_hash[request_hash]
        with (root / "fake-transport.jsonl").open("a") as stream:
            stream.write(
                json.dumps(
                    {
                        "task_id": _task_id(record),
                        "request_sha256": request_hash,
                        "pid": os.getpid(),
                    }
                )
                + "\n"
            )
            stream.flush()
            os.fsync(stream.fileno())
        return _fake_response(phase, fixture.raw_replies[request_hash])

    return open_fake


def _recover_reply(store: ReadingRunStore, fixture: RecoveryFixture) -> None:
    row = store._db.execute("SELECT * FROM attempts WHERE status='inflight'").fetchone()
    records = {_task_id(record): record for record in fixture.records}
    record = records[row["task_id"]]
    ready = fixture.readiness[row["task_id"]]
    units = {unit.id: unit for unit in fixture.units}
    _parse_and_derive(
        {**record, "expected_input_tokens": ready.expected_input_tokens},
        units[record["unit_id"]],
        json.loads(row["raw_reply"]),
    )
    store.complete(row["attempt_id"], "valid")


def _dispatch(store: ReadingRunStore, fixture: RecoveryFixture, root: Path, phase: str) -> list:
    from contextlib import nullcontext

    runtime = fixture.runtime.model_copy(update={"checked_at": datetime.now(UTC)})
    readiness: dict[str, RequestReadiness | dict] = dict(fixture.readiness)
    return dispatch(
        store,
        fixture.records,
        {unit.id: unit for unit in fixture.units},
        readiness,
        runtime,
        "http://localhost:1",
        opt_in=True,
        opener=_opener(root, fixture, phase),
        lock_factory=nullcontext,
        max_calls=2,
        total_seconds=60,
        per_model_seconds=60,
        call_seconds=10,
    )


def _action(store: ReadingRunStore, fixture: RecoveryFixture, root: Path, mode: str, phase: str):
    if mode == "recover_reply":
        _recover_reply(store, fixture)
        return []
    if mode == "reconcile":
        row = store._db.execute(
            "SELECT attempt_id FROM attempts WHERE status='inflight'"
        ).fetchone()
        store.reconcile(
            row["attempt_id"],
            "timeout",
            "Synthetic explicit reconciliation; elapsed and usage remain as recorded",
        )
        return []
    return _dispatch(store, fixture, root, phase)


def run(root: Path, mode: str, phase: str) -> dict:
    fixture = RecoveryFixture.model_validate_json((root / "fixture.json").read_text())
    with patch("socket.socket", _forbid_network):
        return _run_store(root, fixture, mode, phase)


def _run_store(root: Path, fixture: RecoveryFixture, mode: str, phase: str) -> dict:
    store = ReadingRunStore(root / "attempts.sqlite", fixture.fixture_config, fixture.tasks)
    try:
        if mode == "interrupt":
            _install_checkpoint(store, phase)
        return _result(store, fixture, root, mode, phase)
    finally:
        store.close()


def _result(store, fixture, root, mode, phase) -> dict:
    try:
        results = _action(store, fixture, root, mode, phase)
        outcome = {"state": "returned", "result_task_ids": [r["task_id"] for r in results]}
    except ValueError as exc:
        outcome = {"state": "blocked", "reason": str(exc)}
    return {
        "pid": os.getpid(),
        "outcome": outcome,
        "attempts": [
            dict(row) for row in store._db.execute("SELECT * FROM attempts ORDER BY rowid")
        ],
        "summary": store.summary(),
        "timing": store.timing_summary(),
        "network_calls": 0,
    }


if __name__ == "__main__":
    print(json.dumps(run(Path(sys.argv[1]), sys.argv[2], sys.argv[3])), flush=True)
