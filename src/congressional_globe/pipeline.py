"""Local pipeline orchestration; all transformations are explicit commands."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from congressional_globe.chunking import chunk_page
from congressional_globe.extraction import iter_pages, load_page_map
from congressional_globe.inventory import PARTS, SourceFile, inventory
from congressional_globe.models import PageRecord


def write_inventory(root: Path, destination: Path, include_hashes: bool) -> None:
    report = inventory(root, include_hashes)
    serializable = {
        identifier: {
            suffix: _source_file_payload(source_file) for suffix, source_file in derivatives.items()
        }
        for identifier, derivatives in report.items()
    }
    _write_json(destination, serializable)


def extract_identifier(root: Path, destination: Path, identifier: str) -> tuple[Path, Path]:
    hocr_path = root / f"{identifier}_hocr.html"
    map_path = root / f"{identifier}_page_numbers.json"
    page_path = destination / f"{identifier}_pages.jsonl"
    paragraph_path = destination / f"{identifier}_paragraphs.jsonl"
    destination.mkdir(parents=True, exist_ok=True)
    page_map = load_page_map(map_path)
    with (
        page_path.open("w", encoding="utf-8") as pages,
        paragraph_path.open("w", encoding="utf-8") as paragraphs,
    ):
        for page in iter_pages(hocr_path, page_map):
            _write_line(pages, page.model_dump(mode="json"))
            for paragraph in page.paragraphs:
                _write_line(paragraphs, _paragraph_payload(page, paragraph.model_dump(mode="json")))
    return page_path, paragraph_path


def build_rag(root: Path, artifact_root: Path, run_id: str, single_json: bool) -> Path:
    run_directory = artifact_root / run_id
    pages_directory = run_directory / "pages"
    chunks_path = run_directory / "chunks.jsonl"
    run_directory.mkdir(parents=True, exist_ok=True)
    page_paths = [extract_identifier(root, pages_directory, identifier)[0] for identifier in PARTS]
    _write_chunks(page_paths, chunks_path)
    _write_manifest(run_directory, page_paths, chunks_path)
    if single_json:
        _write_single_json(run_directory / "corpus.json", page_paths)
    return run_directory


def _write_chunks(page_paths: list[Path], chunks_path: Path) -> None:
    with chunks_path.open("w", encoding="utf-8") as target:
        for page_path in page_paths:
            _write_chunks_from_page_file(target, page_path)


def _write_chunks_from_page_file(target: Any, page_path: Path) -> None:
    for payload in _read_jsonl(page_path):
        page = PageRecord.model_validate(payload)
        for chunk in chunk_page(page):
            _write_line(target, chunk.model_dump(mode="json"))


def _write_manifest(run_directory: Path, page_paths: list[Path], chunks_path: Path) -> None:
    payload = {
        "schema_version": "0.1.0",
        "title": "The Congressional Globe",
        "congress": 39,
        "session": 1,
        "parts": [
            {"identifier": identifier, "part_number": part} for identifier, part in PARTS.items()
        ],
        "page_files": [str(path.relative_to(run_directory)) for path in page_paths],
        "chunks_file": str(chunks_path.relative_to(run_directory)),
        "raw_metadata_policy": "Preserve Internet Archive metadata separately and unchanged.",
    }
    _write_json(run_directory / "session_manifest.json", payload)


def _write_single_json(destination: Path, page_paths: list[Path]) -> None:
    with destination.open("w", encoding="utf-8") as target:
        target.write('{"schema_version":"0.1.0","pages":[\n')
        first = True
        for page_path in page_paths:
            first = _write_page_file(target, page_path, first)
        target.write("]}\n")


def _write_page_file(target: Any, page_path: Path, first: bool) -> bool:
    for payload in _read_jsonl(page_path):
        if not first:
            target.write(",\n")
        json.dump(payload, target, ensure_ascii=False, separators=(",", ":"))
        first = False
    return first


def _paragraph_payload(page: PageRecord, paragraph: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_identifier": page.item_identifier,
        "part_number": page.part_number,
        "scan_leaf": page.scan_leaf,
        "printed_page": page.printed_page.model_dump(mode="json"),
        "hocr_page_id": page.hocr_page_id,
        **paragraph,
    }


def _source_file_payload(source_file: SourceFile | None) -> dict[str, object] | None:
    if source_file is None:
        return None
    return {
        "path": str(source_file.path),
        "size_bytes": source_file.size_bytes,
        "sha256": source_file.sha256,
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_line(target: Any, payload: object) -> None:
    target.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def _read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        for line in source:
            if line.strip():
                yield json.loads(line)
