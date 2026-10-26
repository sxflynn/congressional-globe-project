"""Compose independent read-only pickup checks, keeping failures explicit."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from congressional_globe.reading_budget_audit import audit_budget
from congressional_globe.reading_evidence import (
    binary_bindings,
    evidence_bindings,
    load_json,
    load_spec,
)


def _check(label: str, action, errors: list):
    try:
        return action()
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        errors.append(f"{label}:{type(exc).__name__}")
        return None


def inspect_evidence(path: Path, current: dict, conn, loader, review_reader) -> dict:
    errors: list[str] = []
    spec = load_spec(path, current["config_sha256"])
    bindings = _check(
        "request_source_image_count_protocol_review_bindings",
        lambda: evidence_bindings(spec, current["config"], conn),
        errors,
    )
    reuse = _check(
        "reuse_evidence", lambda: load_json(spec.reuse) if spec.reuse else {"requests": []}, errors
    )
    budget = (
        _check("cross_run_budget", lambda: audit_budget(spec, current, reuse, loader), errors)
        if reuse is not None
        else None
    )
    binaries = _check("binary_evidence", lambda: binary_bindings(spec), errors)
    if budget is not None:
        errors.extend(budget["errors"])
    errors.extend(_binary_errors(binaries))
    review = _check(
        "review_database_observation", lambda: review_reader(spec.review_database), errors
    )
    return {
        "inspection_path": str(path),
        "bindings": _binding_summary(bindings),
        "budget": budget,
        "binaries": binaries,
        "errors": sorted(set(errors)),
        "current_review": review,
    }


def _binary_errors(binaries) -> list[str]:
    if binaries is None:
        return []
    return [f"{item['artifact']}_hash_missing_or_mismatch" for item in binaries if not item["ok"]]


def _binding_summary(bindings) -> dict | None:
    if bindings is None:
        return None
    return {key: bindings[key] for key in ("requests", "reused_requests", "source_units")}
