"""Quote-anchored v2 reading replies with deterministic host-derived offsets."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from congressional_globe.reading_contracts import (
    EvidenceSpan,
    ReadingCandidate,
    ReadingPatch,
    ReadingReply,
    UncertainReading,
    validate_reply,
)
from congressional_globe.scan_models import NonBlank


class QuoteReadingPatch(BaseModel):
    """A proposed change anchored by exact source wording, never coordinates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: NonBlank
    old: str = Field(min_length=1)
    new: str
    image_ids: list[NonBlank] = Field(min_length=1)
    reason: NonBlank


class QuoteUncertainReading(BaseModel):
    """An uncertainty anchor; empty old text denotes the whole paragraph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: NonBlank
    old: str
    reason: NonBlank


class QuoteReadingReply(BaseModel):
    """v2 reply contract: source quotes replace model-authored offsets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    unit_id: NonBlank
    status: Literal["unchanged", "proposed", "needs_review"]
    patches: list[QuoteReadingPatch]
    uncertain: list[QuoteUncertainReading]


def validate_quote_reply(
    unit: ReadingCandidate,
    reply: QuoteReadingReply,
    image_coverage: dict[str, list[EvidenceSpan]],
) -> tuple[ReadingReply, dict[str, dict]]:
    """Resolve exact unique anchors, then pass the existing v1 guard unchanged."""
    if unit.id != reply.unit_id:
        raise ValueError("reply unit ID mismatch")
    target_order = {paragraph.source_id: index for index, paragraph in enumerate(unit.target)}
    targets = {paragraph.source_id: paragraph for paragraph in unit.target}
    patches = [_derive_patch(patch, targets) for patch in reply.patches]
    uncertain = [_derive_uncertainty(span, targets) for span in reply.uncertain]
    patches.sort(key=lambda patch: (target_order[patch.source_id], patch.start, patch.end))
    uncertain.sort(key=lambda span: (target_order[span.source_id], span.start, span.end))
    _reject_uncertainty_overlaps(uncertain)
    parsed = ReadingReply(
        unit_id=reply.unit_id,
        status=reply.status,
        patches=patches,
        uncertain=uncertain,
    )
    derived = validate_reply(unit, parsed, image_coverage)
    return parsed, derived


def _derive_patch(patch: QuoteReadingPatch, targets: dict) -> ReadingPatch:
    paragraph = _target(patch.source_id, targets, "patch")
    start, end = _unique_quote(paragraph.raw, patch.old)
    return ReadingPatch(
        source_id=patch.source_id,
        start=start,
        end=end,
        old=patch.old,
        new=patch.new,
        image_ids=patch.image_ids,
        reason=patch.reason,
    )


def _derive_uncertainty(span: QuoteUncertainReading, targets: dict) -> UncertainReading:
    paragraph = _target(span.source_id, targets, "uncertainty")
    if span.old == "":
        if not paragraph.raw:
            raise ValueError("whole-paragraph uncertainty requires nonempty source text")
        start, end = 0, len(paragraph.raw)
    else:
        start, end = _unique_quote(paragraph.raw, span.old)
    return UncertainReading(source_id=span.source_id, start=start, end=end, reason=span.reason)


def _target(source_id: str, targets: dict, kind: str):
    if source_id not in targets:
        raise ValueError(f"{kind} references non-target paragraph")
    return targets[source_id]


def _unique_quote(text: str, quote: str) -> tuple[int, int]:
    starts = [index for index in range(len(text)) if text.startswith(quote, index)]
    if len(starts) != 1:
        raise ValueError("source quote must occur exactly once in target paragraph")
    start = starts[0]
    return start, start + len(quote)


def _reject_uncertainty_overlaps(spans: list[UncertainReading]) -> None:
    previous: dict[str, int] = {}
    for span in spans:
        if span.start < previous.get(span.source_id, 0):
            raise ValueError("uncertainty spans overlap")
        previous[span.source_id] = span.end
