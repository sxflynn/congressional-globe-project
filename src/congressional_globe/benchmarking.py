"""Small-sample, opt-in benchmarks for cleanup providers."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, TypeGuard

from pydantic import BaseModel, ConfigDict, Field

from congressional_globe.models import TextEdit
from congressional_globe.normalization import apply_edits, resolve_edits
from congressional_globe.providers import CleanupProvider


class BenchmarkCase(BaseModel):
    """One expected cleanup example at the external JSONL boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    text_ocr: str
    expected_text: str


class BenchmarkRecord(BaseModel):
    """Per-case response and scoring details, including failed cases."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    raw_response: str | None = None
    duration_seconds: float = Field(ge=0)
    validated_edits: list[TextEdit] | None = None
    normalized_text: str | None = None
    needs_image_review: bool = False
    review_reason: str | None = None
    exact_expected_agreement: bool | None = None
    unchanged_control_error: bool | None = None
    usage: dict[str, Any] | None = None
    error: str | None = None


class BenchmarkSummary(BaseModel):
    """Run metadata and aggregate scoring for a benchmark sample."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    backend: str
    model: str
    cases_path: str
    requested_limit: int | None
    cases: int
    usage_cases: int | None = None
    succeeded: int
    failed: int
    review_required: int
    exact_matches: int
    unchanged_controls: int
    unchanged_control_errors: int
    total_input_tokens: int
    total_output_tokens: int
    total_duration_seconds: float = Field(ge=0)
    mean_duration_seconds: float = Field(ge=0)


