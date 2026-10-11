"""Conservative, patch-based cleanup that runs without model requests."""

from __future__ import annotations

import hashlib
import json
import re
from itertools import pairwise
from pathlib import Path

from congressional_globe.models import LineRecord, ParagraphRecord, TextEdit
from congressional_globe.normalization import apply_edits

_LINE_END = re.compile(r"(?<![A-Za-z])([A-Za-z]+)-$")
_LINE_START = re.compile(r"([a-z][A-Za-z]*)")
_SUFFIXES = ("s", "es", "ed", "ing", "ly")


def normalize_jsonl(paragraphs_path: Path, lexicon_path: Path, output_path: Path) -> int:
    """Write normalized records, unresolved hints, and reproducible provenance."""
    _reject_output_alias(paragraphs_path, lexicon_path, output_path)
    lexicon_bytes = lexicon_path.read_bytes()
    lexicon = {word.casefold() for word in lexicon_bytes.decode("utf-8").splitlines()}
    provenance = {
        "pipeline_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "lexicon_sha256": hashlib.sha256(lexicon_bytes).hexdigest(),
        "input_sha256": _file_sha256(paragraphs_path),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with (
        paragraphs_path.open(encoding="utf-8") as source,
        output_path.open("w", encoding="utf-8") as target,
    ):
        for line in source:
            record = _normalized_record(line, lexicon, provenance)
            if record is not None:
                target.write(record + "\n")
                count += 1
    return count


def _reject_output_alias(source: Path, lexicon: Path, output: Path) -> None:
    if _same_file(source, output) or _same_file(lexicon, output):
        raise ValueError("cleanup output must not alias either input path")


def _same_file(left: Path, right: Path) -> bool:
    return left.resolve() == right.resolve() or (
        left.exists() and right.exists() and left.samefile(right)
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalized_record(line: str, lexicon: set[str], provenance: dict[str, str]) -> str | None:
    if not line.strip():
        return None
    payload = json.loads(line)
    fields = {key: value for key, value in payload.items() if key in ParagraphRecord.model_fields}
    paragraph = ParagraphRecord.model_validate(fields)
    edits = _line_wrap_edits(paragraph.lines, paragraph.text_ocr, lexicon)
    normalized = apply_edits(paragraph.text_ocr, edits)
    return json.dumps(
        {
            **payload,
            "text_normalized": normalized,
            "static_edits": [edit.model_dump(mode="json") for edit in edits],
            "unresolved_wrap_hints": _unresolved_hints(paragraph.lines, lexicon),
            "static_cleanup_provenance": provenance,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def normalize_line_wraps(
    paragraph: ParagraphRecord, lexicon: set[str]
) -> tuple[str, list[TextEdit]]:
    """Join lexicon-supported words only across adjacent OCR line boundaries."""
    edits = _line_wrap_edits(paragraph.lines, paragraph.text_ocr, lexicon)
    return apply_edits(paragraph.text_ocr, edits), edits


def _line_wrap_edits(lines: list[LineRecord], source: str, lexicon: set[str]) -> list[TextEdit]:
    positions = _line_positions(lines, source)
    return [
        edit
        for index, (left, right) in enumerate(pairwise(lines))
        if (edit := _positioned_pair_edit(left, right, source, positions, index, lexicon))
        is not None
    ]


def _positioned_pair_edit(
    left: LineRecord,
    right: LineRecord,
    source: str,
    positions: list[int | None],
    index: int,
    lexicon: set[str],
) -> TextEdit | None:
    left_start, right_start = positions[index : index + 2]
    if left_start is None or right_start is None:
        return None
    return _pair_edit(left, right, source, left_start, right_start, lexicon)


def _line_positions(lines: list[LineRecord], source: str) -> list[int | None]:
    positions: list[int | None] = []
    cursor = 0
    for line in lines:
        start = source.find(line.text, cursor)
        positions.append(start if start >= 0 else None)
        if start >= 0:
            cursor = start + len(line.text)
    return positions


def _pair_edit(
    left: LineRecord,
    right: LineRecord,
    source: str,
    left_start: int,
    right_start: int,
    lexicon: set[str],
) -> TextEdit | None:
    left_text = left.text.rstrip()
    left_match = _LINE_END.search(left_text)
    right_match = _LINE_START.match(right.text.lstrip())
    if left_match is None or right_match is None:
        return None
    left_word, right_word = left_match.group(1), right_match.group(1)
    joined = (left_word + right_word).casefold()
    start = left_start + left_match.start()
    right_word_start = right_start + len(right.text) - len(right.text.lstrip())
    gap = source[start + len(left_word) + 1 : right_word_start]
    expected = f"{left_word}-{gap}{right_word}"
    if not gap or not gap.isspace() or source[start : start + len(expected)] != expected:
        return None
    if not _known_word(joined, lexicon):
        return None
    return TextEdit(
        start_char=start,
        end_char=start + len(expected),
        expected=expected,
        replacement=left_word + right_word,
        reason=f"adjacent-line wrap; lexicon form {joined}",
        confidence=0.98,
    )


def _unresolved_hints(lines: list[LineRecord], lexicon: set[str]) -> list[dict[str, str]]:
    return [
        hint
        for left, right in pairwise(lines)
        if (hint := _unresolved_hint(left, right, lexicon)) is not None
    ]


def _unresolved_hint(
    left: LineRecord, right: LineRecord, lexicon: set[str]
) -> dict[str, str] | None:
    left_match = _LINE_END.search(left.text.rstrip())
    right_match = _LINE_START.match(right.text.lstrip())
    if left_match is None or right_match is None:
        return None
    joined = (left_match.group(1) + right_match.group(1)).casefold()
    if _known_word(joined, lexicon):
        return None
    return {
        "left_line_id": left.id,
        "right_line_id": right.id,
        "candidate": joined,
        "reason": "line-end hyphen unresolved by static lexicon",
    }


def _known_word(word: str, lexicon: set[str]) -> bool:
    if word in lexicon:
        return True
    return any(word.endswith(suffix) and word[: -len(suffix)] in lexicon for suffix in _SUFFIXES)
