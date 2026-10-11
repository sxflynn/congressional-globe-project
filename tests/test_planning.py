from __future__ import annotations

import json
from pathlib import Path

import pytest

from congressional_globe.benchmarking import BenchmarkRecord, BenchmarkSummary
from congressional_globe.planning import estimate, load_summary


def _summary(backend: str = "openai", usage_cases: int | None = 4) -> BenchmarkSummary:
    return BenchmarkSummary(
        run_id="benchmark-1",
        backend=backend,
        model="test-model",
        cases_path="cases.jsonl",
        requested_limit=4,
        cases=4,
        usage_cases=usage_cases,
        succeeded=2,
        failed=1,
        review_required=1,
        exact_matches=2,
        unchanged_controls=0,
        unchanged_control_errors=0,
        total_input_tokens=400,
        total_output_tokens=200,
        total_duration_seconds=120,
        mean_duration_seconds=30,
    )


def test_cloud_estimate_uses_sample_rates_and_explicit_retry_fraction() -> None:
    projection = estimate(
        _summary(),
        jobs=100,
        input_usd_per_million=2,
        output_usd_per_million=4,
        retry_fraction=0.1,
    )

    assert projection.projected_requests == pytest.approx(110)
    assert projection.mean_input_tokens_per_request == 100
    assert projection.mean_output_tokens_per_request == 50
    assert projection.projected_total_tokens == pytest.approx(16_500)
    assert projection.sequential_hours == pytest.approx(110 * 30 / 3600)
    assert projection.projected_api_usd == pytest.approx(0.044)
    assert projection.realized_sample_api_usd == pytest.approx(0.0016)
    assert projection.sample_failed == 1 and projection.sample_review_required == 1
    assert "not approval" in projection.quality_status
    assert any("quality" in limitation for limitation in projection.limitations)


def test_local_estimate_cost_is_zero_and_usage_can_be_unavailable() -> None:
    projection = estimate(_summary("ollama", usage_cases=0), jobs=5)

    assert projection.projected_api_usd == 0
    assert projection.realized_sample_api_usd == 0
    assert projection.projected_total_tokens is None
    assert projection.sequential_days == pytest.approx(150 / 86400)


def test_cloud_estimate_rejects_partial_usage_and_unknown_cost_stays_unknown() -> None:
    with pytest.raises(ValueError, match="every benchmark case"):
        estimate(_summary(usage_cases=3), jobs=3)

    projection = estimate(_summary(), jobs=3)
    assert projection.projected_api_usd is None
    assert projection.realized_sample_api_usd is None
    assert "unknown" in projection.pricing


def test_estimate_rejects_empty_sample_and_partial_rates() -> None:
    with pytest.raises(ValueError, match="empty"):
        estimate(_summary().model_copy(update={"cases": 0}), jobs=1)
    with pytest.raises(ValueError, match="both input and output"):
        estimate(_summary(), jobs=1, input_usd_per_million=1)


def test_load_summary_recovers_usage_coverage_from_adjacent_records(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.json"
    old_summary = _summary().model_dump(exclude={"usage_cases"})
    summary_path.write_text(json.dumps(old_summary), encoding="utf-8")
    records = [
        BenchmarkRecord(
            case_id=f"case-{index}",
            raw_response="{}",
            duration_seconds=1,
            usage={"input_tokens": 100, "output_tokens": 50},
        )
        for index in range(4)
    ]
    (tmp_path / "results.jsonl").write_text(
        "".join(record.model_dump_json() + "\n" for record in records), encoding="utf-8"
    )

    summary = load_summary(summary_path)

    assert summary.usage_cases == 4
    projection = estimate(summary, jobs=2, input_usd_per_million=1, output_usd_per_million=1)
    assert projection.projected_api_usd == pytest.approx(0.0003)
    assert projection.realized_sample_api_usd == pytest.approx(0.0006)
