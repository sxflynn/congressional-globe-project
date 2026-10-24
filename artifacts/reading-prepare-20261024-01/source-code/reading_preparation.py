"""Offline, deterministic candidate selection; heuristic strata await source review."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from congressional_globe.inventory import PARTS, sha256_file
from congressional_globe.models import PageRecord, ParagraphRecord
from congressional_globe.reading_contracts import (
    ReadingCandidate,
    ReadingParagraph,
    ReadingStratum,
    text_hash,
)

SEED = 20261024
POOL_SIZE = 16
SPEAKER = re.compile(r"\b(?:Mr\.|The SPEAKER|The PRESIDENT)")
QUOTATION = re.compile(r"\b(?:Be it|be it|Resolved|Sec\.|To the Senate|DEAR SIR|Dear Sir|AN ACT)")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _part(page: PageRecord) -> int:
    part = PARTS.get(page.item_identifier)
    if part is None or part != page.part_number:
        raise ValueError("unknown or mismatched source part")
    return part


def source_paragraph(page: PageRecord, paragraph: ParagraphRecord) -> ReadingParagraph:
    return ReadingParagraph(
        item_identifier=page.item_identifier,
        part_number=_part(page),
        scan_leaf=page.scan_leaf,
        printed_page=page.printed_page,
        paragraph_id=paragraph.id,
        reading_order=paragraph.reading_order,
        hocr_page_id=page.hocr_page_id,
        line_ids=paragraph.line_ids,
        bbox=paragraph.bbox,
        raw=paragraph.text_ocr,
        raw_sha256=text_hash(paragraph.text_ocr),
        static=paragraph.text_normalized or "",
        static_patches=paragraph.static_edits,
        static_sha256=text_hash(paragraph.text_normalized or ""),
    )


def _groups(page: PageRecord, minimum: int, maximum: int):
    """Greedy contiguous paragraph groups; never slice a paragraph to hit a limit."""
    start = words = 0
    for index, paragraph in enumerate(page.paragraphs):
        count = len(paragraph.text_ocr.split())
        if words + count > maximum:
            start, words = index, 0
        words += count
        if minimum <= words <= maximum:
            yield start, index + 1
            start, words = index + 1, 0


def _damage_cue(paragraphs: list[ParagraphRecord]) -> bool:
    return any(_paragraph_damage_cue(paragraph) for paragraph in paragraphs)


def _paragraph_damage_cue(paragraph: ParagraphRecord) -> bool:
    text = paragraph.text_ocr
    if not (SPEAKER.search(text[:160]) or re.search(r"\d|\b(?:bill|January|March|June)\b", text)):
        return False
    return _low_count(paragraph) >= 3 and len(paragraph.static_edits) >= 2


def _low_count(paragraph: ParagraphRecord) -> int:
    words = [word for line in paragraph.lines for word in line.words]
    return sum(_low_word(word.confidence) for word in words)


def _low_word(confidence: int | None) -> bool:
    return confidence is not None and confidence < 50


def _stratum(page: PageRecord, start: int, end: int, long: bool) -> ReadingStratum | None:
    text = "\n".join(paragraph.text_ocr for paragraph in page.paragraphs[start:end])
    if long:
        return "quotation" if QUOTATION.search(text) else "long"
    return _short_stratum(page, start, end, text)


def _short_stratum(page: PageRecord, start: int, end: int, text: str) -> ReadingStratum | None:
    header = "\n".join(paragraph.text_ocr for paragraph in page.paragraphs[:10])
    if re.search(r"(?im)^\s*(?:INDEX|IN DEX)\b", header):
        return "structured"
    if _damage_cue(page.paragraphs[start:end]):
        return "damage_cue"
    return "ordinary" if SPEAKER.search(text) else None


def _candidate(page: PageRecord, start: int, end: int, kind: ReadingStratum) -> ReadingCandidate:
    target = [source_paragraph(page, paragraph) for paragraph in page.paragraphs[start:end]]
    identity = text_hash(_json([paragraph.source_id for paragraph in target]))[:20]
    return ReadingCandidate(
        id=f"reading-{identity}",
        part_number=_part(page),
        stratum=kind,
        split="primary",
        target=target,
        context_before=[
            source_paragraph(page, p) for p in page.paragraphs[max(0, start - 1) : start]
        ],
        context_after=[source_paragraph(page, p) for p in page.paragraphs[end : end + 1]],
        selection_reason=f"OCR-only {kind} cue; document type, continuity and damage unverified",
    )


def _continuation(previous: PageRecord | None, page: PageRecord) -> ReadingCandidate | None:
    if previous is None or previous.item_identifier != page.item_identifier:
        return None
    before = _body_paragraphs(previous)
    after = _body_paragraphs(page)
    if not before or not after:
        return None
    return _join_pages(previous, page, before[-1], after[0])


def _body_paragraphs(page: PageRecord) -> list[ParagraphRecord]:
    return [p for p in page.paragraphs if len(p.text_ocr.split()) >= 10]


def _join_pages(
    before: PageRecord, after: PageRecord, last: ParagraphRecord, first: ParagraphRecord
) -> ReadingCandidate | None:
    text = last.text_ocr + "\n" + first.text_ocr
    if not 700 <= len(text.split()) <= 1200:
        return None
    target = [source_paragraph(before, last), source_paragraph(after, first)]
    identity = text_hash(_json([p.source_id for p in target]))[:20]
    return ReadingCandidate(
        id=f"reading-{identity}",
        part_number=_part(before),
        stratum="continuation",
        split="primary",
        target=target,
        selection_reason="Page-boundary pair; continuity unverified; headers not targeted",
    )


def _anchor_pages(value: Any) -> set[tuple[str, int]]:
    if isinstance(value, list):
        return set().union(*(_anchor_pages(item) for item in value))
    if not isinstance(value, dict):
        return set()
    result = _direct_anchor(value)
    return result.union(*(_anchor_pages(child) for child in value.values()))


def _direct_anchor(value: dict) -> set[tuple[str, int]]:
    item = value.get("item_identifier")
    if not item:
        return set()
    leaves = _leaf_numbers(value)
    return {(item, leaf) for leaf in leaves}


def _leaf_numbers(value: dict) -> list[int]:
    limits = value.get("scan_leaf_range")
    if limits is not None:
        start, end = limits
        if not 0 <= start <= end <= 10000:
            raise ValueError("invalid exposure leaf range")
        return list(range(start, end + 1))
    leaf = value.get("scan_leaf")
    return [leaf] if isinstance(leaf, int) else []


def exposure_pages(paths: list[Path]) -> tuple[set[tuple[str, int]], dict[str, str]]:
    pages: set[tuple[str, int]] = set()
    hashes = {}
    for path in paths:
        hashes[str(path)] = sha256_file(path)
        payloads = path.read_text().splitlines() if path.suffix == ".jsonl" else [path.read_text()]
        for payload in payloads:
            pages.update(_anchor_pages(json.loads(payload)))
    return pages, hashes


class _Reservoirs:
    def __init__(self):
        self.counts: Counter = Counter()
        self.pools: dict[str, list[ReadingCandidate]] = {}
        self.random: dict[str, random.Random] = {}

    def add(self, candidate: ReadingCandidate) -> None:
        key = f"{candidate.part_number}:{candidate.stratum}"
        self.counts[key] += 1
        pool = self.pools.setdefault(key, [])
        rng = self.random.setdefault(key, random.Random(f"{SEED}:{key}"))
        index = len(pool) if len(pool) < POOL_SIZE else rng.randrange(self.counts[key])
        if index < POOL_SIZE:
            _replace(pool, index, candidate)


def _replace(pool: list, index: int, candidate: ReadingCandidate) -> None:
    if index == len(pool):
        pool.append(candidate)
    else:
        pool[index] = candidate


def _candidate_pages(candidate: ReadingCandidate) -> set[tuple[str, int]]:
    return {
        (p.item_identifier, p.scan_leaf)
        for p in [*candidate.context_before, *candidate.target, *candidate.context_after]
    }


def _choose(pool: list[ReadingCandidate], used: set[tuple[str, int]], split: str):
    for candidate in pool:
        if not _candidate_pages(candidate).intersection(used):
            used.update(_candidate_pages(candidate))
            return candidate.model_copy(update={"split": split})
    return None


def _select(pools: dict) -> tuple[list[ReadingCandidate], list[str]]:
    selected, missing, used = [], [], set()
    for part in range(1, 6):
        for kind in ("ordinary", "damage_cue", "structured"):
            _select_one(pools, f"{part}:{kind}", used, "primary", selected, missing)
    long_used = set()
    for kind in ("continuation", "quotation", "long"):
        _select_long(pools, kind, used, long_used, selected, missing)
    for part in range(1, 6):
        _select_one(pools, f"{part}:ordinary", used, "confirmation", selected, missing)
    return selected, missing


def _select_one(pools: dict, key: str, used: set, split: str, selected: list, missing: list):
    candidate = _choose(pools.get(key, []), used, split)
    if candidate:
        selected.append(candidate)
    else:
        missing.append(f"{split}:{key}")


def _select_long(pools: dict, kind: str, used: set, parts: set, selected: list, missing: list):
    eligible = [
        c for part in range(1, 6) if part not in parts for c in pools.get(f"{part}:{kind}", [])
    ]
    candidate = _choose(eligible, used, "primary")
    if candidate:
        parts.add(candidate.part_number)
        selected.append(candidate)
    else:
        missing.append(f"primary:{kind}")


def prepare_candidates(
    pages: Path, exclusions: list[Path], output: Path, source_manifest: Path | None = None
) -> dict:
    """Save auditable candidate selection, not image-certified provider inputs."""
    output.mkdir(parents=True, exist_ok=False)
    excluded, exposure_hashes = exposure_pages(exclusions)
    reservoirs, digest = _Reservoirs(), hashlib.sha256()
    counts: Counter = Counter()
    with pages.open("rb") as source, (output / "selection-audit.jsonl").open("w") as audit:
        previous = None
        for line in source:
            digest.update(line)
            page = PageRecord.model_validate_json(line)
            counts["pages"] += 1
            _page_candidates(page, excluded, reservoirs, audit, counts)
            crossing = _continuation(previous, page)
            _consider(crossing, excluded, reservoirs, audit, counts)
            previous = page
    selected, missing = _select(reservoirs.pools)
    _write_candidates(output, selected)
    bindings = _source_bindings(source_manifest, selected)
    (output / "source-files.json").write_text(json.dumps(bindings, indent=2) + "\n")
    manifest = _manifest(pages, digest.hexdigest(), exposure_hashes, reservoirs, counts, missing)
    manifest["files_sha256"] = {p.name: sha256_file(p) for p in output.iterdir()}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def _page_candidates(page: PageRecord, excluded: set, reservoirs, audit, counts):
    for long in (False, True):
        _sized_candidates(page, long, excluded, reservoirs, audit, counts)


def _sized_candidates(page: PageRecord, long: bool, excluded: set, reservoirs, audit, counts):
    low, high = (700, 1200) if long else (200, 700)
    for start, end in _groups(page, low, high):
        kind = _stratum(page, start, end, long)
        if kind:
            _consider(_candidate(page, start, end, kind), excluded, reservoirs, audit, counts)
        else:
            audit.write(
                _json(dict(page=page.id, start=start, end=end, reason="no-stratum-cue")) + "\n"
            )


def _consider(candidate, excluded, reservoirs, audit, counts):
    if candidate is None:
        return
    rejected = bool(_candidate_pages(candidate).intersection(excluded))
    counts["exposure_rejected" if rejected else "eligible"] += 1
    audit.write(
        _json(
            dict(
                id=candidate.id,
                part=candidate.part_number,
                stratum=candidate.stratum,
                excluded=rejected,
                target=[p.source_id for p in candidate.target],
            )
        )
        + "\n"
    )
    if not rejected:
        reservoirs.add(candidate)


def _write_candidates(output: Path, selected: list[ReadingCandidate]):
    with (output / "candidates.jsonl").open("w") as target:
        for candidate in selected:
            target.write(candidate.model_dump_json() + "\n")
    schema = dict(candidate=ReadingCandidate.model_json_schema())
    (output / "candidate.schema.json").write_text(json.dumps(schema, indent=2) + "\n")


def _manifest(pages: Path, digest: str, exposure_hashes: dict, reservoirs, counts, missing) -> dict:
    return dict(
        version=1,
        run_id="reading-prepare-20261024-01",
        seed=SEED,
        source_path=str(pages),
        source_sha256=digest,
        exposure_files_sha256=exposure_hashes,
        exposure_inventory_complete=False,
        pool_size=POOL_SIZE,
        eligible_by_stratum=dict(reservoirs.counts),
        counts=dict(counts),
        missing_strata=missing,
        source_review="pending",
        launch_ready=False,
        provider_calls=0,
        image_fetches=0,
        limits="OCR-only candidate cues, not verified historical categories or clean controls",
        code_sha256={
            Path(__file__).name: sha256_file(Path(__file__)),
            "reading_contracts.py": sha256_file(Path(__file__).with_name("reading_contracts.py")),
        },
    )


class _SourcePart(BaseModel):
    model_config = ConfigDict(extra="ignore")
    identifier: str
    hocr_path: Path
    hocr_sha256: str
    page_map_path: Path
    page_map_sha256: str


class _Sources(BaseModel):
    model_config = ConfigDict(extra="ignore")
    parts: list[_SourcePart]


def _source_bindings(path: Path | None, selected: list[ReadingCandidate]) -> dict:
    if path is None:
        return dict(verified=False, reason="no immutable-source manifest supplied")
    sources = _Sources.model_validate_json(path.read_text())
    needed = {paragraph.item_identifier for unit in selected for paragraph in unit.target}
    parts = [part for part in sources.parts if part.identifier in needed]
    if {part.identifier for part in parts} != needed:
        raise ValueError("source manifest does not cover selected items")
    return dict(
        verified=True,
        manifest_sha256=sha256_file(path),
        parts=[_verify_source(part) for part in parts],
    )


def _verify_source(part: _SourcePart) -> dict:
    files = [(part.hocr_path, part.hocr_sha256), (part.page_map_path, part.page_map_sha256)]
    for path, digest in files:
        if sha256_file(path) != digest:
            raise ValueError(f"immutable source hash mismatch: {path.name}")
    return part.model_dump(mode="json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=Path, required=True)
    parser.add_argument("--exclusions", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            prepare_candidates(args.pages, args.exclusions, args.output, args.source_manifest),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
