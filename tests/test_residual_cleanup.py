from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest
from openai import APIConnectionError

from congressional_globe import cleanup
from congressional_globe.models import CleanupResult, TextEdit
from congressional_globe.providers import ProviderOutputError, ProviderResult
from congressional_globe.storage import (
    claim_next,
    complete_job,
    create_run,
    jobs_for_run,
    progress,
)


class _Provider:
    def __init__(self, result: ProviderResult) -> None:
        self.result = result
        self.inputs: list[str] = []

    def clean(self, text: str) -> ProviderResult:
        self.inputs.append(text)
        return self.result


def _static_row(item: str = "part-a", leaf: int = 4, paragraph_id: str = "p1") -> dict[str, object]:
    static_edit = TextEdit(
        start_char=0,
        end_char=3,
        expected="raw",
        replacement="static",
        reason="fixture static edit",
        confidence=1,
    )
    return {
        "id": paragraph_id,
        "item_identifier": item,
        "part_number": 1,
        "scan_leaf": leaf,
        "printed_page": {"detected": "12", "inferred": None, "source": "direct_header"},
        "hocr_page_id": f"page_{leaf:06d}",
        "reading_order": 0,
        "line_ids": [f"line_{leaf:06d}_000001"],
        "bbox": {"left": 10, "top": 20, "right": 30, "bottom": 40},
        "text_ocr": "raw",
        "text_normalized": "static",
        "static_edits": [static_edit.model_dump(mode="json")],
    }


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _ai_result(needs_review: bool = False) -> ProviderResult:
    edit = TextEdit(
        start_char=0,
        end_char=6,
        expected="static",
        replacement="final",
        reason="fixture AI patch",
        confidence=0.9,
    )
    cleanup_result = CleanupResult(
        edits=[edit],
        needs_image_review=needs_review,
        review_reason="inspect scan" if needs_review else None,
    )
    return ProviderResult(
        cleanup_result, '{"raw":"response"}', {"input_tokens": 7, "output_tokens": 3}
    )


def _run_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider: _Provider
) -> tuple[Path, str]:
    run_directory = tmp_path / "run"
    run_id = "run-1"
    paragraphs = tmp_path / "static.jsonl"
    _write_rows(paragraphs, [_static_row()])
    assert create_run(cleanup.run_database(run_directory), run_id, paragraphs) == 1
    monkeypatch.setattr(cleanup, "_provider", lambda *_args: provider)
    cleanup.run_jobs(run_directory, run_id, "ollama", "fixture", 1, "http://localhost", 100)
    return run_directory, run_id


def test_queue_uses_static_text_and_composite_identity(tmp_path: Path) -> None:
    paragraphs = tmp_path / "static.jsonl"
    _write_rows(
        paragraphs,
        [_static_row("part-a", 4), _static_row("part-b", 4), _static_row("part-a", 5)],
    )
    database = tmp_path / "jobs.sqlite"

    assert create_run(database, "run-1", paragraphs) == 3
    jobs = jobs_for_run(database, "run-1")

    assert len({job.id for job in jobs}) == 3
    assert {job.source_text for job in jobs} == {"static"}
    assert {json.loads(job.source_json)["text_ocr"] for job in jobs} == {"raw"}
    assert len({job.identity for job in jobs}) == 3
    assert all(job.input_hash == hashlib.sha256(b"static").hexdigest() for job in jobs)


