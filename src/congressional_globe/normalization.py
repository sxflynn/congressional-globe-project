"""Validated application of model-suggested OCR patches."""

from __future__ import annotations

import re
import unicodedata

from congressional_globe.models import TextEdit


def apply_edits(text: str, edits: list[TextEdit]) -> str:
    _validate_edits(text, edits)
    result = text
    for edit in reversed(edits):
        result = result[: edit.start_char] + edit.replacement + result[edit.end_char :]
    return result


def resolve_edits(text: str, edits: list[TextEdit]) -> list[TextEdit]:
    """Correct model offsets only when its exact source anchor occurs once."""
    resolved = [_resolve_edit(text, edit) for edit in edits]
    return _dedupe_and_sort(resolved)


def validate_edit_shapes(text: str, edits: list[TextEdit]) -> None:
    """Reject edits that only change punctuation or numeric values."""
    for edit in edits:
        _validate_edit_shape(edit)


def _validate_edit_shape(edit: TextEdit) -> None:
    if edit.expected == edit.replacement:
        return
    if _numeric_only_pair(edit.expected, edit.replacement):
        raise ValueError("numeric-only edits require review")
    if not _punctuation_only(edit) or _allowed_separator_repair(edit):
        return
    raise ValueError("punctuation-only edits require review")


def _numeric_only_pair(expected: str, replacement: str) -> bool:
    return _is_numeric_only(expected) and _is_numeric_only(replacement)


def _punctuation_only(edit: TextEdit) -> bool:
    return _without_punctuation(edit.expected) == _without_punctuation(edit.replacement)


def _allowed_separator_repair(edit: TextEdit) -> bool:
    return _whitespace_only(edit.expected, edit.replacement) or _hyphen_join(edit)


def _is_numeric_only(value: str) -> bool:
    return bool(value.strip()) and all(char.isdigit() or char in " ,./$%-" for char in value)


def _without_punctuation(value: str) -> str:
    return "".join(char for char in value if not unicodedata.category(char).startswith("P"))


def _whitespace_only(expected: str, replacement: str) -> bool:
    return expected != replacement and expected.split() == replacement.split()


def _hyphen_join(edit: TextEdit) -> bool:
    return bool(
        re.fullmatch(r"[A-Za-z]+-\s+[A-Za-z]+", edit.expected)
    ) and edit.replacement == re.sub(r"-\s+", "", edit.expected)


def _dedupe_and_sort(edits: list[TextEdit]) -> list[TextEdit]:
    """Drop repeated model proposals and order edits against the unmodified text."""
    seen: set[tuple[int, int, str]] = set()
    unique: list[TextEdit] = []
    for edit in sorted(edits, key=lambda item: item.start_char):
        key = (edit.start_char, edit.end_char, edit.replacement)
        if key not in seen:
            seen.add(key)
            unique.append(edit)
    return unique


def _resolve_edit(text: str, edit: TextEdit) -> TextEdit:
    if _matches_source(text, edit):
        return edit
    start = _unique_position(text, edit.expected)
    return edit.model_copy(update={"start_char": start, "end_char": start + len(edit.expected)})


def _matches_source(text: str, edit: TextEdit) -> bool:
    return text[edit.start_char : edit.end_char] == edit.expected


def _unique_position(text: str, expected: str) -> int:
    positions = [index for index in range(len(text)) if text.startswith(expected, index)]
    if len(positions) != 1:
        raise ValueError("edit expected text must occur exactly once when offsets are incorrect")
    return positions[0]


def _validate_edits(text: str, edits: list[TextEdit]) -> None:
    previous_end = 0
    for edit in edits:
        _validate_order(edit, previous_end)
        _validate_span(text, edit)
        _validate_expected_text(text, edit)
        previous_end = edit.end_char


def _validate_order(edit: TextEdit, previous_end: int) -> None:
    if edit.start_char < previous_end:
        raise ValueError("edits must be sorted and non-overlapping")


def _validate_span(text: str, edit: TextEdit) -> None:
    if edit.end_char < edit.start_char or edit.end_char > len(text):
        raise ValueError("edit span is outside source text")


def _validate_expected_text(text: str, edit: TextEdit) -> None:
    if text[edit.start_char : edit.end_char] != edit.expected:
        raise ValueError("edit expected text does not match source text")
