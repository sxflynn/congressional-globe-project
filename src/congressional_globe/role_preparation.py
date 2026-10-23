"""Offline, source-preserving preparation for the bounded role-only retry.

No provider client is imported or called. Outputs are diagnostic inputs, not labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from congressional_globe.role_aliases import ROLE_RESULT_SCHEMA, prepare_aliases
from congressional_globe.subject_sampling import SamplePage

PROMPT = """Classify roles from the supplied raw OCR, using only supplied short IDs.
Return speaker_roles with candidate_id, target_ids, evidence_ids, role, status, basis.
Use target_ids for the paragraph(s) actually attributed, and evidence_ids for the
text supporting that role. Never assign an entire mixed passage to one speaker.
A person mentioned is not necessarily speaking. Distinguish a petition presenter,
a letter author/signature, an actual quoted speaker, and a floor speaker. Do not
resolve unnamed chairs from 'Mr. Speaker' or 'Mr. President'. Broken OCR is evidence,
not permission to invent names. No identity/date/party inference from roster membership.
For unknown attribution use status unknown, candidate_id null, evidence_ids [],
with target_ids and a short basis explaining missing evidence. Never invent IDs.
Page breaks alone neither end nor prove a speech continuation. Inspect preceding
context, intervening named turns, and chamber/date/proceeding boundaries. Apply a
previous speaker to a continuation only when the supplied ordered text supports it.
These are reviewable role proposals, not verified speaker identities. Do not return
topic classifications or dates; those are separate tasks.
"""


class PredecessorManifest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    frozen_inputs_sha256: str


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _read_predecessors(directory: Path) -> tuple[list[dict], str]:
    manifest = PredecessorManifest.model_validate_json((directory / "manifest.json").read_text())
    payload = (directory / "frozen_inputs.jsonl").read_bytes()
    if _sha(payload) != manifest.frozen_inputs_sha256:
        raise ValueError("Predecessor frozen input hash mismatch")
    rows = [json.loads(line) for line in payload.splitlines() if line.strip()]
    if len(rows) != 5:
        raise ValueError("This diagnostic requires exactly five predecessor cases")
    return rows, manifest.frozen_inputs_sha256


def _read_context_pages(path: Path) -> tuple[list[SamplePage], str]:
    selected: dict[int, SamplePage] = {}
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for line in stream:
            digest.update(line)
            _select_page(line, selected)
    if set(selected) != {403, 404}:
        raise ValueError("Both required part-5 adjacent pages must exist exactly once")
    return [selected[403], selected[404]], digest.hexdigest()


def _select_page(line: bytes, selected: dict[int, SamplePage]) -> None:
    if b"congressionalglo7395unit" not in line:
        return
    row = json.loads(line)
    if row.get("scan_leaf") not in {403, 404}:
        return
    page = SamplePage.model_validate(row)
    if page.item_identifier != "congressionalglo7395unit" or page.part_number != 5:
        raise ValueError("Context page source identity mismatch")
    if page.scan_leaf in selected:
        raise ValueError("Duplicate context page")
    selected[page.scan_leaf] = page


def _context_row(pages: list[SamplePage], roles: list[str], statuses: list[str]) -> dict:
    sources: list[dict] = []
    spans: list[dict] = []
    pieces: list[str] = []
    for page, paragraphs in (
        (pages[0], pages[0].paragraphs[-8:]),
        (pages[1], pages[1].paragraphs[:8]),
    ):
        for paragraph in paragraphs:
            _append_paragraph(page, paragraph, pieces, spans, sources)
    raw = "\n\n".join(pieces)
    return {
        "schema_version": "span-selection-input-v1",
        "offset_convention": "unicode_codepoints_half_open",
        "window_id": "hr008-cross-page-p5-403-404-v1",
        "source_anchor": {
            "item_identifier": pages[0].item_identifier,
            "part_number": 5,
            "scan_leaf_range": [403, 404],
            "paragraph_sources": sources,
            "selection": "last 8 paragraphs of leaf403, first 8 of leaf404; not complete pages",
        },
        "raw_text": raw,
        "raw_sha256": _sha(raw.encode()),
        "spans": spans,
        "controlled_role_ids": roles,
        "controlled_topic_ids": [],
        "statuses": statuses,
    }


def _append_paragraph(page, paragraph, pieces: list, spans: list, sources: list) -> None:
    start = sum(len(piece) + 2 for piece in pieces)
    text = paragraph.text_ocr
    source_id = f"{page.id}::{paragraph.id}"
    pieces.append(text)
    spans.append(_span(source_id, "paragraph", text, start, source_id))
    sources.append(
        {
            "composite_paragraph_id": source_id,
            "paragraph_id": paragraph.id,
            "page_id": page.id,
            "scan_leaf": page.scan_leaf,
            "printed_page": page.printed_page.model_dump(),
            "hocr_page_id": page.hocr_page_id,
            "bbox": paragraph.bbox.model_dump() if paragraph.bbox else None,
            "line_ids": paragraph.line_ids,
        }
    )
    _append_cues(text, start, source_id, spans)


def _span(identifier: str, kind: str, text: str, start: int, paragraph: str) -> dict:
    return {
        "span_id": identifier,
        "kind": kind,
        "text": text,
        "start": start,
        "end": start + len(text),
        "source_paragraph_id": paragraph,
        "cue_origin": None,
    }


def _append_cues(text: str, start: int, paragraph: str, spans: list) -> None:
    for index, match in enumerate(
        re.finditer(r"\bMr\.\s+[A-Z][A-Z'\u2019\-]+(?:\s+[A-Z][A-Z'\u2019\-]+)*\.?", text)
    ):
        cue = _span(
            f"{paragraph}:cue:{index}", "speaker_cue", match[0], start + match.start(), paragraph
        )
        cue["cue_origin"] = "literal_uppercase_Mr_pattern_v1; candidate_only_not_a_role"
        spans.append(cue)


def prepare(predecessor: Path, pages: Path, output: Path) -> dict:
    started = time.monotonic()
    if output.exists():
        raise FileExistsError(output)
    rows, predecessor_hash = _read_predecessors(predecessor)
    context_pages, pages_hash = _read_context_pages(pages)
    context = _context_row(context_pages, rows[0]["controlled_role_ids"], rows[0]["statuses"])
    rows.append(context)
    prepared = [prepare_aliases(row) for row in rows]
    output.mkdir(parents=True, exist_ok=False)
    _write_outputs(output, rows, prepared)
    manifest = _manifest(output, rows, predecessor_hash, pages_hash, started)
    _write_json(output / "manifest.json", manifest)
    return manifest


def _write_outputs(output: Path, rows: list[dict], prepared: list[dict]) -> None:
    (output / "frozen-inputs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (output / "provider-inputs.jsonl").write_text(
        "".join(json.dumps(row["input"], ensure_ascii=False) + "\n" for row in prepared)
    )
    _write_json(
        output / "alias-maps.json",
        {row["window_id"]: item["alias_map"] for row, item in zip(rows, prepared, strict=True)},
    )
    _write_json(output / "output.schema.json", ROLE_RESULT_SCHEMA)
    (output / "prompt.txt").write_text(PROMPT)


def _manifest(
    output: Path, rows: list[dict], predecessor_hash: str, pages_hash: str, started: float
) -> dict:
    return {
        "experiment_id": "role-alias-preparation-v1",
        "status": "offline prepared; no provider calls, no role/date results",
        "case_ids": [row["window_id"] for row in rows],
        "case_count": len(rows),
        "predecessor_sha256": predecessor_hash,
        "canonical_pages_sha256": pages_hash,
        "files_sha256": {path.name: _sha(path.read_bytes()) for path in sorted(output.iterdir())},
        "code_sha256": {
            name: _sha((Path(__file__).parent / name).read_bytes())
            for name in ("role_preparation.py", "role_aliases.py")
        },
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "limits": "Six diagnostic cases; role-only task; dates and authority linking deferred",
        "review": "No human gold labels. Cross-page source review must precede model launch.",
        "next": "Freeze source expectations, then implement an audited bounded runner",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predecessor", type=Path, required=True)
    parser.add_argument("--pages", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.predecessor, args.pages, args.output), indent=2))


if __name__ == "__main__":
    main()
