"""Offline, reproducible raw-text sample preparation for subject review.

This module never calls a provider and deliberately samples without inspecting
text content beyond lengths. The exclusion inventory is explicit input; an
incomplete inventory means the resulting examples are not certified holdouts.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from congressional_globe.models import BoundingBox, PrintedPage


class ExcludedParagraph(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_identifier: str
    part_number: int = Field(ge=1, le=5)
    scan_leaf: int = Field(ge=0)
    paragraph_id: str


class ExclusionInventory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1"
    complete: bool = False
    paragraphs: list[ExcludedParagraph] = Field(default_factory=list)


class SampleParagraph(BaseModel):
    """Minimal external page/paragraph shape; large OCR word arrays are ignored."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str
    text_ocr: str
    line_ids: list[str] = Field(default_factory=list)
    bbox: BoundingBox | None = None
    role: str = "body"


class SamplePage(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str
    item_identifier: str
    part_number: int | None = Field(ge=1, le=5)
    scan_leaf: int = Field(ge=0)
    hocr_page_id: str
    printed_page: PrintedPage
    paragraphs: list[SampleParagraph]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _key(page: SamplePage, paragraph: SampleParagraph) -> tuple[str, int, int, str]:
    return page.item_identifier, page.part_number or 0, page.scan_leaf, paragraph.id


def _window_id(page: SamplePage, group: list[SampleParagraph]) -> str:
    digest = hashlib.sha256()
    for paragraph in group:
        digest.update("|".join(map(str, _key(page, paragraph))).encode())
        digest.update(hashlib.sha256(paragraph.text_ocr.encode()).digest())
    return digest.hexdigest()


def _page_windows(
    page: SamplePage, excluded: set[tuple[str, int, int, str]]
) -> list[dict[str, Any]]:
    """Make page-bounded contiguous windows, splitting only at paragraph boundaries."""
    output: list[dict[str, Any]] = []
    group: list[SampleParagraph] = []
    length = 0
    for paragraph in page.paragraphs:
        amount = len(paragraph.text_ocr)
        if group and length + amount + 2 > 3500:
            _append_window(output, page, group, length, excluded)
            group, length = [], 0
        group.append(paragraph)
        length += amount + (2 if len(group) > 1 else 0)
    _append_window(output, page, group, length, excluded)
    return output


def _append_window(
    output: list[dict[str, Any]],
    page: SamplePage,
    group: list[SampleParagraph],
    length: int,
    excluded: set[tuple[str, int, int, str]],
) -> None:
    if not group or not 200 <= length <= 3500:
        return
    ids = [_key(page, paragraph) for paragraph in group]
    output.append(_window_record(page, group, length, ids, excluded))


def _window_record(
    page: SamplePage,
    group: list[SampleParagraph],
    length: int,
    ids: list[tuple[str, int, int, str]],
    excluded: set[tuple[str, int, int, str]],
) -> dict[str, Any]:
    return {
        "item_identifier": page.item_identifier,
        "part_number": page.part_number,
        "scan_leaf": page.scan_leaf,
        "page_id": page.id,
        "hocr_page_id": page.hocr_page_id,
        "printed_page": page.printed_page.model_dump(mode="json"),
        "window_id": _window_id(page, group),
        "paragraphs": [
            {
                "paragraph_id": p.id,
                "raw_text": p.text_ocr,
                "raw_text_sha256": hashlib.sha256(p.text_ocr.encode()).hexdigest(),
                "hocr_line_ids": p.line_ids,
                "bbox": p.bbox.model_dump(mode="json") if p.bbox else None,
                "role": p.role,
            }
            for p in group
        ],
        "char_count": length,
        "excluded": any(identity in excluded for identity in ids),
    }


def _collect_windows(
    source_path: Path,
    excluded: set[tuple[str, int, int, str]],
    count_per_part: int,
    seed: int,
    progress_callback: Callable[[dict[str, Any]], None] | None,
) -> tuple[dict[int, list[dict[str, Any]]], dict[int, int], dict[int, int], int, str]:
    reservoirs = {part: [] for part in range(1, 6)}
    seen = {part: 0 for part in range(1, 6)}
    excluded_count = {part: 0 for part in range(1, 6)}
    randomizers = {part: random.Random(seed + part * 1000003) for part in range(1, 6)}
    pages = 0
    started = time.monotonic()
    digest = hashlib.sha256()
    with source_path.open("rb") as source:
        pages = _scan_source(
            source,
            digest,
            excluded,
            count_per_part,
            progress_callback,
            started,
            reservoirs,
            seen,
            excluded_count,
            randomizers,
        )
    _sort_reservoirs(reservoirs)
    return reservoirs, seen, excluded_count, pages, digest.hexdigest()


def _scan_source(
    source: Any,
    digest: Any,
    excluded: set[tuple[str, int, int, str]],
    count_per_part: int,
    callback: Callable[[dict[str, Any]], None] | None,
    started: float,
    reservoirs: dict[int, list[dict[str, Any]]],
    seen: dict[int, int],
    excluded_count: dict[int, int],
    randomizers: dict[int, random.Random],
) -> int:
    pages = 0
    for line_number, raw_line in enumerate(source, 1):
        digest.update(raw_line)
        page = _parse_page(raw_line.decode("utf-8"), line_number)
        pages += 1
        _scan_page(page, excluded, reservoirs, seen, excluded_count, randomizers, count_per_part)
        _notify_progress(callback, pages, started)
    return pages


def _notify_progress(
    callback: Callable[[dict[str, Any]], None] | None, pages: int, started: float
) -> None:
    if callback is not None and pages % 100 == 0:
        callback(
            {
                "pages_scanned": pages,
                "elapsed_seconds": time.monotonic() - started,
                "total_pages": None,
            }
        )


def _scan_page(
    page: SamplePage,
    excluded: set[tuple[str, int, int, str]],
    reservoirs: dict[int, list[dict[str, Any]]],
    seen: dict[int, int],
    excluded_count: dict[int, int],
    randomizers: dict[int, random.Random],
    count_per_part: int,
) -> None:
    for window in _page_windows(page, excluded):
        _consider_window(
            window, page.part_number, reservoirs, seen, excluded_count, randomizers, count_per_part
        )


def _parse_page(line: str, line_number: int) -> SamplePage:
    try:
        page = SamplePage.model_validate_json(line)
    except Exception as error:
        raise ValueError(f"invalid source page at line {line_number}: {error}") from error
    if page.part_number is None:
        raise ValueError(f"source page has null part_number at line {line_number}")
    return page


def _consider_window(
    window: dict[str, Any],
    part_value: int | None,
    reservoirs: dict[int, list[dict[str, Any]]],
    seen: dict[int, int],
    excluded_count: dict[int, int],
    randomizers: dict[int, random.Random],
    count_per_part: int,
) -> None:
    part = part_value
    if part is None:
        raise ValueError("part_number is required")
    if _record_exclusion(window, part, excluded_count):
        return
    seen[part] += 1
    candidate = {
        **window,
        "window_status": "unreviewed",
        "heldout_status": "pending_exclusion_complete_and_human_review",
        "human_review_status": "pending",
        "human_subject_labels": None,
    }
    reservoir = reservoirs[part]
    _reservoir_add(reservoir, candidate, randomizers[part], seen[part], count_per_part)


def _record_exclusion(window: dict[str, Any], part: int, counts: dict[int, int]) -> bool:
    if not window["excluded"]:
        return False
    counts[part] += 1
    return True


def _reservoir_add(
    reservoir: list[dict[str, Any]],
    candidate: dict[str, Any],
    randomizer: random.Random,
    seen: int,
    count: int,
) -> None:
    if len(reservoir) < count:
        reservoir.append(candidate)
        return
    slot = randomizer.randrange(seen)
    if slot < count:
        reservoir[slot] = candidate


def _sort_reservoirs(reservoirs: dict[int, list[dict[str, Any]]]) -> None:
    for samples in reservoirs.values():
        samples.sort(key=lambda item: (item["scan_leaf"], item["page_id"]))


def _write_packets(path: Path, packets: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for packet in packets:
            stream.write(json.dumps(packet, ensure_ascii=False, sort_keys=True) + "\n")


def _manifest(
    source_path: Path,
    exclusions_path: Path,
    inventory: ExclusionInventory,
    seed: int,
    reservoirs: dict[int, list[dict[str, Any]]],
    seen: dict[int, int],
    excluded_count: dict[int, int],
    pages: int,
    source_sha256: str,
    packet_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "seed": seed,
        "source_path_name": source_path.name,
        "source_sha256": source_sha256,
        "sampling_code_sha256": _sha256_file(Path(__file__)),
        "review_packets_sha256": packet_sha256,
        "exclusion_inventory_sha256": _sha256_file(exclusions_path),
        "exclusions_complete": inventory.complete,
        "window_policy": {
            "page_bounded": True,
            "contiguous_paragraphs": True,
            "min_chars": 200,
            "max_chars": 3500,
            "heading_context": "included_when_contiguous_and_bounded",
            "selection": "uniform_reservoir_by_part",
            "paragraphs_over_3500_chars": "omitted",
            "length_eligibility_bias": "eligible windows only; not a document-type stratum",
        },
        "stratification": "part only; no subject, edit-count, or text-content matching",
        "pages_scanned": pages,
        "eligible_windows_seen_by_part": {str(k): v for k, v in seen.items()},
        "excluded_windows_by_part": {str(k): v for k, v in excluded_count.items()},
        "selected_by_part": {str(k): len(v) for k, v in reservoirs.items()},
        "status": (
            "unreviewed_sample; heldout claims pending complete exclusions "
            "inventory and human review"
        ),
        "provider_calls": 0,
    }


def build_subject_review_sample(
    source_path: Path,
    exclusions_path: Path,
    output_dir: Path,
    seed: int,
    count_per_part: int = 2,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Create frozen, blinded packets using an explicit exclusion inventory.

    Up to five examples per part are permitted. Outputs are created in a new
    directory only; any parse/validation failure removes temporary files and
    leaves no manifest that could imply a completed sample.
    """
    _validate_request(output_dir, count_per_part)
    inventory = ExclusionInventory.model_validate_json(exclusions_path.read_text(encoding="utf-8"))
    excluded = {
        (item.item_identifier, item.part_number, item.scan_leaf, item.paragraph_id)
        for item in inventory.paragraphs
    }
    output_dir.mkdir(parents=True)
    return _build_files(
        source_path,
        exclusions_path,
        output_dir,
        seed,
        count_per_part,
        inventory,
        excluded,
        progress_callback,
    )


def _validate_request(output_dir: Path, count_per_part: int) -> None:
    if not 1 <= count_per_part <= 5:
        raise ValueError("count_per_part must be between 1 and 5")
    if output_dir.exists():
        raise FileExistsError(output_dir)


def _build_files(
    source_path: Path,
    exclusions_path: Path,
    output_dir: Path,
    seed: int,
    count_per_part: int,
    inventory: ExclusionInventory,
    excluded: set[tuple[str, int, int, str]],
    progress_callback: Callable[[dict[str, Any]], None] | None,
) -> dict[str, Any]:
    partial = output_dir / ".packets.jsonl.partial"
    manifest_partial = output_dir / ".manifest.json.partial"
    try:
        reservoirs, seen, excluded_count, pages, source_sha256 = _collect_windows(
            source_path, excluded, count_per_part, seed, progress_callback
        )
        _require_full_sample(reservoirs, count_per_part)
        _write_packets(partial, _flatten_reservoirs(reservoirs))
        manifest = _manifest(
            source_path,
            exclusions_path,
            inventory,
            seed,
            reservoirs,
            seen,
            excluded_count,
            pages,
            source_sha256,
            _sha256_file(partial),
        )
        manifest_partial.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        partial.replace(output_dir / "review_packets.jsonl")
        manifest_partial.replace(output_dir / "manifest.json")
        return manifest
    except Exception:
        partial.unlink(missing_ok=True)
        manifest_partial.unlink(missing_ok=True)
        # Output directory remains as evidence of a failed attempt, never as a completed sample.
        raise


def _require_full_sample(reservoirs: dict[int, list[dict[str, Any]]], count_per_part: int) -> None:
    if any(len(reservoirs[part]) < count_per_part for part in range(1, 6)):
        raise ValueError("insufficient eligible unexcluded windows in one or more parts")


def _flatten_reservoirs(reservoirs: dict[int, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [item for part in reservoirs.values() for item in part]
