"""Durable SQLite storage for immutable review packets and human responses."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from congressional_globe.review_models import ReviewPacket, ReviewSubmission


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ReviewStore:
    """SQLite-backed packet registry, drafts, submissions, and apply receipts."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS packets (
                    packet_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    packet_json TEXT NOT NULL,
                    packet_sha256 TEXT NOT NULL,
                    PRIMARY KEY (packet_id, version)
                );
                CREATE TABLE IF NOT EXISTS drafts (
                    packet_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    reviewer TEXT NOT NULL,
                    answers_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (packet_id, version, reviewer)
                );
                CREATE TABLE IF NOT EXISTS submissions (
                    submission_id TEXT PRIMARY KEY,
                    packet_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    packet_sha256 TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    answers_json TEXT NOT NULL,
                    notes TEXT,
                    payload_sha256 TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (packet_id, version, reviewer, revision)
                );
                CREATE TABLE IF NOT EXISTS applied_receipts (
                    submission_id TEXT PRIMARY KEY REFERENCES submissions(submission_id),
                    reference TEXT NOT NULL,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _latest(self, connection: sqlite3.Connection, packet_id: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM packets WHERE packet_id = ? ORDER BY version DESC LIMIT 1",
            (packet_id,),
        ).fetchone()

    def _packet_row(
        self, connection: sqlite3.Connection, packet_id: str, version: int | None
    ) -> sqlite3.Row:
        row = (
            self._latest(connection, packet_id)
            if version is None
            else connection.execute(
                "SELECT * FROM packets WHERE packet_id = ? AND version = ?",
                (packet_id, version),
            ).fetchone()
        )
        if row is None:
            raise KeyError(f"unknown review packet {packet_id!r} version {version!r}")
        latest = self._latest(connection, packet_id)
        if latest is None or row["version"] != latest["version"]:
            raise ValueError("review packet version is stale")
        return row

    def _validate_answers(
        self, packet_json: str, answers: dict[str, str], *, complete: bool
    ) -> dict[str, str]:
        packet = ReviewPacket.model_validate_json(packet_json)
        questions = {question.id: question for question in packet.questions}
        self._check_known_questions(questions, answers)
        self._check_answer_values(questions, answers)
        missing = self._missing_required(packet, answers) if complete else []
        if missing:
            raise ValueError(f"required answers are missing: {missing}")
        return answers

    def _check_known_questions(self, questions: dict[str, Any], answers: dict[str, str]) -> None:
        unknown = set(answers) - set(questions)
        if unknown:
            raise ValueError(f"answers contain unknown question IDs: {sorted(unknown)}")

    def _check_answer_values(self, questions: dict[str, Any], answers: dict[str, str]) -> None:
        for key, answer in answers.items():
            if questions[key].options and answer and answer not in questions[key].options:
                raise ValueError(f"answer for {key!r} must match a listed option")

    def _missing_required(self, packet: ReviewPacket, answers: dict[str, str]) -> list[str]:
        return [
            question.id
            for question in packet.questions
            if question.required and not answers.get(question.id, "").strip()
        ]

    def register(self, packet: ReviewPacket | dict[str, Any]) -> dict[str, Any]:
        parsed = ReviewPacket.model_validate(packet)
        packet_json = _canonical(parsed.model_dump(mode="json"))
        packet_hash = _digest(packet_json)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT packet_sha256 FROM packets WHERE packet_id = ? AND version = ?",
                (parsed.id, parsed.version),
            ).fetchone()
            if existing and existing["packet_sha256"] != packet_hash:
                raise ValueError("packet ID/version is already registered with different content")
            connection.execute(
                "INSERT OR IGNORE INTO packets VALUES (?, ?, ?, ?)",
                (parsed.id, parsed.version, packet_json, packet_hash),
            )
        return {**parsed.model_dump(mode="json"), "packet_sha256": packet_hash}

    def packets(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT p.* FROM packets p JOIN "
                "(SELECT packet_id, MAX(version) version FROM packets GROUP BY packet_id) latest "
                "ON latest.packet_id = p.packet_id AND latest.version = p.version "
                "ORDER BY p.packet_id"
            ).fetchall()
        return [self._packet_dict(row) for row in rows]

    def _packet_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {**json.loads(row["packet_json"]), "packet_sha256": row["packet_sha256"]}

    def get_packet(self, packet_id: str, version: int | None = None) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = (
                self._latest(connection, packet_id)
                if version is None
                else connection.execute(
                    "SELECT * FROM packets WHERE packet_id = ? AND version = ?",
                    (packet_id, version),
                ).fetchone()
            )
            return None if row is None else self._packet_dict(row)

    def save_draft(
        self, packet_id: str, version: int, reviewer: str, answers: dict[str, str]
    ) -> dict[str, Any]:
        submission = ReviewSubmission(reviewer=reviewer, answers=answers)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            packet = self._packet_row(connection, packet_id, version)
            checked = self._validate_answers(
                packet["packet_json"], submission.answers, complete=False
            )
            answers_json = _canonical(checked)
            connection.execute(
                "INSERT INTO drafts(packet_id, version, reviewer, answers_json) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(packet_id, version, reviewer) DO UPDATE SET "
                "answers_json = excluded.answers_json, updated_at = CURRENT_TIMESTAMP",
                (packet_id, version, submission.reviewer, answers_json),
            )
            row = connection.execute(
                "SELECT * FROM drafts WHERE packet_id = ? AND version = ? AND reviewer = ?",
                (packet_id, version, submission.reviewer),
            ).fetchone()
        return self._draft_dict(row)

    def get_draft(self, packet_id: str, version: int, reviewer: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            self._packet_row(connection, packet_id, version)
            row = connection.execute(
                "SELECT * FROM drafts WHERE packet_id = ? AND version = ? AND reviewer = ?",
                (packet_id, version, reviewer.strip()),
            ).fetchone()
        return None if row is None else self._draft_dict(row)

    def _draft_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "packet_id": row["packet_id"],
            "version": row["version"],
            "reviewer": row["reviewer"],
            "answers": json.loads(row["answers_json"]),
            "updated_at": row["updated_at"],
        }

    def submit(
        self,
        packet_id: str,
        version: int,
        reviewer: str,
        answers: dict[str, str],
        notes: str | None = None,
    ) -> dict[str, Any]:
        data = ReviewSubmission(reviewer=reviewer, answers=answers, notes=notes)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            packet = self._packet_row(connection, packet_id, version)
            checked = self._validate_answers(packet["packet_json"], data.answers, complete=True)
            answers_json = _canonical(checked)
            payload_hash = _digest(_canonical({"answers": checked, "notes": data.notes}))
            duplicate = connection.execute(
                "SELECT * FROM submissions WHERE packet_id = ? AND version = ? "
                "AND reviewer = ? ORDER BY revision DESC LIMIT 1",
                (packet_id, version, data.reviewer),
            ).fetchone()
            if duplicate and duplicate["payload_sha256"] == payload_hash:
                self._delete_draft(connection, packet_id, version, data.reviewer)
                return self._submission_dict(connection, duplicate)
            previous = connection.execute(
                "SELECT MAX(revision) revision FROM submissions "
                "WHERE packet_id = ? AND version = ? AND reviewer = ?",
                (packet_id, version, data.reviewer),
            ).fetchone()
            revision = (previous["revision"] or 0) + 1
            submission_id = str(uuid4())
            connection.execute(
                "INSERT INTO submissions(submission_id, packet_id, version, packet_sha256, "
                "reviewer, answers_json, notes, payload_sha256, revision) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    submission_id,
                    packet_id,
                    version,
                    packet["packet_sha256"],
                    data.reviewer,
                    answers_json,
                    data.notes,
                    payload_hash,
                    revision,
                ),
            )
            row = connection.execute(
                "SELECT * FROM submissions WHERE submission_id = ?", (submission_id,)
            ).fetchone()
            self._delete_draft(connection, packet_id, version, data.reviewer)
            return self._submission_dict(connection, row)

    def _delete_draft(
        self, connection: sqlite3.Connection, packet_id: str, version: int, reviewer: str
    ) -> None:
        connection.execute(
            "DELETE FROM drafts WHERE packet_id = ? AND version = ? AND reviewer = ?",
            (packet_id, version, reviewer),
        )

    def _submission_dict(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        receipt = connection.execute(
            "SELECT reference, applied_at FROM applied_receipts WHERE submission_id = ?",
            (row["submission_id"],),
        ).fetchone()
        latest = connection.execute(
            "SELECT MAX(revision) revision FROM submissions "
            "WHERE packet_id = ? AND version = ? AND reviewer = ?",
            (row["packet_id"], row["version"], row["reviewer"]),
        ).fetchone()
        return {
            "submission_id": row["submission_id"],
            "packet_id": row["packet_id"],
            "version": row["version"],
            "packet_sha256": row["packet_sha256"],
            "reviewer": row["reviewer"],
            "answers": json.loads(row["answers_json"]),
            "notes": row["notes"],
            "payload_sha256": row["payload_sha256"],
            "revision": row["revision"],
            "superseded": row["revision"] < latest["revision"],
            "created_at": row["created_at"],
            "applied": receipt is not None,
            "applied_reference": None if receipt is None else receipt["reference"],
            "applied_at": None if receipt is None else receipt["applied_at"],
        }

    def submissions(self, pending_only: bool = False) -> list[dict[str, Any]]:
        clause = (
            "WHERE r.submission_id IS NULL AND s.revision = "
            "(SELECT MAX(newer.revision) FROM submissions newer "
            "WHERE newer.packet_id = s.packet_id AND newer.version = s.version "
            "AND newer.reviewer = s.reviewer)"
            if pending_only
            else ""
        )
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT s.* FROM submissions s LEFT JOIN applied_receipts r "
                f"ON r.submission_id = s.submission_id {clause} "
                "ORDER BY s.packet_id, s.reviewer, s.revision"
            ).fetchall()
            return [self._submission_dict(connection, row) for row in rows]

    def mark_applied(self, submission_id: str, reference: str) -> dict[str, Any]:
        clean_reference = reference.strip()
        if not clean_reference:
            raise ValueError("applied reference must not be blank")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM submissions WHERE submission_id = ?", (submission_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown submission {submission_id!r}")
            latest = connection.execute(
                "SELECT MAX(revision) revision FROM submissions "
                "WHERE packet_id = ? AND version = ? AND reviewer = ?",
                (row["packet_id"], row["version"], row["reviewer"]),
            ).fetchone()
            if row["revision"] < latest["revision"]:
                raise ValueError("superseded submission cannot be applied")
            receipt = connection.execute(
                "SELECT reference FROM applied_receipts WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
            if receipt and receipt["reference"] != clean_reference:
                raise ValueError("submission already has a different applied receipt")
            connection.execute(
                "INSERT OR IGNORE INTO applied_receipts(submission_id, reference) VALUES (?, ?)",
                (submission_id, clean_reference),
            )
            return self._submission_dict(connection, row)

    def export(self, submission_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM submissions WHERE submission_id = ?", (submission_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown submission {submission_id!r}")
            packet = connection.execute(
                "SELECT packet_json, packet_sha256 FROM packets "
                "WHERE packet_id = ? AND version = ?",
                (row["packet_id"], row["version"]),
            ).fetchone()
            receipt = connection.execute(
                "SELECT reference, applied_at FROM applied_receipts WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
            submission = self._submission_dict(connection, row)
            return {
                "packet_snapshot": {
                    "packet_json": packet["packet_json"],
                    "packet_sha256": packet["packet_sha256"],
                },
                "packet": json.loads(packet["packet_json"]),
                "submission": submission,
                "applied_receipt": None
                if receipt is None
                else {"reference": receipt["reference"], "applied_at": receipt["applied_at"]},
            }