def test_completed_ai_result_materializes_against_static_input(tmp_path: Path, monkeypatch) -> None:
    provider = _Provider(_ai_result())
    run_directory, run_id = _run_provider(tmp_path, monkeypatch, provider)
    static_path = tmp_path / "static.jsonl"
    output = tmp_path / "combined.jsonl"
    _write_rows(static_path, [_static_row()])

    assert provider.inputs == ["static"]
    assert cleanup.materialize_all(run_directory, run_id, static_path, output) == 1
    result = json.loads(output.read_text(encoding="utf-8"))

    assert result["text_ocr"] == "raw"
    assert result["static_edits"][0]["expected"] == "raw"
    assert result["text_normalized"] == "final"
    assert result["ai_input_text"] == "static"
    assert result["ai_input_sha256"] == hashlib.sha256(b"static").hexdigest()
    assert result["ai_edits"][0]["expected"] == "static"
    assert result["cleanup_status"] == "completed"
    assert result["ai_provenance"]["model_identity"] == "ollama:fixture"
    assert result["ai_provenance"]["usage"] == {"input_tokens": 7, "output_tokens": 3}
    assert result["ai_provenance"]["edit_ledger"][0]["stage"] == "static"
    job = jobs_for_run(cleanup.run_database(run_directory), run_id)[0]
    assert job.raw_response == '{"raw":"response"}'
    assert json.loads(job.usage_json or "{}") == {"input_tokens": 7, "output_tokens": 3}
    events = [
        json.loads(line)
        for line in (run_directory / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    result_event = next(event for event in events if event["event"] == "job_result")
    assert result_event["run_id"] == run_id
    assert result_event["identity"] == job.identity
    assert result_event["status"] == "completed"
    assert result_event["before_text"] == "static"
    assert result_event["after_text"] == "final"
    assert result_event["after_text_kind"] == "accepted_normalized"
    assert result_event["applied_edits"][0]["replacement"] == "final"


def test_provider_parse_failure_persists_raw_usage_and_review_result_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paragraphs = tmp_path / "static.jsonl"
    _write_rows(paragraphs, [_static_row()])
    run_directory = tmp_path / "run"
    run_id = "parse-failure"
    database = cleanup.run_database(run_directory)
    create_run(database, run_id, paragraphs)

    class MalformedProvider:
        def clean(self, text: str) -> ProviderResult:
            raise ProviderOutputError(
                "invalid provider JSON",
                raw_response='{"edits":',
                usage={"input_tokens": 19, "output_tokens": 6},
                finish_reason="length",
                output_status=None,
            )

    monkeypatch.setattr(cleanup, "_provider", lambda *_args: MalformedProvider())
    cleanup.run_jobs(run_directory, run_id, "ollama", "fixture", 1, "http://localhost", 100)

    job = jobs_for_run(database, run_id)[0]
    assert job.status == "review"
    assert job.raw_response == '{"edits":'
    assert json.loads(job.usage_json or "{}") == {"input_tokens": 19, "output_tokens": 6}
    assert (run_directory / "responses" / f"{job.id}.json").read_text(
        encoding="utf-8"
    ) == '{"edits":'
    events = [
        json.loads(line)
        for line in (run_directory / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    result_event = next(event for event in events if event["event"] == "job_result")
    assert result_event["status"] == "review"
    assert result_event["before_text"] == "static"
    assert result_event["after_text"] == "static"
    assert result_event["after_text_kind"] == "unchanged_retained_input"
    assert result_event["applied_edits"] == []
    assert result_event["raw_response"] == '{"edits":'
    assert result_event["finish_reason"] == "length"
    assert result_event["usage"] == {"input_tokens": 19, "output_tokens": 6}


def test_image_review_response_is_not_completed_and_materializes_static(tmp_path, monkeypatch):
    provider = _Provider(_ai_result(needs_review=True))
    run_directory, run_id = _run_provider(tmp_path, monkeypatch, provider)
    job = jobs_for_run(cleanup.run_database(run_directory), run_id)[0]

    assert progress(cleanup.run_database(run_directory), run_id)["review"] == 1
    assert job.status == "review"
    assert job.raw_response == '{"raw":"response"}'
    assert json.loads(job.usage_json or "{}") == {"input_tokens": 7, "output_tokens": 3}


def test_live_worker_lock_prevents_claim_recovery(tmp_path: Path, monkeypatch):
    provider = _Provider(_ai_result())
    run_directory = tmp_path / "run"
    run_id = "run-1"
    paragraphs = tmp_path / "static.jsonl"
    _write_rows(paragraphs, [_static_row()])
    database = cleanup.run_database(run_directory)
    create_run(database, run_id, paragraphs)
    claimed = claim_next(database, run_id, "ollama", "fixture")
    assert claimed is not None
    monkeypatch.setattr(cleanup, "_provider", lambda *_args: provider)

    with (
        cleanup._worker_lock(run_directory, run_id),
        pytest.raises(RuntimeError, match="already holds"),
    ):
        cleanup.run_jobs(run_directory, run_id, "ollama", "fixture", 1, "http://localhost", 100)

    assert progress(database, run_id)["claimed"] == 1
    assert provider.inputs == []


def test_materializer_keeps_pending_static_row(tmp_path: Path) -> None:
    run_directory = tmp_path / "run"
    run_id = "run-1"
    static_path = tmp_path / "static.jsonl"
    output = tmp_path / "combined.jsonl"
    _write_rows(static_path, [_static_row()])
    create_run(cleanup.run_database(run_directory), run_id, static_path)

    assert cleanup.materialize_all(run_directory, run_id, static_path, output) == 1
    result = json.loads(output.read_text(encoding="utf-8"))

    assert result["text_normalized"] == "static"
    assert result["cleanup_status"] == "pending"


def test_materializer_matches_repeated_paragraph_ids_by_composite_identity(
    tmp_path: Path, monkeypatch
) -> None:
    provider = _Provider(_ai_result())
    run_directory = tmp_path / "run"
    run_id = "run-1"
    queued = tmp_path / "queued.jsonl"
    _write_rows(queued, [_static_row("part-a", 4), _static_row("part-b", 4)])
    create_run(cleanup.run_database(run_directory), run_id, queued)
    monkeypatch.setattr(cleanup, "_provider", lambda *_args: provider)
    cleanup.run_jobs(run_directory, run_id, "ollama", "fixture", 1, "http://localhost", 100)
    static_path = tmp_path / "static.jsonl"
    output = tmp_path / "combined.jsonl"
    _write_rows(static_path, [_static_row("part-a", 4), _static_row("part-b", 4)])

    cleanup.materialize_all(run_directory, run_id, static_path, output)
    results = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

    assert [row["cleanup_status"] for row in results] == ["completed", "pending"]
    assert results[0]["text_normalized"] == "final"
    assert results[1]["text_normalized"] == "static"


def test_materializer_preserves_empty_static_normalized_text(tmp_path: Path) -> None:
    run_directory = tmp_path / "run"
    run_id = "run-1"
    static_path = tmp_path / "static.jsonl"
    output = tmp_path / "combined.jsonl"
    row = {**_static_row(), "text_ocr": "raw", "text_normalized": "", "static_edits": []}
    _write_rows(static_path, [row])
    create_run(cleanup.run_database(run_directory), run_id, static_path)

    cleanup.materialize_all(run_directory, run_id, static_path, output)
    result = json.loads(output.read_text(encoding="utf-8"))

    assert result["text_normalized"] == ""
    assert result["cleanup_status"] == "pending"


def test_run_jobs_does_not_retry_connection_failure_in_same_drain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paragraphs = tmp_path / "static.jsonl"
    _write_rows(paragraphs, [_static_row("part-a", 4), _static_row("part-b", 4)])
    run_directory = tmp_path / "run"
    run_id = "run-1"
    database = cleanup.run_database(run_directory)
    create_run(database, run_id, paragraphs)

    class FailingProvider:
        calls = 0

        def clean(self, text: str) -> ProviderResult:
            self.calls += 1
            raise APIConnectionError(message="offline", request=cast(Any, None))

    provider = FailingProvider()
    monkeypatch.setattr(cleanup, "_provider", lambda *_args: provider)

    cleanup.run_jobs(run_directory, run_id, "ollama", "fixture", 10, "http://localhost", 100)

    jobs = jobs_for_run(database, run_id)
    assert provider.calls == 1
    assert sorted(job.attempts for job in jobs) == [0, 1]
    assert progress(database, run_id)["pending"] == 2
    events = [
        json.loads(line)
        for line in (run_directory / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    result_event = next(event for event in events if event["event"] == "job_result")
    assert result_event["status"] == "retry_pending"
    assert result_event["before_text"] == result_event["after_text"] == "static"
    assert result_event["after_text_kind"] == "unchanged_retained_input"
    assert result_event["applied_edits"] == []


def test_noop_completion_records_unchanged_text_and_source_citation(tmp_path: Path, monkeypatch):
    row = {
        **_static_row(),
        "text_ocr": "unchanged",
        "text_normalized": "unchanged",
        "static_edits": [],
    }
    paragraphs = tmp_path / "static.jsonl"
    _write_rows(paragraphs, [row])
    run_directory = tmp_path / "run"
    run_id = "noop-result"
    database = cleanup.run_database(run_directory)
    create_run(database, run_id, paragraphs)
    result = ProviderResult(
        CleanupResult(edits=[], needs_image_review=False, review_reason=None),
        '{"edits":[]}',
        {"input_tokens": 5, "output_tokens": 2},
    )
    monkeypatch.setattr(cleanup, "_provider", lambda *_args: _Provider(result))

    cleanup.run_jobs(run_directory, run_id, "ollama", "fixture", 1, "http://localhost", 100)

    events = [
        json.loads(line)
        for line in (run_directory / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    result_event = next(event for event in events if event["event"] == "job_result")
    assert result_event["before_text"] == result_event["after_text"] == "unchanged"
    assert result_event["after_text_kind"] == "accepted_normalized"
    assert result_event["applied_edits"] == []
    assert result_event["printed_page"]["detected"] == "12"
    assert result_event["hocr_page_id"] == "page_000004"
    assert result_event["line_ids"] == ["line_000004_000001"]
    assert result_event["bbox"] == {"left": 10, "top": 20, "right": 30, "bottom": 40}


def test_run_jobs_does_not_claim_after_wall_clock_budget(tmp_path: Path, monkeypatch):
    rows = [_static_row("part-a", 4, f"p{index}") for index in range(3)]
    paragraphs = tmp_path / "static.jsonl"
    _write_rows(paragraphs, rows)
    run_directory = tmp_path / "run"
    run_id = "run-1"
    database = cleanup.run_database(run_directory)
    create_run(database, run_id, paragraphs)
    now = [0.0]
    claims = 0
    real_claim = cleanup.claim_next

    def claim(*args):
        nonlocal claims
        claims += 1
        return real_claim(*args)

    def finish_request(*_args):
        now[0] = 5.0
        return True

    monkeypatch.setattr(cleanup, "perf_counter", lambda: now[0])
    monkeypatch.setattr(cleanup, "claim_next", claim)
    monkeypatch.setattr(cleanup, "_provider", lambda *_args: object())
    monkeypatch.setattr(cleanup, "_process_job", finish_request)

    cleanup.run_jobs(run_directory, run_id, "ollama", "fixture", 10, "http://localhost", 100, 5)

    assert claims == 1
    assert progress(database, run_id)["pending"] == 2


def test_rejected_punctuation_edit_routes_entire_response_to_review(tmp_path: Path, monkeypatch):
    row = {**_static_row(), "text_ocr": "an, ihc", "text_normalized": "an, ihc", "static_edits": []}
    paragraphs = tmp_path / "static.jsonl"
    _write_rows(paragraphs, [row])
    run_directory = tmp_path / "run"
    run_id = "run-1"
    database = cleanup.run_database(run_directory)
    create_run(database, run_id, paragraphs)
    result = ProviderResult(
        CleanupResult(
            edits=[
                TextEdit(
                    start_char=0,
                    end_char=3,
                    expected="an,",
                    replacement="an",
                    reason="fixture punctuation change",
                    confidence=0.9,
                ),
                TextEdit(
                    start_char=4,
                    end_char=7,
                    expected="ihc",
                    replacement="the",
                    reason="fixture OCR correction",
                    confidence=0.9,
                ),
            ],
            needs_image_review=False,
            review_reason=None,
        ),
        '{"raw":"response"}',
        {"input_tokens": 2, "output_tokens": 2},
    )
    monkeypatch.setattr(cleanup, "_provider", lambda *_args: _Provider(result))

    cleanup.run_jobs(run_directory, run_id, "ollama", "fixture", 1, "http://localhost", 100)

    job = jobs_for_run(database, run_id)[0]
    assert job.status == "review"
    assert "punctuation-only" in (job.error or "")
    assert job.raw_response == '{"raw":"response"}'


def test_materializer_moves_legacy_unsafe_completed_job_to_review(tmp_path: Path):
    row = {**_static_row(), "text_ocr": "an,", "text_normalized": "an,", "static_edits": []}
    static_path = tmp_path / "static.jsonl"
    _write_rows(static_path, [row])
    run_directory = tmp_path / "run"
    run_id = "run-1"
    database = cleanup.run_database(run_directory)
    create_run(database, run_id, static_path)
    job = claim_next(database, run_id, "ollama", "legacy")
    assert job is not None
    edit = TextEdit(
        start_char=0,
        end_char=3,
        expected="an,",
        replacement="an",
        reason="legacy punctuation edit",
        confidence=0.9,
    )
    complete_job(
        database,
        job.id,
        {
            "cleanup": CleanupResult(
                edits=[edit], needs_image_review=False, review_reason=None
            ).model_dump(mode="json"),
            "applied_edits": [edit.model_dump(mode="json")],
            "text_normalized": "an",
        },
        3,
        raw_response="legacy raw response",
    )
    output = tmp_path / "combined.jsonl"

    cleanup.materialize_all(run_directory, run_id, static_path, output)

    result = json.loads(output.read_text(encoding="utf-8"))
    refreshed = jobs_for_run(database, run_id)[0]
    assert result["text_normalized"] == "an,"
    assert result["cleanup_status"] == "review"
    assert "punctuation-only" in result["context"]["model_review_reason"]
    assert refreshed.status == "review"
    assert refreshed.raw_response == "legacy raw response"
    assert refreshed.result_json is not None


def test_materializer_keeps_existing_output_on_invalid_input(tmp_path: Path):
    run_directory = tmp_path / "run"
    run_id = "run-1"
    static_path = tmp_path / "static.jsonl"
    output = tmp_path / "combined.jsonl"
    static_path.write_text("not-json\n", encoding="utf-8")
    output.write_text("existing\n", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        cleanup.materialize_all(run_directory, run_id, static_path, output)

    assert output.read_text(encoding="utf-8") == "existing\n"


def test_materializer_rejects_static_input_alias(tmp_path: Path) -> None:
    static_path = tmp_path / "static.jsonl"
    _write_rows(static_path, [_static_row()])
    with pytest.raises(ValueError, match="must differ"):
        cleanup.materialize_all(tmp_path / "run", "run-1", static_path, static_path)


def test_storage_refuses_to_complete_image_review_result(tmp_path: Path) -> None:
    paragraphs = tmp_path / "static.jsonl"
    _write_rows(paragraphs, [_static_row()])
    database = cleanup.run_database(tmp_path / "run")
    create_run(database, "run-1", paragraphs)
    job = claim_next(database, "run-1", "ollama", "fixture")
    assert job is not None
    result = {"cleanup": _ai_result(needs_review=True).cleanup.model_dump(mode="json")}

    with pytest.raises(ValueError, match="cannot be completed"):
        complete_job(database, job.id, result, 1)
