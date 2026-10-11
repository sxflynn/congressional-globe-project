"""Transparent workload projections based on measured provider benchmarks."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from congressional_globe.benchmarking import BenchmarkRecord, BenchmarkSummary


class WorkloadEstimate(BaseModel):
    """Projected sequential cost/time, with benchmark provenance and limits."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    benchmark_run_id: str
    backend: str
    model: str
    sample_cases: int = Field(ge=1)
    sample_failed: int = Field(ge=0)
    sample_review_required: int = Field(ge=0)
    requested_jobs: int = Field(ge=0)
    retry_fraction: float = Field(ge=0)
    projected_requests: float = Field(ge=0)
    mean_seconds_per_request: float = Field(ge=0)
    sequential_hours: float = Field(ge=0)
    sequential_days: float = Field(ge=0)
    mean_input_tokens_per_request: float | None = Field(default=None, ge=0)
    mean_output_tokens_per_request: float | None = Field(default=None, ge=0)
    projected_input_tokens: float | None = Field(default=None, ge=0)
    projected_output_tokens: float | None = Field(default=None, ge=0)
    projected_total_tokens: float | None = Field(default=None, ge=0)
    realized_sample_api_usd: float | None = Field(default=None, ge=0)
    projected_api_usd: float | None = Field(default=None, ge=0)
    pricing: str
    quality_status: str
    limitations: list[str]


def estimate(
    summary: BenchmarkSummary,
    jobs: int,
    input_usd_per_million: float | None = None,
    output_usd_per_million: float | None = None,
    retry_fraction: float = 0,
) -> WorkloadEstimate:
    """Project time and token usage from an explicitly measured sample."""
    _validate_request(summary, jobs, retry_fraction)
    rates = _validate_rates(input_usd_per_million, output_usd_per_million)
    has_usage = _has_complete_usage(summary)
    if summary.backend == "openai":
        _require_cloud_usage(summary, has_usage)
    mean_input = summary.total_input_tokens / summary.cases if has_usage else None
    mean_output = summary.total_output_tokens / summary.cases if has_usage else None
    requests = jobs * (1 + retry_fraction)
    projected_input = mean_input * requests if mean_input is not None else None
    projected_output = mean_output * requests if mean_output is not None else None
    cost = _projected_api_cost(summary.backend, projected_input, projected_output, rates)
    realized_cost = _realized_sample_cost(summary, rates)
    seconds = summary.mean_duration_seconds * requests
    return WorkloadEstimate(
        benchmark_run_id=summary.run_id,
        backend=summary.backend,
        model=summary.model,
        sample_cases=summary.cases,
        sample_failed=summary.failed,
        sample_review_required=summary.review_required,
        requested_jobs=jobs,
        retry_fraction=retry_fraction,
        projected_requests=requests,
        mean_seconds_per_request=summary.mean_duration_seconds,
        sequential_hours=seconds / 3600,
        sequential_days=seconds / 86400,
        mean_input_tokens_per_request=mean_input,
        mean_output_tokens_per_request=mean_output,
        projected_input_tokens=projected_input,
        projected_output_tokens=projected_output,
        projected_total_tokens=_total_tokens(projected_input, projected_output),
        realized_sample_api_usd=realized_cost,
        projected_api_usd=cost,
        pricing=_pricing_label(summary.backend, rates),
        quality_status="Projection only; not approval for corpus-wide use.",
        limitations=_limitations(summary.backend, has_usage),
    )


def load_summary(path: Path) -> BenchmarkSummary:
    """Load and validate a benchmark summary artifact."""
    summary = BenchmarkSummary.model_validate_json(path.read_text(encoding="utf-8"))
    if summary.usage_cases is not None:
        return summary
    results_path = path.with_name("results.jsonl")
    if not results_path.exists():
        return summary
    coverage, input_tokens, output_tokens = _usage_from_results(results_path)
    if coverage > summary.cases:
        raise ValueError("benchmark result usage coverage exceeds the summary sample count")
    if input_tokens != summary.total_input_tokens or output_tokens != summary.total_output_tokens:
        raise ValueError("benchmark result token totals do not match the summary")
    return summary.model_copy(update={"usage_cases": coverage})


def _usage_from_results(path: Path) -> tuple[int, int, int]:
    totals = [0, 0, 0]
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        _add_usage(totals, BenchmarkRecord.model_validate_json(line))
    return totals[0], totals[1], totals[2]


