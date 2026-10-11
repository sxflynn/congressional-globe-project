from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from congressional_globe import cleanup
from congressional_globe.models import CleanupResult, TextEdit
from congressional_globe.providers import ProviderResult
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
        "scan_leaf": leaf,
        "reading_order": 0,
        "line_ids": [],
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
