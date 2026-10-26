"""Durable, provider-agnostic journal for clean-reading pilot attempts.

This module only records work. A caller must explicitly dispatch requests and
must never infer that a persisted in-flight request did or did not reach a provider.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

_TERMINAL = {"valid", "invalid", "failed", "timeout"}


class _Task(BaseModel):
    model_config = ConfigDict(extra="allow")
    task_id: str


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _add_model_time(totals: dict, model: str, elapsed: float) -> None:
    bucket = totals.setdefault(model, {"calls": 0, "seconds": 0.0})
    bucket["calls"] += 1
    bucket["seconds"] += elapsed


def _collect_timing(rows) -> dict:
    totals: dict[str, dict[str, float | int]] = {}
    unknown_elapsed = unknown_model = call_count = 0
    total_seconds = 0.0
    for row in rows:
        model, elapsed = ReadingRunStore._timing_values(row)
        call_count += 1
        unknown_model += not bool(model)
        if elapsed is None:
            unknown_elapsed += 1
            continue
        total_seconds += elapsed
        if model:
            _add_model_time(totals, model, elapsed)
    return {
        "calls": call_count,
        "seconds": total_seconds,
        "models": totals,
        "unknown_elapsed_attempts": unknown_elapsed,
        "unknown_model_attempts": unknown_model,
    }


class ReadingRunStore:
    """Immutable run identity and exactly-once task claims (not a scheduler).

    ``claim(task_id, request)`` durably stores the exact request before returning.
    Then ``record_reply`` stores raw text and usage before parsing. Finish with
    ``complete`` or ``fail``. An in-flight attempt blocks all new claims until
    ``reconcile`` explicitly records its terminal disposition.
    """

    def __init__(self, path: Path, config: dict, tasks: list[dict]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.config = config
        parsed = [_Task.model_validate(task) for task in tasks]
        ids = [task.task_id for task in parsed]
        if len(ids) != len(set(ids)):
            raise ValueError("task_id values must be unique")
        self.tasks = tasks
        self._db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        try:
            self._initialize()
        except BaseException:
            self._db.close()
            raise

    def _initialize(self) -> None:
        version = self._db.execute("PRAGMA user_version").fetchone()[0]
        if version != 0:
            raise ValueError("unsupported reading journal schema version")
        self._check_existing_identity()
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._schema()
        self._identity()

    def _check_existing_identity(self) -> None:
        tables = {
            row[0] for row in self._db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if "run_identity" in tables:
            self._check_required_tables(tables)
            row = self._db.execute("SELECT 1 FROM run_identity WHERE singleton=1").fetchone()
            if row is None:
                raise ValueError("existing journal is missing run identity")
            self._identity()
            return
        if tables:
            raise ValueError("unrecognized existing reading journal schema")

    @staticmethod
    def _check_required_tables(tables: set[str]) -> None:
        required = {"run_identity", "tasks", "attempts", "stop_reports"}
        if not required <= tables:
            raise ValueError(
                "incomplete reading journal schema; refusing implicit table recreation"
            )

    def _schema(self) -> None:
        self._db.executescript(
            """CREATE TABLE IF NOT EXISTS run_identity (
                 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                 config_json TEXT NOT NULL, config_sha256 TEXT NOT NULL,
                 task_manifest_json TEXT NOT NULL
               );
               CREATE TABLE IF NOT EXISTS tasks (
                 task_id TEXT PRIMARY KEY, ordinal INTEGER NOT NULL UNIQUE,
                 task_json TEXT NOT NULL, task_sha256 TEXT NOT NULL,
                 status TEXT NOT NULL CHECK(status IN (
                   'pending','inflight','valid','invalid','failed','timeout'
                 ))
               );
               CREATE TABLE IF NOT EXISTS attempts (
                 attempt_id TEXT PRIMARY KEY,
                 task_id TEXT NOT NULL UNIQUE REFERENCES tasks(task_id),
                 status TEXT NOT NULL, request_json TEXT NOT NULL,
                 raw_reply TEXT, usage_json TEXT, detail TEXT,
                 started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                 elapsed_seconds REAL,
                 finished_at TEXT
               );
               CREATE TABLE IF NOT EXISTS stop_reports (
                 report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                 report_json TEXT NOT NULL,
                 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
               );"""
        )
        columns = {row["name"] for row in self._db.execute("PRAGMA table_info(attempts)")}
        if "elapsed_seconds" not in columns:
            self._db.execute("ALTER TABLE attempts ADD COLUMN elapsed_seconds REAL")

    @contextmanager
    def _write_transaction(self) -> Generator[None]:
        self._db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self._db.rollback()
            raise
        else:
            self._db.commit()

    def _identity(self) -> None:
        config_json = _json(self.config)
        manifest = _json([{"task_id": t["task_id"], "sha256": _hash(t)} for t in self.tasks])
        row = self._db.execute("SELECT * FROM run_identity WHERE singleton=1").fetchone()
        if row:
            if (row["config_json"], row["config_sha256"], row["task_manifest_json"]) != (
                config_json,
                _hash(self.config),
                manifest,
            ):
                raise ValueError("run store identity does not match config and tasks")
            return
        with self._write_transaction():
            self._db.execute(
                "INSERT INTO run_identity VALUES (1, ?, ?, ?)",
                (config_json, _hash(self.config), manifest),
            )
            self._db.executemany(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, 'pending')",
                [(t["task_id"], i, _json(t), _hash(t)) for i, t in enumerate(self.tasks)],
            )

    def claim(self, task_id: str, request: dict) -> str:
        """Atomically claim one pending task, committing its exact request first."""
        attempt_id = str(uuid.uuid4())
        with self._write_transaction():
            if self._db.execute("SELECT 1 FROM attempts WHERE status='inflight'").fetchone():
                raise ValueError("an attempt is unresolved; reconcile before dispatch")
            self._check_request_identity(task_id, request)
            cur = self._db.execute(
                "UPDATE tasks SET status='inflight' WHERE task_id=? AND status='pending'",
                (task_id,),
            )
            if cur.rowcount != 1:
                raise ValueError("task is unknown or already claimed/terminal")
            self._db.execute(
                "INSERT INTO attempts "
                "(attempt_id,task_id,status,request_json) VALUES(?,?, 'inflight', ?)",
                (attempt_id, task_id, _json(request)),
            )
            return attempt_id

    def _check_request_identity(self, task_id: str, request: dict) -> None:
        row = self._db.execute("SELECT task_json FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise ValueError("task is unknown")
        expected = json.loads(row["task_json"]).get("request_sha256")
        if expected is not None and expected != _hash(request):
            raise ValueError("request does not match frozen task request_sha256")

    def record_reply(self, attempt_id: str, raw_reply: str, usage: dict | None) -> None:
        """Commit the provider's raw reply and usage before caller-side parsing."""
        usage_json = _json(usage) if usage is not None else None
        with self._write_transaction():
            row = self._db.execute(
                "SELECT raw_reply, usage_json FROM attempts "
                "WHERE attempt_id=? AND status='inflight'",
                (attempt_id,),
            ).fetchone()
            if row is None:
                raise ValueError("attempt is unknown or no longer inflight")
            if row["raw_reply"] is not None:
                if (row["raw_reply"], row["usage_json"]) != (raw_reply, usage_json):
                    raise ValueError("raw reply and usage are immutable once recorded")
                return
            self._db.execute(
                "UPDATE attempts SET raw_reply=?, usage_json=? WHERE attempt_id=?",
                (raw_reply, usage_json, attempt_id),
            )

    def record_elapsed(self, attempt_id: str, elapsed_seconds: float) -> None:
        """Durably save measured attempt time before terminal validation."""
        if elapsed_seconds < 0:
            raise ValueError("elapsed seconds cannot be negative")
        self._update_inflight(
            "UPDATE attempts SET elapsed_seconds=? WHERE attempt_id=? AND status='inflight'",
            (elapsed_seconds, attempt_id),
        )

    def record_transport_error(self, attempt_id: str, error: str, elapsed_seconds: float) -> None:
        """Record an ambiguous transport outcome while keeping the attempt inflight."""
        if elapsed_seconds < 0:
            raise ValueError("elapsed seconds cannot be negative")
        detail = _json({"transport_error": error, "usage": None})
        self._update_inflight(
            "UPDATE attempts SET detail=?, elapsed_seconds=? "
            "WHERE attempt_id=? AND status='inflight'",
            (detail, elapsed_seconds, attempt_id),
        )

    def timing_summary(self) -> dict:
        """Return durable elapsed-time and call totals grouped by model."""
        rows = self._db.execute(
            "SELECT request_json, elapsed_seconds FROM attempts ORDER BY started_at"
        )
        return _collect_timing(rows)

    def record_stop_report(self, stop_file: str, pending_tasks: int) -> None:
        report = _json(
            {"reason": "stop_file_present", "stop_file": stop_file, "pending_tasks": pending_tasks}
        )
        with self._write_transaction():
            self._db.execute("INSERT INTO stop_reports (report_json) VALUES (?)", (report,))

    def stop_reports(self) -> list[dict]:
        return [
            json.loads(row["report_json"])
            for row in self._db.execute("SELECT report_json FROM stop_reports ORDER BY report_id")
        ]

    @staticmethod
    def _timing_values(row: sqlite3.Row) -> tuple[str | None, float | None]:
        request = json.loads(row["request_json"])
        return request.get("model"), row["elapsed_seconds"]

    def complete(
        self, attempt_id: str, status: Literal["valid", "invalid"], detail: str | None = None
    ) -> None:
        if status not in {"valid", "invalid"}:
            raise ValueError("completion status must be valid or invalid")
        self._terminal(attempt_id, status, detail, require_reply=True)

    def fail(self, attempt_id: str, status: Literal["failed", "timeout"], detail: str) -> None:
        if status not in {"failed", "timeout"}:
            raise ValueError("failure status must be failed or timeout")
        self._terminal(attempt_id, status, detail)

    def reconcile(self, attempt_id: str, status: Literal["failed", "timeout"], detail: str) -> None:
        """Explicitly resolve an abandoned attempt; never retries or infers outcome."""
        if status not in {"failed", "timeout"}:
            raise ValueError("reconciliation status must be failed or timeout")
        self._terminal(attempt_id, status, detail)

    def _terminal(
        self, attempt_id: str, status: str, detail: str | None, require_reply: bool = False
    ) -> None:
        if status not in _TERMINAL:
            raise ValueError("terminal status is invalid")
        with self._write_transaction():
            row = self._db.execute(
                "SELECT task_id, raw_reply FROM attempts WHERE attempt_id=? AND status='inflight'",
                (attempt_id,),
            ).fetchone()
            if row is None:
                raise ValueError("attempt is unknown or no longer inflight")
            if require_reply and row["raw_reply"] is None:
                raise ValueError("cannot complete before raw reply is recorded")
            self._db.execute(
                "UPDATE attempts SET status=?, detail=?, "
                "finished_at=CURRENT_TIMESTAMP "
                "WHERE attempt_id=?",
                (status, detail, attempt_id),
            )
            self._db.execute("UPDATE tasks SET status=? WHERE task_id=?", (status, row["task_id"]))

    def _update_inflight(self, sql: str, values: tuple) -> None:
        with self._db:
            cur = self._db.execute(sql, values)
            if cur.rowcount != 1:
                raise ValueError("attempt is unknown or no longer inflight")

    def next_pending(self) -> dict | None:
        row = self._db.execute(
            "SELECT task_json FROM tasks WHERE status='pending' ORDER BY ordinal LIMIT 1"
        ).fetchone()
        return json.loads(row["task_json"]) if row else None

    def attempt(self, attempt_id: str) -> dict:
        row = self._db.execute(
            "SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
        if row is None:
            raise ValueError("unknown attempt")
        return {
            "attempt_id": row["attempt_id"],
            "task_id": row["task_id"],
            "status": row["status"],
            "request": json.loads(row["request_json"]),
            "raw_reply": row["raw_reply"],
            "usage": json.loads(row["usage_json"]) if row["usage_json"] else None,
            "detail": row["detail"],
        }

    def summary(self) -> dict[str, int]:
        counts = {status: 0 for status in ("pending", "inflight", *_TERMINAL)}
        for row in self._db.execute("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"):
            counts[row["status"]] = row["n"]
        return counts

    def close(self) -> None:
        self._db.close()
