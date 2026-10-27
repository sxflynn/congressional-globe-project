"""Durable SQLite store for bounded role-run tasks and attempts.

The store owns identity and checkpoints, not worker liveness. Callers must use
``mark_interrupted`` only after independently establishing that a worker is idle.
Schema v3 stores config, packets, caller requests and raw-response/result hashes.
Legacy journals are rejected without migration or writes.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

_STATUSES = {"pending", "inflight", "valid", "invalid", "error", "unresolved"}
_TERMINAL = {"valid", "invalid", "error", "unresolved"}


class _Packet(BaseModel):
    model_config = ConfigDict(extra="allow")
    window_id: str


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


class RoleRunStore:
    """Persist an immutable run identity plus ordered tasks and call attempts."""

    def __init__(self, path: Path, config: dict, packets: list[dict]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.config = config
        parsed = [_Packet.model_validate(packet) for packet in packets]
        ids = [packet.window_id for packet in parsed]
        if len(ids) != len(set(ids)):
            raise ValueError("packet window_id values must be unique")
        self.packets = packets
        self._db = sqlite3.connect(self.path, timeout=30)
        self._db.row_factory = sqlite3.Row
        try:
            self._initialize()
        except BaseException:
            self._db.close()
            raise

    def _initialize(self) -> None:
        config_json = _json(self.config)
        manifest = [{"window_id": p["window_id"], "sha256": _digest(p)} for p in self.packets]
        manifest_json = _json(manifest)
        tables = {
            r[0] for r in self._db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if tables:
            self._verify_existing(tables, config_json, manifest_json)
            return
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._create_schema()
        self._insert_run(config_json, manifest_json)

    def _verify_existing(self, tables: set[str], config_json: str, manifest_json: str) -> None:
        if not {"run_identity", "tasks", "attempts", "attempt_checkpoints"} <= tables:
            raise ValueError("incomplete or legacy role journal schema; no implicit migration")
        existing = self._db.execute("SELECT * FROM run_identity WHERE singleton=1").fetchone()
        if existing is None:
            raise ValueError("role journal identity is missing")
        self._verify_identity(existing, config_json, manifest_json)
        if self._db.execute("PRAGMA user_version").fetchone()[0] != 3:
            raise ValueError("unsupported role journal schema version")
        missing = self._db.execute(
            "SELECT 1 FROM attempts a LEFT JOIN attempt_checkpoints c USING(attempt_id) "
            "WHERE c.attempt_id IS NULL"
        ).fetchone()
        if missing:
            raise ValueError("role journal is missing attempt checkpoints")
        self.budget_summary()
        self.results()

    def _create_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS run_identity (
              singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
              config_json TEXT NOT NULL, config_sha256 TEXT NOT NULL,
              packet_manifest_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
              window_id TEXT PRIMARY KEY, ordinal INTEGER NOT NULL UNIQUE,
              packet_json TEXT NOT NULL, packet_sha256 TEXT NOT NULL,
              status TEXT NOT NULL CHECK (status IN
                ('pending','inflight','valid','invalid','error','unresolved'))
            );
            CREATE TABLE IF NOT EXISTS attempts (
              attempt_id TEXT PRIMARY KEY, window_id TEXT NOT NULL REFERENCES tasks(window_id),
              status TEXT NOT NULL, result_json TEXT, result_sha256 TEXT,
              started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS attempt_checkpoints (
              attempt_id TEXT PRIMARY KEY REFERENCES attempts(attempt_id),
              request_json TEXT NOT NULL, request_sha256 TEXT NOT NULL,
              response_json TEXT, response_sha256 TEXT, elapsed_seconds REAL
            );
            PRAGMA user_version=3;
            """
        )

    def _verify_identity(self, existing: sqlite3.Row, config_json: str, manifest_json: str) -> None:
        if (
            existing["config_json"] != config_json
            or existing["config_sha256"] != _digest(self.config)
            or existing["packet_manifest_json"] != manifest_json
        ):
            raise ValueError("run store identity does not match config and packets")

    def _insert_run(self, config_json: str, manifest_json: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO run_identity VALUES (1, ?, ?, ?)",
                (config_json, _digest(self.config), manifest_json),
            )
            self._db.executemany(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, 'pending')",
                [(p["window_id"], i, _json(p), _digest(p)) for i, p in enumerate(self.packets)],
            )

    def next_pending(self) -> dict | None:
        row = self._db.execute(
            "SELECT packet_json FROM tasks WHERE status='pending' ORDER BY ordinal LIMIT 1"
        ).fetchone()
        return json.loads(row["packet_json"]) if row else None

    def packet(self, window_id: str) -> dict:
        row = self._db.execute(
            "SELECT packet_json FROM tasks WHERE window_id=?", (window_id,)
        ).fetchone()
        if row is None:
            raise ValueError("unknown task")
        return json.loads(row["packet_json"])

    def inflight_id(self, window_id: str) -> str:
        row = self._db.execute(
            "SELECT attempt_id FROM attempts WHERE window_id=? AND status='inflight'",
            (window_id,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown inflight attempt")
        return row["attempt_id"]

    def start(self, window_id: str, request: dict | None = None) -> str:
        attempt_id = str(uuid.uuid4())
        with self._db:
            row = self._db.execute(
                "SELECT status, packet_json, packet_sha256 FROM tasks WHERE window_id=?",
                (window_id,),
            ).fetchone()
            if row is None or row["status"] != "pending":
                raise ValueError("task is unknown or not pending")
            self._check_start(row, window_id, request)
            self._db.execute("UPDATE tasks SET status='inflight' WHERE window_id=?", (window_id,))
            self._db.execute(
                "INSERT INTO attempts (attempt_id, window_id, status) VALUES (?, ?, 'inflight')",
                (attempt_id, window_id),
            )
            self._db.execute(
                "INSERT INTO attempt_checkpoints(attempt_id, request_json, request_sha256) "
                "VALUES(?, ?, ?)",
                self._request_checkpoint(attempt_id, request, row),
            )
        return attempt_id

    @staticmethod
    def _request_checkpoint(attempt_id: str, request: dict | None, row: sqlite3.Row) -> tuple:
        value = request or {"packet": json.loads(row["packet_json"])}
        return attempt_id, _json(value), _digest(value)

    def _check_start(self, row: sqlite3.Row, window_id: str, request: dict | None) -> None:
        if self._db.execute(
            "SELECT 1 FROM attempts WHERE status IN ('inflight','unresolved')"
        ).fetchone():
            raise ValueError("an attempt is unresolved; no new dispatch")
        if _digest(json.loads(row["packet_json"])) != row["packet_sha256"]:
            raise ValueError("stored packet identity mismatch")
        expected = self.config.get("request_hashes", {}).get(window_id)
        if expected is not None and _digest(request) != expected:
            raise ValueError("request identity does not match frozen configuration")

    def record_response(self, attempt_id: str, response: dict, elapsed_seconds: float) -> None:
        if not math.isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("elapsed seconds must be finite and nonnegative")
        serialized = _json(response)
        with self._db:
            row = self._response_checkpoint(attempt_id)
            if row["response_json"] is not None:
                if (row["response_json"], row["elapsed_seconds"]) != (serialized, elapsed_seconds):
                    raise ValueError("saved response and usage/time are immutable")
                return
            self._db.execute(
                "UPDATE attempt_checkpoints SET response_json=?, response_sha256=?, "
                "elapsed_seconds=? WHERE attempt_id=?",
                (serialized, _digest(response), elapsed_seconds, attempt_id),
            )

    def _response_checkpoint(self, attempt_id: str) -> sqlite3.Row:
        row = self._db.execute(
            "SELECT c.*,a.window_id FROM attempt_checkpoints c JOIN attempts a USING(attempt_id) "
            "WHERE attempt_id=? AND a.status='inflight'",
            (attempt_id,),
        ).fetchone()
        if row is None:
            raise ValueError("attempt is unknown or no longer inflight")
        self._verify_checkpoint(dict(row))
        return row

    def _verify_checkpoint(self, row: dict) -> None:
        if _text_hash(row["request_json"]) != row["request_sha256"]:
            raise ValueError("saved request hash mismatch")
        expected = self.config.get("request_hashes", {}).get(row["window_id"])
        if expected is not None and expected != row["request_sha256"]:
            raise ValueError("saved request configuration mismatch")
        _verify_response_hash(row)
        _verify_elapsed(row)

    def saved_responses(self) -> list[dict]:
        rows = self._db.execute(
            "SELECT a.attempt_id,a.window_id,c.* "
            "FROM attempts a JOIN attempt_checkpoints c USING(attempt_id) "
            "WHERE a.status='inflight' AND c.response_json IS NOT NULL ORDER BY a.rowid"
        )
        return [self._saved_response(dict(row)) for row in rows]

    def _saved_response(self, row: dict) -> dict:
        self._verify_checkpoint(row)
        return {**row, "response": json.loads(row["response_json"])}

    def budget_summary(self) -> dict:
        rows = [
            dict(row)
            for row in self._db.execute(
                "SELECT a.window_id,c.* FROM attempt_checkpoints c "
                "JOIN attempts a USING(attempt_id)"
            )
        ]
        for row in rows:
            self._verify_checkpoint(row)
        return _budget_totals(rows, self.config.get("max_output_tokens"))

    def finish(self, attempt_id: str, result: dict, status: str) -> None:
        if status not in _TERMINAL:
            raise ValueError("finish status must be terminal")
        result_json = _json(result)
        with self._db:
            attempt = self._db.execute(
                "SELECT window_id, status FROM attempts WHERE attempt_id=?", (attempt_id,)
            ).fetchone()
            if attempt is None or attempt["status"] != "inflight":
                raise ValueError("attempt is unknown or no longer inflight")
            task = self._db.execute(
                "SELECT status FROM tasks WHERE window_id=?", (attempt["window_id"],)
            ).fetchone()
            if task is None or task["status"] != "inflight":
                raise ValueError("task is no longer inflight")
            self._check_saved_result(attempt_id, result)
            self._db.execute(
                "UPDATE attempts SET status=?, result_json=?, result_sha256=?, "
                "finished_at=CURRENT_TIMESTAMP "
                "WHERE attempt_id=?",
                (status, result_json, _digest(result), attempt_id),
            )
            self._db.execute(
                "UPDATE tasks SET status=? WHERE window_id=?", (status, attempt["window_id"])
            )

    def _check_saved_result(self, attempt_id: str, result: dict) -> None:
        row = self._response_checkpoint(attempt_id)
        if row["response_json"] is None:
            return
        response = json.loads(row["response_json"])
        if any(result.get(key) != value for key, value in response.items()):
            raise ValueError("terminal result cannot replace saved raw response or usage")

    def mark_interrupted(self) -> int:
        """Mark outstanding calls unresolved after the caller proves the worker idle."""
        with self._db:
            if self.saved_responses():
                raise ValueError(
                    "saved response must be validated; cannot discard it as interrupted"
                )
            rows = self._db.execute(
                "SELECT attempt_id, window_id FROM attempts WHERE status='inflight'"
            ).fetchall()
            for row in rows:
                self._db.execute(
                    "UPDATE attempts SET status='unresolved', result_json=?, result_sha256=?, "
                    "finished_at=CURRENT_TIMESTAMP WHERE attempt_id=?",
                    (
                        _json({"error": "interrupted; outcome unknown"}),
                        _digest({"error": "interrupted; outcome unknown"}),
                        row["attempt_id"],
                    ),
                )
                self._db.execute(
                    "UPDATE tasks SET status='unresolved' WHERE window_id=?", (row["window_id"],)
                )
        return len(rows)

    def summary(self) -> dict:
        counts = {status: 0 for status in _STATUSES}
        for row in self._db.execute("SELECT status, COUNT(*) AS count FROM tasks GROUP BY status"):
            counts[row["status"]] = row["count"]
        attempts = self._db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        return {"statuses": counts, "attempts": attempts}

    def results(self) -> list[dict]:
        rows = self._db.execute(
            "SELECT a.window_id,a.status,a.result_json,a.result_sha256,c.response_json "
            "FROM attempts a JOIN attempt_checkpoints c USING(attempt_id) "
            "WHERE a.status IN ('valid','invalid','error','unresolved') "
            "ORDER BY a.started_at,a.rowid"
        ).fetchall()
        return [_checked_result(dict(row)) for row in rows]

    def close(self) -> None:
        self._db.close()


def _token_count(value: Any) -> int | None:
    if type(value) is int and value >= 0:
        return value
    return None


def _checked_result(row: dict) -> dict:
    if _text_hash(row["result_json"]) != row["result_sha256"]:
        raise ValueError("terminal result hash mismatch")
    result = json.loads(row["result_json"])
    _verify_result_response(result, row["response_json"])
    return {"window_id": row["window_id"], "status": row["status"], "result": result}


def _verify_result_response(result: dict, serialized: str | None) -> None:
    if serialized is None:
        return
    if any(result.get(key) != value for key, value in json.loads(serialized).items()):
        raise ValueError("terminal result differs from saved raw response or usage")


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _verify_response_hash(row: dict) -> None:
    if (
        row["response_json"] is not None
        and _text_hash(row["response_json"]) != row["response_sha256"]
    ):
        raise ValueError("saved response hash mismatch")


def _verify_elapsed(row: dict) -> None:
    elapsed = row["elapsed_seconds"]
    if elapsed is not None and (not math.isfinite(elapsed) or elapsed < 0):
        raise ValueError("saved elapsed time is invalid")


def _usage_values(row: dict) -> tuple[int | None, int | None]:
    response = json.loads(row["response_json"]) if row["response_json"] else {}
    usage = response.get("usage") or {}
    if not isinstance(usage, dict):
        return None, None
    if not _valid_cached(usage):
        return None, None
    return _token_count(usage.get("input_tokens")), _token_count(usage.get("output_tokens"))


def _valid_cached(usage: dict) -> bool:
    cached = _token_count(usage.get("cached_input_tokens") or 0)
    incoming = _token_count(usage.get("input_tokens"))
    if incoming is None or cached is None:
        return False
    return cached <= incoming


def _budget_totals(rows: list[dict], output_limit: int | None) -> dict:
    result = {
        "calls": len(rows),
        "seconds": 0.0,
        "unknown_elapsed": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "unknown_usage": 0,
        "output_limit_exceeded": False,
    }
    for row in rows:
        _add_budget_row(result, row)
        _, outgoing = _usage_values(row)
        if outgoing is not None and output_limit is not None:
            result["output_limit_exceeded"] |= outgoing > output_limit
    return result


def _add_budget_row(result: dict, row: dict) -> None:
    elapsed = row["elapsed_seconds"]
    if elapsed is None:
        result["unknown_elapsed"] += 1
    else:
        result["seconds"] += elapsed
    incoming, outgoing = _usage_values(row)
    if incoming is None or outgoing is None:
        result["unknown_usage"] += 1
        return
    result["input_tokens"] += incoming
    result["output_tokens"] += outgoing