def run_benchmark(
    cases_path: Path,
    provider: CleanupProvider,
    *,
    backend: str,
    model: str,
    run_id: str,
    limit: int | None = None,
    artifacts_dir: Path = Path("artifacts/benchmarks"),
) -> BenchmarkSummary:
    """Run selected cases sequentially and write JSONL records plus a summary.

    Provider calls are opt-in: this function performs them only when called. The
    caller should configure the provider's network timeout before passing it in.
    """
    _validate_run_options(backend, model, run_id, limit)
    cases = _load_cases(cases_path, limit)
    destination = artifacts_dir / run_id
    destination.mkdir(parents=True, exist_ok=False)
    records_path = destination / "results.jsonl"
    durations: list[float] = []
    counts = _empty_counts()
    with records_path.open("w", encoding="utf-8") as records_file:
        for case in cases:
            record = _run_case(provider, case)
            records_file.write(record.model_dump_json() + "\n")
            durations.append(record.duration_seconds)
            _count_record(counts, record, case)
    summary = _make_summary(cases_path, run_id, backend, model, limit, counts, durations)
    (destination / "summary.json").write_text(
        summary.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return summary


def _validate_run_options(backend: str, model: str, run_id: str, limit: int | None) -> None:
    _validate_provider_identity(backend, model)
    _validate_run_id(run_id)
    _validate_limit(limit)


def _validate_provider_identity(backend: str, model: str) -> None:
    if backend.strip() and model.strip():
        return
    raise ValueError("backend and model must be non-empty")


def _validate_run_id(run_id: str) -> None:
    if run_id and Path(run_id).name == run_id and run_id not in {".", ".."}:
        return
    raise ValueError("run_id must be a single safe directory name")


def _validate_limit(limit: int | None) -> None:
    if limit is None or limit >= 1:
        return
    raise ValueError("limit must be positive")


def _load_cases(path: Path, limit: int | None) -> list[BenchmarkCase]:
    cases = []
    seen: set[str] = set()
    for line_number, line in _iter_nonempty_lines(path):
        cases.append(_parse_case(line, line_number, seen))
        if _limit_reached(limit, len(cases)):
            break
    if not cases:
        raise ValueError("benchmark case file contains no cases")
    return cases


def _iter_nonempty_lines(path: Path) -> Iterator[tuple[int, str]]:
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if line.strip():
                yield line_number, line


def _limit_reached(limit: int | None, count: int) -> bool:
    return limit is not None and count >= limit


def _parse_case(line: str, line_number: int, seen: set[str]) -> BenchmarkCase:
    try:
        case = BenchmarkCase.model_validate_json(line)
    except ValueError as error:
        raise ValueError(f"invalid benchmark case on line {line_number}: {error}") from error
    if case.id in seen:
        raise ValueError(f"duplicate benchmark case id {case.id!r}")
    seen.add(case.id)
    return case


def _run_case(provider: CleanupProvider, case: BenchmarkCase) -> BenchmarkRecord:
    started = time.perf_counter()
    raw_response: str | None = None
    usage: dict[str, Any] | None = None
    edits: list[TextEdit] | None = None
    normalized_text: str | None = None
    needs_review = False
    review_reason: str | None = None
    try:
        result = provider.clean(case.text_ocr)
        raw_response = result.raw_response
        usage = _provider_usage(result)
        needs_review = result.cleanup.needs_image_review
        review_reason = result.cleanup.review_reason
        edits = resolve_edits(case.text_ocr, result.cleanup.edits)
        normalized_text = apply_edits(case.text_ocr, edits)
        return BenchmarkRecord(
            case_id=case.id,
            raw_response=raw_response,
            duration_seconds=time.perf_counter() - started,
            validated_edits=edits,
            normalized_text=normalized_text,
            needs_image_review=needs_review,
            review_reason=review_reason,
            exact_expected_agreement=normalized_text == case.expected_text,
            unchanged_control_error=(
                normalized_text != case.text_ocr if case.expected_text == case.text_ocr else None
            ),
            usage=usage,
        )
    except Exception as error:
        raw_response = raw_response or _exception_raw_response(error)
        return BenchmarkRecord(
            case_id=case.id,
            raw_response=raw_response,
            duration_seconds=time.perf_counter() - started,
            validated_edits=edits,
            normalized_text=normalized_text,
            needs_image_review=needs_review,
            review_reason=review_reason,
            usage=usage,
            error=f"{type(error).__name__}: {error}",
        )


def _provider_usage(result: Any) -> dict[str, Any] | None:
    usage = getattr(result, "usage", None)
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        usage = usage.model_dump(mode="json")
    return dict(usage) if isinstance(usage, dict) else {"value": usage}


def _exception_raw_response(error: Exception) -> str | None:
    raw = getattr(error, "raw_response", None)
    return raw if isinstance(raw, str) else None


def _empty_counts() -> dict[str, int]:
    return {
        "succeeded": 0,
        "failed": 0,
        "review_required": 0,
        "exact_matches": 0,
        "unchanged_controls": 0,
        "unchanged_control_errors": 0,
        "usage_cases": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }


def _count_record(counts: dict[str, int], record: BenchmarkRecord, case: BenchmarkCase) -> None:
    _count_usage(counts, record.usage)
    if record.needs_image_review:
        counts["review_required"] += 1
    if record.error:
        counts["failed"] += 1
        return
    if record.needs_image_review:
        return
    counts["succeeded"] += 1
    counts["exact_matches"] += int(record.exact_expected_agreement is True)
    if case.expected_text == case.text_ocr:
        counts["unchanged_controls"] += 1
        counts["unchanged_control_errors"] += int(record.unchanged_control_error is True)


def _count_usage(counts: dict[str, int], usage: dict[str, Any] | None) -> None:
    if usage is None:
        return
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if not _is_token_count(input_tokens) or not _is_token_count(output_tokens):
        return
    counts["usage_cases"] += 1
    counts["total_input_tokens"] += input_tokens
    counts["total_output_tokens"] += output_tokens


def _is_token_count(value: Any) -> TypeGuard[int]:
    return type(value) is int and value >= 0


def _make_summary(
    cases_path: Path,
    run_id: str,
    backend: str,
    model: str,
    limit: int | None,
    counts: dict[str, int],
    durations: list[float],
) -> BenchmarkSummary:
    total = sum(durations)
    return BenchmarkSummary(
        run_id=run_id,
        backend=backend,
        model=model,
        cases_path=str(cases_path),
        requested_limit=limit,
        cases=len(durations),
        total_duration_seconds=total,
        mean_duration_seconds=total / len(durations) if durations else 0,
        **counts,
    )
