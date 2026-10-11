"""Conservative geometry-aware cleanup that runs without model requests."""

from __future__ import annotations

import json
import re
from itertools import pairwise
from pathlib import Path

from congressional_globe.models import LineRecord, ParagraphRecord, TextEdit
from congressional_globe.normalization import apply_edits

_LINE_WRAP = re.compile(r"([A-Za-z]+)-\s+([a-z][A-Za-z]*)")
_SUFFIXES = ("s", "es", "ed", "ing", "ly")


def normalize_jsonl(paragraphs_path: Path, lexicon_path: Path, output_path: Path) -> int:
    """Write derived normalized records and an explicit patch ledger as JSONL."""
    lexicon = {word.casefold() for word in lexicon_path.read_text(encoding="utf-8").splitlines()}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with (
        paragraphs_path.open(encoding="utf-8") as source,
        output_path.open("w", encoding="utf-8") as target,
    ):
        for line in source:
            record = _normalized_record(line, lexicon)
            if record is not None:
                target.write(record + "\n")
                count += 1
    return count


def _normalized_record(line: str, lexicon: set[str]) -> str | None:
    if not line.strip():
        return None
    payload = json.loads(line)
    fields = {key: value for key, value in payload.items() if key in ParagraphRecord.model_fields}
    paragraph = ParagraphRecord.model_validate(fields)
    normalized, edits = normalize_line_wraps(paragraph, lexicon)
    return json.dumps(
        {
            **payload,
            "text_normalized": normalized,
            "static_edits": [edit.model_dump(mode="json") for edit in edits],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def normalize_line_wraps(
    paragraph: ParagraphRecord, lexicon: set[str]
) -> tuple[str, list[TextEdit]]:
    """Join only alphabetic line-end hyphens whose result is lexically supported."""
    edits = _line_wrap_edits(paragraph.lines, paragraph.text_ocr, lexicon)
    return apply_edits(paragraph.text_ocr, edits), edits


def _line_wrap_edits(lines: list[LineRecord], source: str, lexicon: set[str]) -> list[TextEdit]:
    edits: list[TextEdit] = []
    for left, right in pairwise(lines):
        edits.extend(_pair_edits(left, right, source, lexicon))
    return edits


def _pair_edits(
    left: LineRecord, right: LineRecord, source: str, lexicon: set[str]
) -> list[TextEdit]:
    match = _LINE_WRAP.search(f"{left.text} {right.text}")
    if match is None:
        return []
    joined = (match.group(1) + match.group(2)).lower()
    if not _known_word(joined, lexicon):
        return []
    expected = f"{match.group(1)}- {match.group(2)}"
    start = _line_pair_position(source, left.text, right.text, expected)
    if start is None:
        return []
    return [
        TextEdit(
            start_char=start,
            end_char=start + len(expected),
            expected=expected,
            replacement=match.group(1) + match.group(2),
            reason=f"geometry-confirmed line wrap; lexicon form {joined}",
            confidence=0.98,
        )
    ]


def _line_pair_position(source: str, left: str, right: str, expected: str) -> int | None:
    left_start = source.find(left)
    if left_start < 0:
        return None
    boundary = left_start + len(left)
    right_start = source.find(right, boundary)
    if right_start < 0:
        return None
    start = source.find(expected, boundary - len(left), right_start + len(right))
    if start < boundary - len(left) or start + len(expected) > right_start + len(right):
        return None
    return start


def _known_word(word: str, lexicon: set[str]) -> bool:
    if word in lexicon:
        return True
    return any(word.endswith(suffix) and word[: -len(suffix)] in lexicon for suffix in _SUFFIXES)
