from __future__ import annotations

import json
from pathlib import Path

from congressional_globe.benchmarking import run_benchmark
from congressional_globe.models import CleanupResult, TextEdit
from congressional_globe.providers import ProviderResult


class FakeProvider:
    def __init__(self, results: list[ProviderResult]) -> None:
        self.results = iter(results)
        self.calls: list[str] = []

    def clean(self, text: str) -> ProviderResult:
        self.calls.append(text)
        return next(self.results)


def _result(text: str, *, usage: dict[str, int] | None = None) -> ProviderResult:
    edits = []
    if text == "Congrefs":
        edits = [
            TextEdit(
                start_char=6,
                end_char=7,
                expected="f",
                replacement="s",
                reason="long s OCR confusion",
                confidence=0.99,
            )
        ]
    return ProviderResult(
        cleanup=CleanupResult(edits=edits, needs_image_review=False, review_reason=None),
        raw_response='{"edits": []}',
        usage=usage or {},
    )


def test_benchmark_records_exact_agreement_controls_usage_and_summary(
    tmp_path: Path,
) -> None:
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {"id": "correction", "text_ocr": "Congrefs", "expected_text": "Congress"}
                ),
                json.dumps(
                    {"id": "control", "text_ocr": "unchanged", "expected_text": "unchanged"}
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    provider = FakeProvider(
        [
            _result("Congrefs", usage={"input_tokens": 7, "output_tokens": 3}),
            _result("unchanged"),
        ]
    )

    summary = run_benchmark(
        cases_path,
        provider,
        backend="ollama",
        model="benchmark-model",
        run_id="sample-1",
        artifacts_dir=tmp_path / "artifacts",
    )

    records = [
        json.loads(line)
        for line in (tmp_path / "artifacts/sample-1/results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert provider.calls == ["Congrefs", "unchanged"]
    assert summary.cases == 2 and summary.exact_matches == 2
    assert summary.total_input_tokens == 7 and summary.total_output_tokens == 3
    assert summary.unchanged_controls == 1 and summary.unchanged_control_errors == 0
    assert records[0]["normalized_text"] == "Congress"
    assert records[0]["validated_edits"][0]["replacement"] == "s"
    assert records[0]["usage"] == {"input_tokens": 7, "output_tokens": 3}
    assert records[1]["unchanged_control_error"] is False
    assert (
        json.loads((tmp_path / "artifacts/sample-1/summary.json").read_text(encoding="utf-8"))[
            "backend"
        ]
        == "ollama"
    )


def test_benchmark_keeps_raw_response_when_patch_validation_fails(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        json.dumps({"id": "bad", "text_ocr": "source", "expected_text": "target"}) + "\n",
        encoding="utf-8",
    )
    invalid = ProviderResult(
        cleanup=CleanupResult(
            edits=[
                TextEdit(
                    start_char=0,
                    end_char=3,
                    expected="wrong",
                    replacement="target",
                    reason="bad anchor",
                    confidence=0.5,
                )
            ],
            needs_image_review=False,
            review_reason=None,
        ),
        raw_response='{"raw": "kept"}',
        usage={},
    )

    summary = run_benchmark(
        cases_path,
        FakeProvider([invalid]),
        backend="openai",
        model="test-model",
        run_id="invalid-edit",
        limit=1,
        artifacts_dir=tmp_path / "artifacts",
    )

    record = json.loads(
        (tmp_path / "artifacts/invalid-edit/results.jsonl").read_text(encoding="utf-8")
    )
    assert summary.failed == 1 and summary.exact_matches == 0
    assert record["raw_response"] == '{"raw": "kept"}'
    assert record["error"].startswith("ValueError:")


def test_benchmark_counts_review_response_separately_and_keeps_usage(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        json.dumps({"id": "review", "text_ocr": "same", "expected_text": "same"}) + "\n",
        encoding="utf-8",
    )
    review_result = ProviderResult(
        cleanup=CleanupResult(
            edits=[], needs_image_review=True, review_reason="verify against scan"
        ),
        raw_response='{"needs_image_review": true}',
        usage={"input_tokens": 11, "output_tokens": 5},
    )

    summary = run_benchmark(
        cases_path,
        FakeProvider([review_result]),
        backend="ollama",
        model="test-model",
        run_id="review-needed",
        artifacts_dir=tmp_path / "artifacts",
    )

    record = json.loads(
        (tmp_path / "artifacts/review-needed/results.jsonl").read_text(encoding="utf-8")
    )
    assert summary.succeeded == 0 and summary.failed == 0
    assert summary.review_required == 1 and summary.exact_matches == 0
    assert summary.total_input_tokens == 11 and summary.total_output_tokens == 5
    assert record["needs_image_review"] is True
    assert record["review_reason"] == "verify against scan"
    assert record["raw_response"] == '{"needs_image_review": true}'
    assert record["usage"] == {"input_tokens": 11, "output_tokens": 5}


def test_benchmark_validates_limited_cases_before_calling_provider(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        "\n".join(
            [
                json.dumps({"id": "first", "text_ocr": "a", "expected_text": "a"}),
                json.dumps({"id": "first", "text_ocr": "b", "expected_text": "b"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    provider = FakeProvider([_result("a")])
    artifacts_dir = tmp_path / "artifacts"

    try:
        run_benchmark(
            cases_path,
            provider,
            backend="ollama",
            model="test-model",
            run_id="invalid-input",
            limit=2,
            artifacts_dir=artifacts_dir,
        )
    except ValueError as error:
        assert "duplicate benchmark case id" in str(error)
    else:
        raise AssertionError("duplicate cases should be rejected before provider requests")

    assert provider.calls == []
    assert not (artifacts_dir / "invalid-input").exists()
