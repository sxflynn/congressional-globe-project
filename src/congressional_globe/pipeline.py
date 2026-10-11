"""Local pipeline orchestration; all transformations are explicit commands."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any

from congressional_globe.chunking import chunk_page
from congressional_globe.extraction import iter_pages, load_page_map
from congressional_globe.inventory import PARTS, SourceFile, inventory
from congressional_globe.models import PageRecord, ParagraphRecord
from congressional_globe.normalization import apply_edits


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


def build_rag_from_pages(pages_path: Path, chunks_path: Path, max_characters: int = 4_000) -> int:
    """Build page-bounded RAG JSONL from an existing canonical pages JSONL."""
    chunks_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with chunks_path.open("w", encoding="utf-8") as target:
        for payload in _read_jsonl(pages_path):
            page = PageRecord.model_validate(payload)
            for chunk in chunk_page(page, max_characters):
                _write_line(target, chunk.model_dump(mode="json"))
                count += 1
    return count


def merge_normalized_paragraphs(pages_path: Path, normalized_path: Path, output_path: Path) -> int:
    """Merge complete normalized paragraph JSONL into pages, preserving OCR and ledgers."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _reject_output_aliases(pages_path, normalized_path, output_path)
    temporary_path = _temporary_output(output_path)
    with TemporaryDirectory(prefix="globe-merge-") as temporary:
        try:
            database = Path(temporary) / "paragraphs.sqlite"
            _index_normalized_paragraphs(database, normalized_path)
            page_count = _merge_pages(database, pages_path, temporary_path)
            _reject_unmatched_paragraphs(database)
            os.replace(temporary_path, output_path)
        finally:
            temporary_path.unlink(missing_ok=True)
    return page_count


def _reject_output_aliases(pages: Path, normalized: Path, output: Path) -> None:
    for source in (pages, normalized):
        same_path = source.resolve() == output.resolve()
        same_file = source.exists() and output.exists() and os.path.samefile(source, output)
        if same_path or same_file:
            raise ValueError(f"Output path aliases an input file: {source}")


def _temporary_output(output: Path) -> Path:
    with NamedTemporaryFile(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent) as temp:
        return Path(temp.name)


def _index_normalized_paragraphs(database: Path, normalized_path: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE normalized (item TEXT, leaf INTEGER, paragraph TEXT, "
            "text_ocr TEXT, text_normalized TEXT, payload TEXT, "
            "PRIMARY KEY (item, leaf, paragraph))"
        )
        for payload in _read_jsonl(normalized_path):
            paragraph = _validated_normalized(payload)
            identity = _paragraph_identity(payload)
            try:
                connection.execute(
                    "INSERT INTO normalized VALUES (?, ?, ?, ?, ?, ?)",
                    (*identity, paragraph.text_ocr, paragraph.text_normalized, json.dumps(payload)),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError(f"Duplicate normalized paragraph identity: {identity}") from error


def _validated_normalized(payload: dict[str, Any]):
    fields = {key: value for key, value in payload.items() if key in ParagraphRecord.model_fields}
    paragraph = ParagraphRecord.model_validate(fields)
    if paragraph.text_normalized is None:
        raise ValueError(f"Normalized text is missing for paragraph {paragraph.id}")
    return paragraph


def _paragraph_identity(payload: dict[str, Any]) -> tuple[str, int, str]:
    required = ("item_identifier", "scan_leaf", "id")
    try:
        item, leaf, paragraph = (payload[key] for key in required)
    except KeyError as error:
        raise ValueError(
            f"Normalized paragraph is missing identity field: {error.args[0]}"
        ) from error
    return str(item), int(leaf), str(paragraph)


def _merge_pages(database: Path, pages_path: Path, output_path: Path) -> int:
    count = 0
    with sqlite3.connect(database) as connection, output_path.open("w", encoding="utf-8") as target:
        for payload in _read_jsonl(pages_path):
            page = PageRecord.model_validate(payload)
            paragraphs = _merge_page_paragraphs(connection, page)
            text_normalized = "\n\n".join(paragraph["text_normalized"] for paragraph in paragraphs)
            merged = PageRecord.model_validate(
                {**payload, "paragraphs": paragraphs, "text_normalized": text_normalized}
            )
            _write_line(target, merged.model_dump(mode="json"))
            count += 1
    return count


def _merge_page_paragraphs(
    connection: sqlite3.Connection, page: PageRecord
) -> list[dict[str, Any]]:
    return [_merge_paragraph(connection, page, paragraph) for paragraph in page.paragraphs]


def _merge_paragraph(
    connection: sqlite3.Connection, page: PageRecord, paragraph: ParagraphRecord
) -> dict[str, Any]:
    identity = (page.item_identifier, page.scan_leaf, paragraph.id)
    row = _lookup_normalized(connection, identity)
    if row[0] != paragraph.text_ocr:
        raise ValueError(f"Raw OCR mismatch for normalized paragraph: {identity}")
    derived = json.loads(row[2])
    merged = _normalized_paragraph(paragraph, derived, row[1], identity)
    connection.execute(
        "DELETE FROM normalized WHERE item = ? AND leaf = ? AND paragraph = ?", identity
    )
    return merged.model_dump(mode="json")


def _lookup_normalized(
    connection: sqlite3.Connection, identity: tuple[str, int, str]
) -> tuple[str, str, str]:
    row = connection.execute(
        "SELECT text_ocr, text_normalized, payload FROM normalized "
        "WHERE item = ? AND leaf = ? AND paragraph = ?",
        identity,
    ).fetchone()
    if row is None:
        raise ValueError(f"Missing normalized paragraph identity: {identity}")
    return row


def _normalized_paragraph(
    paragraph: ParagraphRecord,
    derived: dict[str, Any],
    text_normalized: str,
    identity: tuple[str, int, str],
) -> ParagraphRecord:
    updates: dict[str, Any] = {"text_normalized": text_normalized}
    for field in ("static_edits", "static_cleanup_provenance", "unresolved_wrap_hints"):
        if field in derived:
            updates[field] = derived[field]
    merged = ParagraphRecord.model_validate({**paragraph.model_dump(mode="json"), **updates})
    _verify_static_ledger(merged, derived, identity)
    return merged


def _verify_static_ledger(
    paragraph: ParagraphRecord, derived: dict[str, Any], identity: tuple[str, int, str]
) -> None:
    if "static_edits" not in derived or _has_ai_edits(derived):
        return
    static_text = apply_edits(paragraph.text_ocr, paragraph.static_edits)
    if static_text != paragraph.text_normalized:
        raise ValueError(f"Static edit ledger does not reproduce normalized text: {identity}")


def _has_ai_edits(derived: dict[str, Any]) -> bool:
    return "applied_edits" in derived or "ai_cleanup" in derived


def _reject_unmatched_paragraphs(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        row = connection.execute("SELECT item, leaf, paragraph FROM normalized LIMIT 1").fetchone()
    if row is not None:
        raise ValueError(f"Normalized paragraph has no canonical page: {tuple(row)}")


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
