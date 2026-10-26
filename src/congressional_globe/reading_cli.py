"""Bounded, offline journal inspection; unresolved evidence fails verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from congressional_globe.reading_budget_audit import token_usage
from congressional_globe.reading_pickup_audit import inspect_evidence

MAX_OUTPUT_BYTES = 8192
_UNRESOLVED = [
    "cross_run_budget_provenance_and_deduplication",
    "request_source_image_control_count_protocol_review_bindings",
    "runtime_binary_and_counter_helper_separate_hashes",
]


def add_reading_commands(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("reading", help="Read-only reading journal inspection")
    actions = command.add_subparsers(dest="reading_action", required=True)
    for name in ("status", "verify"):
        action = actions.add_parser(name, help=f"Offline journal {name} for an explicit run")
        action.add_argument("--run-dir", type=Path, required=True)
        action.add_argument("--json", action="store_true", dest="json_out")
        action.add_argument(
            "--evidence",
            type=Path,
            help="Explicit hash-bound inspection recipe; never a launch configuration",
        )


def _encode(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _emit(report: dict) -> None:
    payload = _encode(report)
    if len(payload.encode()) + 1 > MAX_OUTPUT_BYTES:
        payload = _encode(
            {"ok": False, "error": "output_limit_exceeded", "max_output_bytes": MAX_OUTPUT_BYTES}
        )
    print(payload)
    if json.loads(payload).get("ok") is False:
        raise SystemExit(1)


def run_reading(arguments: argparse.Namespace, _: Path) -> None:
    actions = {"status": _reading_status, "verify": _reading_verify}
    try:
        evidence = getattr(arguments, "evidence", None)
        report = actions[arguments.reading_action](arguments.run_dir, evidence)
    except (OSError, ValueError, sqlite3.Error, KeyError, TypeError):
        report = {
            "ok": False,
            "error": "journal_inspection_failed",
            "detail": "Journal missing, changed or malformed; inspect explicit run evidence.",
        }
    _emit(report)


def _fingerprints(paths: list[Path]) -> list:
    return [
        (p.exists(), p.stat().st_size, p.stat().st_mtime_ns) if p.exists() else (False, 0, 0)
        for p in paths
    ]


@contextmanager
def _open_readonly_store(run_dir: Path, filename: str = "attempts.sqlite"):
    # Never open the original SQLite: even mode=ro can update/create WAL sidecars.
    source = Path(run_dir) / filename
    if not source.is_file():
        raise FileNotFoundError("missing attempts.sqlite")
    paths = [source, source.with_name(source.name + "-wal")]
    before = _fingerprints(paths)
    with tempfile.TemporaryDirectory(prefix="globe-reading-inspect-") as scratch:
        copied = Path(scratch) / filename
        for path in paths:
            if path.exists():
                shutil.copyfile(path, Path(scratch) / path.name)
        if before != _fingerprints(paths):
            raise ValueError("journal changed during snapshot; retry inspection")
        conn = sqlite3.connect(copied.as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN")
            yield conn
        finally:
            conn.close()


def _hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode()).hexdigest()


def _identity(conn) -> tuple[dict, list, str]:
    row = conn.execute("SELECT * FROM run_identity WHERE singleton=1").fetchone()
    if row is None:
        raise ValueError("missing run identity")
    config = TypeAdapter(dict[str, Any]).validate_json(row["config_json"])
    manifest = TypeAdapter(list[dict[str, str]]).validate_json(row["task_manifest_json"])
    return config, manifest, row["config_sha256"]


def _counts(conn, table: str) -> dict:
    # Table names are internal constants, never caller input.
    return {
        row["status"]: row["n"]
        for row in conn.execute(f"SELECT status, COUNT(*) AS n FROM {table} GROUP BY status")
    }


def _elapsed(value) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("invalid elapsed seconds")
    return number


def _usage_known(value) -> bool:
    if not value:
        return False
    usage = json.loads(value)
    if not isinstance(usage, dict):
        return False
    return all(
        type(usage.get(k)) is int and usage[k] >= 0 for k in ("prompt_eval_count", "eval_count")
    )


def _timing(conn) -> dict:
    summary: dict[str, Any] = {
        "calls": 0,
        "known_input_tokens": 0,
        "known_output_tokens": 0,
        "seconds": 0.0,
        "unknown_elapsed_attempts": 0,
        "unknown_token_usage_attempts": 0,
        "models": {},
    }
    rows = conn.execute("SELECT request_json, elapsed_seconds, usage_json FROM attempts")
    for row in rows:
        request = TypeAdapter(dict[str, Any]).validate_json(row["request_json"])
        elapsed = _elapsed(row["elapsed_seconds"])
        tokens = token_usage(row["usage_json"])
        summary["known_input_tokens"] += tokens["known_input_tokens"]
        summary["known_output_tokens"] += tokens["known_output_tokens"]
        summary["calls"] += 1
        summary["unknown_elapsed_attempts"] += elapsed is None
        summary["unknown_token_usage_attempts"] += not _usage_known(row["usage_json"])
        summary["seconds"] += elapsed or 0
        model = request.get("model") or "unknown"
        bucket = summary["models"].setdefault(model, {"calls": 0, "seconds": 0.0})
        bucket["calls"] += 1
        bucket["seconds"] += elapsed or 0
    return summary


def _plan_state() -> dict:
    path = Path(__file__).resolve().parents[2] / "MASTER_PLAN.md"
    if not path.is_file():
        return {"state": "unavailable", "path": str(path)}
    data = path.read_bytes()
    lines = [line for line in data.decode().splitlines() if line.startswith("**Next default:")]
    return {
        "path": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "next_action": lines[0] if lines else "unknown",
        "ownership": _active_work(data.decode()),
        "plan_file_age_seconds": max(0, datetime.now(UTC).timestamp() - path.stat().st_mtime),
        "checkpoint_age": "unknown_no_machine_timestamp",
    }


def _active_work(text: str) -> list[str]:
    section = text.split("## Active work\n", 1)
    if len(section) != 2:
        return []
    lines = section[1].split("\n## ", 1)[0].splitlines()
    return [line for line in lines if line.startswith("| ")][2:6]


def _review_state(path: str | None) -> dict:
    if path is None:
        return {"state": "unavailable_not_supplied"}
    source = Path(path)
    with _open_readonly_store(source.parent, source.name) as conn:
        pending = conn.execute(
            "SELECT COUNT(*) FROM submissions s LEFT JOIN applied_receipts r "
            "USING(submission_id) WHERE r.submission_id IS NULL AND s.revision = "
            "(SELECT MAX(n.revision) FROM submissions n WHERE n.packet_id=s.packet_id "
            "AND n.version=s.version AND n.reviewer=s.reviewer)"
        ).fetchone()[0]
        unanswered = conn.execute(
            "SELECT COUNT(*) FROM packets p WHERE p.version = "
            "(SELECT MAX(n.version) FROM packets n WHERE n.packet_id=p.packet_id) "
            "AND NOT EXISTS (SELECT 1 FROM submissions s WHERE "
            "s.packet_id=p.packet_id AND s.version=p.version)"
        ).fetchone()[0]
    return {
        "state": "observed_readonly",
        "database": path,
        "pending_unapplied_submissions": pending,
        "packets_without_submission": unanswered,
        "observed_at": datetime.now(UTC).isoformat(),
    }


def _reading_status(run_dir: Path, evidence: Path | None = None) -> dict[str, Any]:
    with _open_readonly_store(run_dir) as conn:
        config, manifest, config_hash = _identity(conn)
        tasks = _counts(conn, "tasks")
        timing = _timing(conn)
        report = {
            "run_dir": str(run_dir),
            "config_sha256": config_hash,
            "observed_at": datetime.now(UTC).isoformat(),
            "task_count": len(manifest),
            "tasks_by_status": tasks,
            "journal_counts": {
                "total_tasks": sum(tasks.values()),
                "tasks_by_status": tasks,
                "attempts_by_status": _counts(conn, "attempts"),
                "attempt_count": timing["calls"],
                "terminal": sum(tasks.get(s, 0) for s in ("valid", "invalid", "failed", "timeout")),
                "pending": tasks.get("pending", 0),
                "inflight": tasks.get("inflight", 0),
            },
            "timing": timing,
            "budget": {
                "current_recorded_seconds": timing["seconds"],
                "current_calls": timing["calls"],
                "configured_limits": {
                    k: config.get(k)
                    for k in ("max_calls", "total_seconds", "per_model_seconds", "call_seconds")
                },
                "prior_usage": "unknown_unverified",
                "remaining_allowance": None,
            },
            "unknown_usage": {
                k: timing[k] for k in ("unknown_elapsed_attempts", "unknown_token_usage_attempts")
            },
            "review/ownership_state": {
                "human_review": "not_queried",
                "ownership": "see_MASTER_PLAN_active_work",
                "stop_report_count": conn.execute("SELECT COUNT(*) FROM stop_reports").fetchone()[
                    0
                ],
            },
            "runtime": {"state": "observation_unknown", "launch_ready": False},
            "next_action": _plan_state(),
            "bounded_output": True,
        }
        if evidence is not None:
            verification = _verify_connection(conn, run_dir, evidence)
            _attach_evidence(report, verification)
        return report


def _attach_evidence(report: dict, verification: dict) -> None:
    report["evidence_verification"] = verification
    extra = verification["evidence"]
    if extra is not None:
        report["review/ownership_state"]["human_review"] = extra["current_review"]
        report["budget"]["prior_usage"] = (
            "recomputed_see_evidence_verification"
            if extra["budget"] is not None
            else "unknown_evidence_failed"
        )


def _check_tasks(conn, manifest: list) -> list[str]:
    actual = []
    errors = []
    for row in conn.execute("SELECT * FROM tasks ORDER BY ordinal"):
        task = TypeAdapter(dict[str, Any]).validate_json(row["task_json"])
        digest = _hash(task)
        actual.append({"task_id": row["task_id"], "sha256": digest})
        if digest != row["task_sha256"] or task.get("task_id") != row["task_id"]:
            errors.append("task_identity_mismatch")
    if actual != manifest:
        errors.append("task_manifest_mismatch")
    return errors


def _check_attempt(row) -> list[str]:
    task = json.loads(row["task_json"]) if row["task_json"] else {}
    request = TypeAdapter(dict[str, Any]).validate_json(row["request_json"])
    errors = []
    if row["task_status"] != row["status"]:
        errors.append("attempt_task_status_mismatch")
    if task.get("request_sha256") != _hash(request):
        errors.append("request_hash_missing_or_mismatch")
    if row["status"] in ("valid", "invalid") and row["raw_reply"] is None:
        errors.append("terminal_without_raw_reply")
    return errors


def _check_attempts(conn) -> list[str]:
    errors = []
    query = (
        "SELECT a.*, t.task_json, t.status AS task_status "
        "FROM attempts a LEFT JOIN tasks t USING(task_id)"
    )
    for row in conn.execute(query):
        errors.extend(_check_attempt(row))
    missing = conn.execute(
        "SELECT COUNT(*) FROM tasks t LEFT JOIN attempts a USING(task_id) "
        "WHERE t.status != 'pending' AND a.attempt_id IS NULL"
    ).fetchone()[0]
    if missing:
        errors.append("claimed_task_without_attempt")
    return errors


def _limit_exceeded(actual, limit) -> bool:
    if limit is None:
        return False
    number = _elapsed(limit)
    return actual > number


def _budget_errors(conn, config: dict, timing: dict) -> list[str]:
    errors = []
    for actual, key in ((timing["calls"], "max_calls"), (timing["seconds"], "total_seconds")):
        if _limit_exceeded(actual, config.get(key)):
            errors.append(f"exceeds_{key}")
    errors.extend(_model_budget_errors(config, timing))
    maximum = conn.execute("SELECT MAX(elapsed_seconds) FROM attempts").fetchone()[0] or 0
    if _limit_exceeded(maximum, config.get("call_seconds")):
        errors.append("exceeds_call_seconds")
    return errors


def _model_budget_errors(config: dict, timing: dict) -> list[str]:
    errors = []
    limits = config.get("per_model_seconds")
    for model, values in timing["models"].items():
        limit = limits.get(model) if isinstance(limits, dict) else limits
        if _limit_exceeded(values["seconds"], limit):
            errors.append("exceeds_per_model_seconds")
    return errors


def _reading_verify(run_dir: Path, evidence: Path | None = None) -> dict[str, Any]:
    with _open_readonly_store(run_dir) as conn:
        return _verify_connection(conn, run_dir, evidence)


def _verify_connection(conn, run_dir: Path, evidence: Path | None) -> dict:
    current = _journal_snapshot(conn)
    journal_ok = not current["errors"]
    errors = list(current["errors"])
    timing = _timing(conn)
    errors.extend(_budget_errors(conn, current["config"], timing))
    extra = None
    if evidence is not None:
        extra = inspect_evidence(evidence, current, conn, _load_run_snapshot, _review_state)
        errors.extend(extra["errors"])
    unresolved = _unresolved_evidence(conn, timing, extra)
    ok = not errors and not unresolved
    return {
        "run_dir": str(run_dir),
        "ok": ok,
        "journal_checks_ok": journal_ok,
        "errors": sorted(set(errors)),
        "unresolved": unresolved,
        "timing": timing,
        "evidence": extra,
        "historical_integrity": "verified_bindings_only" if ok else "not_fully_verified",
        "source_fidelity": "not_assessed",
        "launch_ready": False,
        "bounded_output": True,
        "no_network": True,
        "no_inference": True,
        "original_store_opened": False,
    }


def _unresolved_evidence(conn, timing: dict, extra: dict | None) -> list:
    unresolved = list(_UNRESOLVED) if extra is None else []
    if timing["unknown_elapsed_attempts"] and extra is None:
        unresolved.append("unknown_elapsed_time_requires_conservative_reservation")
    if conn.execute("SELECT COUNT(*) FROM attempts WHERE status='inflight'").fetchone()[0]:
        unresolved.append("inflight_attempt_requires_reconciliation")
    return unresolved


def _journal_snapshot(conn) -> dict:
    config, manifest, config_hash = _identity(conn)
    errors = _check_tasks(conn, manifest) + _check_attempts(conn)
    if config_hash != _hash(config):
        errors.append("config_hash_mismatch")
    return {
        "config": config,
        "config_sha256": config_hash,
        "rows": [dict(row) for row in conn.execute("SELECT * FROM attempts")],
        "errors": errors,
    }


def _load_run_snapshot(run_dir: Path) -> dict:
    with _open_readonly_store(run_dir) as conn:
        return _journal_snapshot(conn)
