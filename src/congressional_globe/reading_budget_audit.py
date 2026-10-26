"""Recompute bounded cross-run usage from exact journal rows, never spend it."""

from __future__ import annotations

import json
import math
from pathlib import Path

from pydantic import Field

from congressional_globe.reading_evidence import (
    EvidenceModel,
    FileRef,
    InspectionEvidence,
    checked_file,
    load_json,
)
from congressional_globe.reading_requests import digest, wire_bytes


class BudgetBounds(EvidenceModel):
    max_calls: int = Field(ge=0)
    max_total_seconds: float = Field(ge=0, allow_inf_nan=False)
    max_model_seconds: float = Field(ge=0, allow_inf_nan=False)
    max_call_seconds: float = Field(gt=0, allow_inf_nan=False)


def _number(value) -> float:
    if type(value) not in {int, float}:
        raise ValueError("budget number must be numeric, not boolean/text")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("invalid budget number")
    return number


def _cap(config: dict) -> float | None:
    value = config.get("call_seconds")
    return None if value is None else _number(value)


def _collect_runs(spec: InspectionEvidence, current: dict, loader) -> list[dict]:
    runs = [current]
    for ref in spec.prior_runs:
        run = loader(Path(ref.run_dir))
        if run["config_sha256"] != ref.config_sha256 or run["errors"]:
            raise ValueError("prior_journal_identity_or_integrity_mismatch")
        runs.append(run)
    return runs


def _unique_attempts(runs: list[dict]) -> tuple[dict, int]:
    attempts = {}
    duplicates = 0
    for run in runs:
        for row in run["rows"]:
            duplicates += _insert_attempt(attempts, row, run["config"])
    return attempts, duplicates


def _insert_attempt(attempts: dict, row: dict, config: dict) -> int:
    fingerprint = digest(wire_bytes({"row": row, "call_cap": _cap(config)}))
    prior = attempts.get(row["attempt_id"])
    if prior is not None:
        _same_attempt(prior, fingerprint)
        return 1
    attempts[row["attempt_id"]] = {"row": row, "cap": _cap(config), "fingerprint": fingerprint}
    return 0


def _same_attempt(prior: dict, fingerprint: str) -> None:
    if prior["fingerprint"] != fingerprint:
        raise ValueError("same_attempt_id_has_conflicting_journal_records")


def _charge(record: dict) -> tuple[float, bool]:
    row, cap = record["row"], record["cap"]
    elapsed = row["elapsed_seconds"]
    ambiguous = elapsed is None or row["raw_reply"] is None
    if ambiguous and cap is None:
        raise ValueError("unknown_time_has_no_recorded_call_reservation")
    known = 0.0 if elapsed is None else _number(elapsed)
    return _reserved_seconds(known, cap, ambiguous), ambiguous


def _reserved_seconds(known: float, cap: float | None, ambiguous: bool) -> float:
    return max(known, cap or 0) if ambiguous else known


def _totals(records: list[dict]) -> dict:
    result = {
        "calls": 0,
        "known_input_tokens": 0,
        "known_output_tokens": 0,
        "recorded_seconds": 0.0,
        "conservative_seconds": 0.0,
        "reserved_or_ambiguous_attempts": 0,
        "unknown_elapsed_attempts": 0,
        "unknown_token_usage_attempts": 0,
        "models": {},
    }
    for record in records:
        _add_attempt(result, record)
    return result


def _add_attempt(result: dict, record: dict) -> None:
    row = record["row"]
    request = json.loads(row["request_json"])
    model = request.get("model")
    if not isinstance(model, str) or not model:
        raise ValueError("attempt_model_identity_unknown")
    charged, ambiguous = _charge(record)
    tokens = token_usage(row["usage_json"])
    result["known_input_tokens"] += tokens["known_input_tokens"]
    result["known_output_tokens"] += tokens["known_output_tokens"]
    result["calls"] += 1
    result["recorded_seconds"] += _number(row["elapsed_seconds"] or 0)
    result["conservative_seconds"] += charged
    result["reserved_or_ambiguous_attempts"] += ambiguous
    result["unknown_elapsed_attempts"] += row["elapsed_seconds"] is None
    result["unknown_token_usage_attempts"] += not _known_usage(row["usage_json"])
    bucket = result["models"].setdefault(model, {"calls": 0, "conservative_seconds": 0.0})
    bucket["calls"] += 1
    bucket["conservative_seconds"] += charged


def _token(usage: dict, key: str) -> int:
    value = usage.get(key)
    return value if type(value) is int and value >= 0 else 0


def token_usage(value) -> dict:
    usage = json.loads(value) if value else {}
    if not isinstance(usage, dict):
        usage = {}
    return {
        "known_input_tokens": _token(usage, "prompt_eval_count"),
        "known_output_tokens": _token(usage, "eval_count"),
    }


def _known_usage(value) -> bool:
    usage = json.loads(value) if value else {}
    if not isinstance(usage, dict):
        return False
    return all(
        type(usage.get(k)) is int and usage[k] >= 0 for k in ("prompt_eval_count", "eval_count")
    )


