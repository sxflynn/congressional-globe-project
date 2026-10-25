"""Offline revalidation of saved M1 role replies under contract v2."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from congressional_globe.role_v2 import role_result_schema, validate_role_result_v2


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _read_provider_inputs(path: Path) -> dict[str, dict[str, Any]]:
    return {row["window_id"]: row for row in map(json.loads, path.read_text().splitlines())}


def revalidate_saved_replies(preparation: Path, comparison: Path) -> dict[str, Any]:
    inputs = _read_provider_inputs(preparation / "provider-inputs.jsonl")
    summaries: list[tuple[str, Path]] = [
        ("mini", comparison / "mini" / "summary.json"),
        ("qwen", comparison / "qwen" / "summary.json"),
    ]
    rows = _collect_records(summaries, inputs)
    return _revalidation_document(preparation, summaries, rows)


def _collect_records(
    summaries: list[tuple[str, Path]], inputs: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model, path in summaries:
        rows.extend(_model_records(model, path, inputs))
    return rows


def _model_records(
    model: str, path: Path, inputs: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    summary = json.loads(path.read_text())
    return [_attempt_record(model, path, attempt, inputs) for attempt in summary["results"]]


def _attempt_record(
    model: str,
    path: Path,
    attempt: dict[str, Any],
    inputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    raw_reply = attempt["result"].get("output_text")
    if not isinstance(raw_reply, str):
        return _failed_record(model, path, attempt, "saved output_text is missing")
    return _validate_record(model, path, attempt, raw_reply, inputs.get(attempt["window_id"]))


def _revalidation_document(
    preparation: Path, summaries: list[tuple[str, Path]], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "schema_version": "role-revalidation-v2",
        "protocol_version": "role-result-v2",
        "source_artifacts": {
            "provider_inputs": _sha256_file(preparation / "provider-inputs.jsonl"),
            "mini_summary": _sha256_file(summaries[0][1]),
            "qwen_summary": _sha256_file(summaries[1][1]),
            "validator_code": _sha256_file(Path(__file__).with_name("role_v2.py")),
            "revalidator_code": _sha256_file(Path(__file__)),
        },
        "records": rows,
        "counts": {
            "saved_replies": len(rows),
            "v2_valid": sum(row["v2_status"] == "valid" for row in rows),
            "v2_invalid": sum(row["v2_status"] == "invalid" for row in rows),
        },
        "interpretation": "Structural revalidation only; no semantic/source or human-grade claim.",
    }


def _validate_record(
    model: str,
    summary_path: Path,
    attempt: dict[str, Any],
    raw_reply: str,
    packet: dict[str, Any] | None,
) -> dict[str, Any]:
    base = _record_base(model, summary_path, attempt, raw_reply)
    if packet is None:
        return {
            **base,
            "v2_status": "invalid",
            "v2_error": "matching frozen input packet is missing",
        }
    try:
        parsed = json.loads(raw_reply)
        validated = validate_role_result_v2(parsed, packet)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return {**base, "v2_status": "invalid", "v2_error": str(exc)}
    return {**base, "v2_status": "valid", "v2_result": validated}


def _failed_record(
    model: str, summary_path: Path, attempt: dict[str, Any], error: str
) -> dict[str, Any]:
    raw_reply = json.dumps(attempt.get("result", {}), ensure_ascii=False, separators=(",", ":"))
    return {
        **_record_base(model, summary_path, attempt, raw_reply),
        "v2_status": "invalid",
        "v2_error": error,
    }


def _record_base(
    model: str, summary_path: Path, attempt: dict[str, Any], raw_reply: str
) -> dict[str, Any]:
    result = attempt["result"]
    raw_response = result.get("raw_response")
    return {
        "model": model,
        "window_id": attempt["window_id"],
        "v1_status": attempt["status"],
        "v1_validation_error": result.get("validation_error"),
        "source_summary": str(summary_path),
        "raw_reply": raw_reply,
        "raw_reply_sha256": _sha256_bytes(raw_reply.encode("utf-8")),
        "provider_response_sha256": (
            _sha256_bytes(raw_response.encode("utf-8")) if isinstance(raw_response, str) else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = revalidate_saved_replies(args.preparation, args.comparison)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "revalidation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    (args.output / "schema.json").write_text(
        json.dumps(role_result_schema(), ensure_ascii=False, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