def _add_usage(totals: list[int], record: BenchmarkRecord) -> None:
    values = record.usage or {}
    source_input = _nonnegative_integer(values.get("input_tokens"))
    source_output = _nonnegative_integer(values.get("output_tokens"))
    if source_input is None or source_output is None:
        return
    totals[0] += 1
    totals[1] += source_input
    totals[2] += source_output


def _nonnegative_integer(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _validate_request(summary: BenchmarkSummary, jobs: int, retry_fraction: float) -> None:
    if summary.cases < 1:
        raise ValueError("cannot estimate from an empty benchmark summary")
    _validate_jobs(jobs)
    _validate_retry(retry_fraction)
    _validate_measurements(summary)
    if summary.backend not in {"ollama", "openai"}:
        raise ValueError(f"unsupported benchmark backend: {summary.backend}")


def _validate_jobs(jobs: int) -> None:
    if jobs < 0:
        raise ValueError("jobs cannot be negative")


def _validate_retry(retry_fraction: float) -> None:
    if retry_fraction < 0 or not math.isfinite(retry_fraction):
        raise ValueError("retry_fraction must be finite and non-negative")


def _validate_measurements(summary: BenchmarkSummary) -> None:
    if summary.mean_duration_seconds < 0 or not math.isfinite(summary.mean_duration_seconds):
        raise ValueError("benchmark duration must be finite and non-negative")
    if summary.total_input_tokens < 0 or summary.total_output_tokens < 0:
        raise ValueError("benchmark token totals cannot be negative")
    _validate_usage_coverage(summary)


def _validate_usage_coverage(summary: BenchmarkSummary) -> None:
    if summary.usage_cases is not None and not 0 <= summary.usage_cases <= summary.cases:
        raise ValueError("benchmark usage coverage is outside the sample count")


def _validate_rates(
    input_rate: float | None, output_rate: float | None
) -> tuple[float, float] | None:
    if input_rate is None and output_rate is None:
        return None
    if input_rate is None or output_rate is None:
        raise ValueError("supply both input and output token rates")
    _validate_rate_values(input_rate, output_rate)
    return input_rate, output_rate


def _validate_rate_values(input_rate: float, output_rate: float) -> None:
    if not math.isfinite(input_rate) or not math.isfinite(output_rate):
        raise ValueError("token rates must be finite")
    if input_rate < 0 or output_rate < 0:
        raise ValueError("token rates cannot be negative")


def _has_complete_usage(summary: BenchmarkSummary) -> bool:
    return summary.usage_cases == summary.cases


def _require_cloud_usage(summary: BenchmarkSummary, has_usage: bool) -> None:
    if has_usage:
        return
    raise ValueError("OpenAI estimates require input and output usage for every benchmark case")


def _projected_api_cost(
    backend: str,
    projected_input: float | None,
    projected_output: float | None,
    rates: tuple[float, float] | None,
) -> float | None:
    if backend == "ollama":
        return 0.0
    if rates is None or projected_input is None or projected_output is None:
        return None
    return (projected_input * rates[0] + projected_output * rates[1]) / 1_000_000


def _realized_sample_cost(
    summary: BenchmarkSummary, rates: tuple[float, float] | None
) -> float | None:
    if summary.backend == "ollama":
        return 0.0
    if rates is None:
        return None
    return (
        summary.total_input_tokens * rates[0] + summary.total_output_tokens * rates[1]
    ) / 1_000_000


def _total_tokens(input_tokens: float | None, output_tokens: float | None) -> float | None:
    if input_tokens is None or output_tokens is None:
        return None
    return input_tokens + output_tokens


def _pricing_label(backend: str, rates: tuple[float, float] | None) -> str:
    if backend == "ollama":
        return "Local inference; $0 API cost only. Compute and hardware costs excluded."
    if rates is None:
        return "API cost unknown; no token prices supplied."
    return f"Estimated from supplied input/output rates USD per million tokens: {rates}."


def _limitations(backend: str, has_usage: bool) -> list[str]:
    notes = [
        "Sequential projection scales the sample mean; no confidence interval is inferred.",
        "Retry fraction is explicit; observed failures do not set retries.",
        "Static cleanup, export, I/O, startup, concurrency, and hardware overhead are unmeasured.",
        "Benchmark failures and image-review counts describe the sample and are not extrapolated.",
    ]
    if not has_usage:
        notes.append(
            "Token totals are unavailable because usage was not reported for the full sample."
        )
    if backend == "ollama":
        notes.append("Zero API dollars do not include local compute or hardware cost.")
    notes.append("Projected time and cost do not establish output quality or operational approval.")
    return notes