def _check_reuse(reuse: dict, attempts: dict, current_ids: set[str]) -> None:
    seen = set()
    exported = _reuse_export(reuse)
    for entry in reuse.get("requests", []):
        saved = entry["attempt"]
        identifier = saved["attempt_id"]
        if identifier in seen or identifier in current_ids:
            raise ValueError("reuse_is_duplicated_or_charged_as_new_attempt")
        seen.add(identifier)
        row = attempts[identifier]["row"]
        _one_reuse(entry, row)
        _export_matches(exported[identifier], row)


def _reuse_export(reuse: dict) -> dict:
    if not reuse.get("requests"):
        return {}
    export = load_json(FileRef.model_validate(reuse["source_attempt_export"]))
    return {row["attempt_id"]: row for row in export["attempts"]}


def _export_matches(exported: dict, row: dict) -> None:
    if any(exported[k] != row[k] for k in ("task_id", "status", "raw_reply", "elapsed_seconds")):
        raise ValueError("reuse_terminal_export_differs_from_journal")
    if exported["request_sha256"] != digest(wire_bytes(json.loads(row["request_json"]))):
        raise ValueError("reuse_terminal_export_request_mismatch")


def _one_reuse(entry: dict, row: dict) -> None:
    saved, request = entry["attempt"], entry["request"]
    fields = ("task_id", "status", "started_at", "finished_at", "elapsed_seconds")
    if any(saved[key] != row[key] for key in fields):
        raise ValueError("reuse_attempt_fields_mismatch")
    if row["status"] != "valid" or row["raw_reply"] is None:
        raise ValueError("reuse_requires_valid_saved_reply")
    if digest(wire_bytes(json.loads(row["request_json"]))) != request["request_sha256"]:
        raise ValueError("reuse_request_hash_mismatch")


def _limit_errors(totals: dict, limits: dict) -> list[str]:
    errors = []
    checks = ((totals["calls"], "max_calls"), (totals["conservative_seconds"], "max_total_seconds"))
    for actual, name in checks:
        if actual > _number(limits[name]):
            errors.append(f"cumulative_{name}_exceeded")
    errors.extend(_model_limit_errors(totals, limits))
    return sorted(set(errors))


def _model_limit_errors(totals: dict, limits: dict) -> list[str]:
    return [
        "cumulative_model_seconds_exceeded"
        for bucket in totals["models"].values()
        if bucket["conservative_seconds"] > _number(limits["max_model_seconds"])
    ]


def _prior_claim_errors(prior: dict, budget: dict) -> list[str]:
    claim = budget["prior_usage"]
    if claim["calls"] != prior["calls"]:
        return ["prior_call_narrative_mismatch"]
    if not math.isclose(
        _number(claim["total_seconds"]), prior["conservative_seconds"], abs_tol=0.00001
    ):
        return ["prior_seconds_narrative_mismatch"]
    return _prior_model_claim_errors(prior, claim)


def _prior_model_claim_errors(prior: dict, claim: dict) -> list[str]:
    if set(prior["models"]) != set(claim["by_model"]):
        return ["prior_model_set_mismatch"]
    for model, bucket in prior["models"].items():
        declared = claim["by_model"][model]
        if not math.isclose(
            _number(declared["conservative_total_seconds"]),
            bucket["conservative_seconds"],
            abs_tol=0.00001,
        ):
            return ["prior_model_narrative_mismatch"]
    return []


def _budget_sources(budget: dict) -> None:
    sources = budget.get("sources", {})
    if not sources:
        raise ValueError("budget_provenance_missing")
    for path, sha in sources.items():
        checked_file(FileRef(path=path, sha256=sha))


def audit_budget(spec: InspectionEvidence, current: dict, reuse: dict, loader) -> dict:
    budget = load_json(spec.budget)
    BudgetBounds.model_validate(budget["approved_bounds"])
    _budget_sources(budget)
    runs = _collect_runs(spec, current, loader)
    attempts, duplicates = _unique_attempts(runs)
    current_ids = {row["attempt_id"] for row in current["rows"]}
    _check_reuse(reuse, attempts, current_ids)
    prior = _totals([v for key, v in attempts.items() if key not in current_ids])
    total = _totals(list(attempts.values()))
    errors = _prior_claim_errors(prior, budget) + _limit_errors(total, budget["approved_bounds"])
    errors.extend(_call_limit_errors(list(attempts.values()), budget["approved_bounds"]))
    return {
        "prior": prior,
        "cumulative": total,
        "deduplicated_attempt_references": duplicates,
        "approved_bounds": budget["approved_bounds"],
        "errors": errors,
        "remaining_allowance": None,
        "budget_evidence_sha256": spec.budget.sha256,
    }


def _call_limit_errors(records: list[dict], limits: dict) -> list[str]:
    limit = _number(limits["max_call_seconds"])
    if any(_over_call_limit(record, limit) for record in records):
        return ["exceeds_call_seconds"]
    return []


def _over_call_limit(record: dict, limit: float) -> bool:
    elapsed = _number(record["row"]["elapsed_seconds"] or 0)
    return elapsed > limit or (record["cap"] or 0) > limit
