"""Exact quote location and inverse support maps for productive OCR proposals."""

from __future__ import annotations

from congressional_globe.deterministic_models import (
    ExactEdit,
    SupportSegment,
    derived_support,
    replay_with_map,
)


def unique_quote_span(text: str, quote: str) -> tuple[int, int]:
    """Return a unique literal interval; overlapping matches count as distinct."""
    if not quote or not quote.strip():
        raise ValueError("quote must be nonblank")
    positions = [
        index for index in range(len(text) - len(quote) + 1) if text.startswith(quote, index)
    ]
    if len(positions) != 1:
        raise ValueError("quote must occur exactly once in its declared text")
    start = positions[0]
    return start, start + len(quote)


def replay_support_map(
    raw: str, edits: tuple[ExactEdit, ...], expected: str
) -> tuple[SupportSegment, ...]:
    """Replay frozen raw edits and require the exact derived text."""
    text, support = replay_with_map(raw, edits)
    if text != expected:
        raise ValueError("derived layer does not replay from raw")
    return support


def inverse_quote_support(
    raw: str,
    derived: str,
    quote: str,
    edits: tuple[ExactEdit, ...],
) -> tuple[int, int, int, int]:
    """Map one uniquely located derived quote to its original raw support interval."""
    derived_start, derived_end = unique_quote_span(derived, quote)
    support = replay_support_map(raw, edits, derived)
    selected = [
        segment
        for segment in support
        if segment.derived_start < derived_end and derived_start < segment.derived_end
    ]
    if not selected:
        raise ValueError("derived quote has no raw support")
    raw_start, raw_end = derived_support(support, derived_start, derived_end)
    return derived_start, derived_end, raw_start, raw_end
