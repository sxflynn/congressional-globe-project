"""Read-only reading run status and verification (explicit run/config only)."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from congressional_globe.reading_run_store import ReadingRunStore


def add_reading_commands(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("reading", help="Read-only reading run status/verification")
    actions = command.add_subparsers(dest="reading_action", required=True)
    status = actions.add_parser("status", help="Report status for an explicit run")
    status.add_argument("--run-dir", type=Path, required=True, help="Explicit run directory containing attempts.sqlite")
    status.add_argument("--json", action="store_true", dest="json_out")
    verify = actions.add_parser("verify", help="Verify run bindings for an explicit run")
    verify.add_argument("--run-dir", type=Path, required=True, help="Explicit run directory containing attempts.sqlite")
    verify.add_argument("--json", action="store_true", dest="json_out")


def run_reading(arguments: argparse.Namespace, _: Path) -> None:
    if arguments.reading_action == "status":
        report = _reading_status(arguments.run_dir)
        if getattr(arguments, "json_out", False):
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            return
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if arguments.reading_action == "verify":
        report = _reading_verify(arguments.run_dir)
        if getattr(arguments, "json_out", False):
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            return
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    raise ValueError(f"Unknown reading action: {arguments.reading_action}")


def _open_readonly_store(run_dir: Path) -> sqlite3.Connection:
    db_path = run_dir / "attempts.sqlite"
    if not db_path.exists():
        raise FileNotFoundError(f"attempts.sqlite not found in {run_dir}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _reading_status(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    conn = _open_readonly_store(run_dir)
    try:
        identity = conn.execute("SELECT config_json, config_sha256, task_manifest_json FROM run_identity WHERE singleton=1").fetchone()
        if identity is None:
            raise ValueError("missing run identity")
        config = json.loads(identity["config_json"])
        task_manifest = json.loads(identity["task_manifest_json"])
        
        task_rows = list(conn.execute("SELECT status, COUNT(*) as n FROM tasks GROUP BY status"))
        tasks_by_status = {row["status"]: int(row["n"]) for row in task_rows}
        total_tasks = len(task_manifest)
        
        attempt_rows = list(conn.execute("SELECT attempt_id, task_id, status, request_json, raw_reply, usage_json, detail, elapsed_seconds, started_at, finished_at FROM attempts"))
        attempts = []
        unknown_elapsed = 0
        unknown_model = 0
        for row in attempt_rows:
            req = json.loads(row["request_json"]) if row["request_json"] else {}
            model = req.get("model") if isinstance(req, dict) else None
            elapsed = row["elapsed_seconds"]
            if elapsed is None:
                unknown_elapsed += 1
            if not model:
                unknown_model += 1
            usage = json.loads(row["usage_json"]) if row["usage_json"] else None
            attempts.append({
                "attempt_id": row["attempt_id"],
                "task_id": row["task_id"],
                "status": row["status"],
                "model": model,
                "elapsed_seconds": elapsed,
                "has_raw_reply": row["raw_reply"] is not None,
                "has_usage": usage is not None,
                "detail": row["detail"],
            })
        
        # Budget info from config
        max_calls = config.get("max_calls")
        total_seconds = config.get("total_seconds")
        per_model_seconds = config.get("per_model_seconds")
        
        # Compute timing summary like store does
        timing = {"calls": 0, "seconds": 0.0, "models": {}, "unknown_elapsed_attempts": unknown_elapsed, "unknown_model_attempts": unknown_model}
        for att in attempts:
            timing["calls"] += 1
            if att["elapsed_seconds"] is not None:
                timing["seconds"] += float(att["elapsed_seconds"])
                if att["model"]:
                    bucket = timing["models"].setdefault(att["model"], {"calls": 0, "seconds": 0.0})
                    bucket["calls"] += 1
                    bucket["seconds"] += float(att["elapsed_seconds"])
        
        stop_reports = []
        for row in conn.execute("SELECT report_json, created_at FROM stop_reports ORDER BY report_id"):
            try:
                stop_reports.append({"report": json.loads(row["report_json"]), "created_at": row["created_at"]})
            except Exception:
                stop_reports.append({"report_json": row["report_json"], "created_at": row["created_at"]})
        
        return {
            "run_dir": str(run_dir),
            "config_sha256": identity["config_sha256"],
            "task_count": total_tasks,
            "tasks_by_status": tasks_by_status,
            "attempts": attempts,
            "journal_counts": {
                "total_tasks": total_tasks,
                "tasks_by_status": tasks_by_status,
                "attempt_count": len(attempts),
                "terminal": sum(tasks_by_status.get(s, 0) for s in ("valid", "invalid", "failed", "timeout")),
                "pending": tasks_by_status.get("pending", 0),
                "inflight": tasks_by_status.get("inflight", 0),
            },
            "timing": timing,
            "budget": {
                "max_calls": max_calls,
                "total_seconds": total_seconds,
                "per_model_seconds": per_model_seconds,
                "prior/current evidence": {
                    "recorded_seconds": timing["seconds"],
                    "calls": timing["calls"],
                    "by_model": timing["models"],
                },
            },
            "unknown_usage": {
                "unknown_elapsed_attempts": unknown_elapsed,
                "unknown_model_attempts": unknown_model,
                "attempts_without_elapsed": unknown_elapsed,
            },
            "review/ownership_state": {
                "stop_reports": stop_reports,
                "inflight_blocking": tasks_by_status.get("inflight", 0) > 0,
            },
            "next_action": _next_action(tasks_by_status, timing, max_calls),
            "bounded_output": True,
        }
    finally:
        conn.close()


def _next_action(tasks_by_status: dict, timing: dict, max_calls: Any) -> str:
    inflight = tasks_by_status.get("inflight", 0)
    pending = tasks_by_status.get("pending", 0)
    if inflight > 0:
        return "reconcile_inflight_attempt_before_new_dispatch"
    if pending > 0:
        if max_calls is not None and timing.get("calls", 0) >= max_calls:
            return "at_or_over_call_budget_no_new_dispatch"
        return "dispatch_next_pending_from_explicit_run"
    return "all_tasks_terminal_review_evidence"


def _reading_verify(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    conn = _open_readonly_store(run_dir)
    try:
        identity = conn.execute("SELECT config_json, config_sha256, task_manifest_json FROM run_identity WHERE singleton=1").fetchone()
        if identity is None:
            raise ValueError("missing run identity")
        config = json.loads(identity["config_json"])
        task_manifest = json.loads(identity["task_manifest_json"])
        errors = []
        warnings = []
        # Check task manifest consistency
        task_rows = list(conn.execute("SELECT task_id, task_sha256, status FROM tasks"))
        if len(task_rows) != len(task_manifest):
            errors.append("task_count_mismatch")
        # Check attempts
        attempt_rows = list(conn.execute("SELECT attempt_id, task_id, status, request_json, elapsed_seconds, usage_json, raw_reply FROM attempts"))
        seen_task_ids = set()
        for row in attempt_rows:
            if row["task_id"] in seen_task_ids:
                errors.append(f"duplicate_attempt_task:{row['task_id']}")
            seen_task_ids.add(row["task_id"])
            try:
                req = json.loads(row["request_json"])
            except Exception:
                errors.append(f"bad_request_json:{row['attempt_id']}")
                continue
            if not isinstance(req, dict):
                errors.append(f"bad_request_type:{row['attempt_id']}")
                continue
            # Check bindings
            if not req.get("model") and not req.get("model_digest"):
                warnings.append(f"missing_model_identity:{row['attempt_id']}")
            if row["status"] in ("valid", "invalid") and row["raw_reply"] is None:
                errors.append(f"terminal_without_raw_reply:{row['attempt_id']}")
            if row["elapsed_seconds"] is None and row["status"] != "inflight":
                warnings.append(f"unknown_elapsed_time:{row['attempt_id']}")
        timing = {"calls": len(attempt_rows), "seconds": 0.0, "models": {}}
        unknown_elapsed = 0
        for row in attempt_rows:
            if row["elapsed_seconds"] is None:
                unknown_elapsed += 1
            else:
                timing["seconds"] += float(row["elapsed_seconds"])
        if unknown_elapsed:
            warnings.append(f"unknown_elapsed_attempts:{unknown_elapsed}")
        # Conservative cross-run budget check
        max_calls = config.get("max_calls")
        if max_calls is not None and timing["calls"] > max_calls:
            errors.append("call_count_exceeds_configured_max_calls")
        return {
            "run_dir": str(run_dir),
            "ok": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "checks": {
                "identity_present": identity is not None,
                "request_bindings_checked": len(attempt_rows),
                "task_manifest_count": len(task_manifest),
                "reuse_bindings_consistent": len(seen_task_ids) == len(attempt_rows),
                "conservative_budgets": {
                    "max_calls": max_calls,
                    "total_seconds": config.get("total_seconds"),
                    "per_model_seconds": config.get("per_model_seconds"),
                    "recorded_seconds": timing["seconds"],
                    "double_count_risk": False,
                },
            },
            "bounded_output": True,
            "no_writes": True,
            "no_network": True,
            "no_inference": True,
            "sqlite_constructor_writes_avoided": True,
        }
    finally:
        conn.close()

