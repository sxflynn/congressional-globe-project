"""Focused orchestration tests that never call a provider."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from congressional_globe import workflow
from congressional_globe.inventory import PARTS
from congressional_globe.models import PageRecord, ParagraphRecord


def test_plan_only_prepares_all_parts_and_writes_residuals_without_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, lexicon = _source_fixture(tmp_path)
    output_root = tmp_path / "artifacts" / "runs"
    monkeypatch.setattr(workflow, "load_page_map", lambda _path: {})
    monkeypatch.setattr(workflow, "iter_pages", lambda path, _map: iter([_page(path.stem)]))
    monkeypatch.setattr(workflow, "classify_page", lambda page: page)
    monkeypatch.setattr(
        workflow, "needs_model", lambda paragraph: paragraph.id.endswith("-residual")
    )
    monkeypatch.setattr(
        workflow.cleanup,
        "run_jobs",
        lambda *args, **kwargs: pytest.fail("plan-only mode called a provider"),
    )

    report = workflow.run_static_first(
        root, "plan", lexicon, output_root=output_root, plan_only=True
    )

    assert report["scope"] == "plan_only"
    assert report["pages"] == len(PARTS)
    assert report["paragraphs"] == len(PARTS) * 2
    assert report["residual_paragraphs"] == len(PARTS)
    assert len(report["parts"]) == 5
    run_dir = output_root / "plan"
    assert (run_dir / "static_paragraphs.jsonl").is_file()
    assert len(_jsonl(run_dir / "residual_paragraphs.jsonl")) == len(PARTS)
    manifest = json.loads((run_dir / "workflow_manifest.json").read_text(encoding="utf-8"))
    assert all(part["metadata_raw_status"] == "not_available" for part in manifest["parts"])
    assert manifest["stages"]["residual_routing"] == "complete"
    assert not (run_dir / "jobs.sqlite").exists()


def test_backend_none_materializes_pending_static_rows_without_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, lexicon = _source_fixture(tmp_path)
    output_root = tmp_path / "runs"
    monkeypatch.setattr(workflow, "load_page_map", lambda _path: {})
    monkeypatch.setattr(workflow, "iter_pages", lambda path, _map: iter([_page(path.stem)]))
    monkeypatch.setattr(workflow, "classify_page", lambda page: page)
    monkeypatch.setattr(
        workflow, "needs_model", lambda paragraph: paragraph.id.endswith("-residual")
    )
    monkeypatch.setattr(
        workflow.cleanup,
        "run_jobs",
        lambda *args, **kwargs: pytest.fail("backend none invoked a provider"),
    )

    report = workflow.run_static_first(root, "no-ai", lexicon, output_root=output_root)

    assert report["queue_created"] is True
    assert report["pending"] == len(PARTS)
    assert report["cleanup_complete"] is False
    run_dir = output_root / "no-ai"
    assert (run_dir / "jobs.sqlite").is_file()
    assert (run_dir / "canonical_pages.jsonl").is_file()
    output_records = _jsonl(run_dir / "normalized.jsonl")
    assert sum(record.get("cleanup_status") == "pending" for record in output_records) == len(PARTS)


def test_resume_rejects_changed_lexicon_or_page_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, lexicon = _source_fixture(tmp_path)
    output_root = tmp_path / "artifacts" / "runs"
    monkeypatch.setattr(workflow, "load_page_map", lambda _path: {})
    monkeypatch.setattr(workflow, "iter_pages", lambda path, _map: iter([_page(path.stem)]))
    monkeypatch.setattr(workflow, "classify_page", lambda page: page)
    monkeypatch.setattr(workflow, "needs_model", lambda _paragraph: False)
    workflow.run_static_first(root, "stable", lexicon, output_root=output_root, page_limit=1)

    with pytest.raises(ValueError, match="different root, lexicon, or page limit"):
        workflow.run_static_first(root, "stable", lexicon, output_root=output_root, page_limit=2)

    lexicon.write_text("different\n", encoding="utf-8")
    with pytest.raises(ValueError, match="different root, lexicon, or page limit"):
        workflow.run_static_first(root, "stable", lexicon, output_root=output_root, page_limit=1)


def test_ai_execution_requires_explicit_model(tmp_path: Path) -> None:
    root, lexicon = _source_fixture(tmp_path)

    with pytest.raises(ValueError, match="explicit model"):
        workflow.run_static_first(
            root,
            "invalid",
            lexicon,
            output_root=tmp_path / "runs",
            backend="openai",
            model=None,
            ai_limit=1,
        )


def test_bounded_ai_run_keeps_pending_jobs_and_writes_static_canonical_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, lexicon = _source_fixture(tmp_path)
    output_root = tmp_path / "artifacts" / "runs"
    calls: list[tuple[str, str, int]] = []
    monkeypatch.setattr(workflow, "load_page_map", lambda _path: {})
    monkeypatch.setattr(workflow, "iter_pages", lambda path, _map: iter([_page(path.stem)]))
    monkeypatch.setattr(workflow, "classify_page", lambda page: page)
    monkeypatch.setattr(
        workflow, "needs_model", lambda paragraph: paragraph.id.endswith("-residual")
    )
    monkeypatch.setattr(
        workflow.cleanup,
        "run_jobs",
        lambda directory, run_id, backend, model, limit, *_args: calls.append(
            (backend, model, limit)
        ),
    )

    report = workflow.run_static_first(
        root,
        "bounded",
        lexicon,
        output_root=output_root,
        backend="ollama",
        model="stub-model",
        ai_limit=2,
    )

    assert calls == [("ollama", "stub-model", 2)]
    assert report["queue_created"] is True
    assert report["pending"] == len(PARTS)
    assert report["cleanup_complete"] is False
    run_dir = output_root / "bounded"
    assert (run_dir / "canonical_pages.jsonl").is_file()
    assert (run_dir / "chunks.jsonl").is_file()
    normalized = _jsonl(run_dir / "normalized.jsonl")
    assert all("cleanup_status" in record for record in normalized)


def _source_fixture(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "source"
    root.mkdir()
    for identifier in PARTS:
        (root / f"{identifier}_hocr.html").write_text("placeholder", encoding="utf-8")
        (root / f"{identifier}_djvu.xml").write_text("placeholder", encoding="utf-8")
        (root / f"{identifier}_page_numbers.json").write_text(
            json.dumps({"pages": []}), encoding="utf-8"
        )
    lexicon = tmp_path / "lexicon.txt"
    lexicon.write_text("body\n", encoding="utf-8")
    return root, lexicon


def _page(identifier: str) -> PageRecord:
    paras = [
        _paragraph(f"{identifier}-body", "plain text"),
        _paragraph(f"{identifier}-residual", "uncertain-text"),
    ]
    return PageRecord(
        id=f"ia:{identifier}:leaf:1",
        item_identifier=identifier,
        part_number=PARTS[identifier.removesuffix("_hocr")],
        scan_leaf=1,
        hocr_page_id="page_000001",
        printed_page={"detected": "1"},
        text_ocr="\n\n".join(paragraph.text_ocr for paragraph in paras),
        paragraphs=paras,
    )


def _paragraph(identifier: str, text: str) -> ParagraphRecord:
    return ParagraphRecord(id=identifier, reading_order=0, line_ids=[], text_ocr=text)


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
