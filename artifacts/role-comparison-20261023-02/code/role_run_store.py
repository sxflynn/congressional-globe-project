"""Durable SQLite store for bounded role-run tasks and attempts.

The store owns identity and checkpoints, not worker liveness. Callers must use
``mark_interrupted`` only after independently establishing that a worker is idle.
Schema v1 stores canonical config/packet JSON and SHA-256 identities in SQLite.
"""

from __future__ import annotations

import hashlib
import json
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
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._initialize()

    def _initialize(self) -> None:
        self._create_schema()
        config_json = _json(self.config)
        manifest = [{"window_id": p["window_id"], "sha256": _digest(p)} for p in self.packets]
        manifest_json = _json(manifest)
        existing = self._db.execute("SELECT * FROM run_identity WHERE singleton=1").fetchone()
        if existing:
            self._verify_identity(existing, config_json, manifest_json)
            return
        self._insert_run(config_json, manifest_json)

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
              status TEXT NOT NULL, result_json TEXT,
              started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              finished_at TEXT
            );
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

    def start(self, window_id: str) -> str:
        attempt_id = str(uuid.uuid4())
        with self._db:
            row = self._db.execute(
                "SELECT status FROM tasks WHERE window_id=?", (window_id,)
            ).fetchone()
            if row is None or row["status"] != "pending":
                raise ValueError("task is unknown or not pending")
            self._db.execute("UPDATE tasks SET status='inflight' WHERE window_id=?", (window_id,))
            self._db.execute(
                "INSERT INTO attempts (attempt_id, window_id, status) VALUES (?, ?, 'inflight')",
                (attempt_id, window_id),
            )
        return attempt_id

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
            self._db.execute(
                "UPDATE attempts SET status=?, result_json=?, finished_at=CURRENT_TIMESTAMP "
                "WHERE attempt_id=?",
                (status, result_json, attempt_id),
            )
            self._db.execute(
                "UPDATE tasks SET status=? WHERE window_id=?", (status, attempt["window_id"])
            )

    def mark_interrupted(self) -> int:
        """Mark outstanding calls unresolved after the caller proves the worker idle."""
        with self._db:
            rows = self._db.execute(
                "SELECT attempt_id, window_id FROM attempts WHERE status='inflight'"
            ).fetchall()
            for row in rows:
                self._db.execute(
                    "UPDATE attempts SET status='unresolved', result_json=?, "
                    "finished_at=CURRENT_TIMESTAMP WHERE attempt_id=?",
                    (_json({"error": "interrupted; outcome unknown"}), row["attempt_id"]),
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
            "SELECT window_id, status, result_json FROM attempts "
            "WHERE status IN ('valid','invalid','error','unresolved') ORDER BY started_at, rowid"
        ).fetchall()
        return [
            {
                "window_id": row["window_id"],
                "status": row["status"],
                "result": json.loads(row["result_json"]),
            }
            for row in rows
        ]

    def close(self) -> None:
        self._db.close()
