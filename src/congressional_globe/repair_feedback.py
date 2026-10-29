"""Check explicit source/image-bound feedback requirements against proposed edits.

Operator-supplied requirements must retain their actual archived human provenance.
Passing a local check is not historical acceptance or permission to launch a model.
"""

import hashlib
from typing import Literal

from pydantic import Field

from congressional_globe.bracket_cues import BracketSource, Contract
from congressional_globe.deterministic_models import ExactEdit, SupportSegment, replay_with_map
from congressional_globe.scan_models import Sha256


class FeedbackRequirement(Contract):
    source_id: str = Field(min_length=1)
    raw_sha256: Sha256
    image_sha256: Sha256
    note_id: str = Field(min_length=1)
    expected_edit: ExactEdit


class FeedbackCheck(Contract):
    note_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    raw_sha256: Sha256
    image_sha256: Sha256
    proposed_sha256: Sha256
    state: Literal["addressed_in_proposal", "not_addressed", "unresolved_mapping"]
    reason: str = Field(min_length=1)
    scope: Literal["named_feedback_only_not_whole_reading_acceptance"] = (
        "named_feedback_only_not_whole_reading_acceptance"
    )


def _verify_requirement(source, image_bytes, requirement):
    source = BracketSource.model_validate(source)
    requirement = FeedbackRequirement.model_validate(requirement)
    if (source.source_id, source.raw_sha256) != (requirement.source_id, requirement.raw_sha256):
        raise ValueError("feedback belongs to another source")
    if hashlib.sha256(image_bytes).hexdigest() != requirement.image_sha256:
        raise ValueError("feedback image is missing or changed")
    replay_with_map(source.raw_text, (requirement.expected_edit,))
    if not requirement.expected_edit.replacement.strip():
        raise ValueError("deletion feedback needs a nonblank surrounding-context replacement")
    return source, requirement


def feedback_instruction(source, image_bytes: bytes, requirement: FeedbackRequirement) -> str:
    source, requirement = _verify_requirement(source, image_bytes, requirement)
    edit = requirement.expected_edit
    return (
        f"Source-specific human feedback {requirement.note_id}; source {source.source_id}; "
        f"raw SHA-256 {source.raw_sha256}; image SHA-256 {requirement.image_sha256}. "
        f"Check the exact raw passage {edit.raw_quote!r} against the image. "
        f"The recorded case-specific requested reading is {edit.replacement!r}. "
        "Repair all other supported errors in this same assigned target. "
        "Preserve genuine punctuation and report uncertainty if the evidence disagrees. "
        "A review flag or a dictionary match is not a completed correction."
    )


def check_feedback(
    source, image_bytes: bytes, requirement: FeedbackRequirement, edits: tuple[ExactEdit, ...]
) -> FeedbackCheck:
    source, requirement = _verify_requirement(source, image_bytes, requirement)
    proposed, mapping = _replay_proposal(source.raw_text, edits)
    state, reason = _assess(proposed, requirement.expected_edit, mapping)
    return FeedbackCheck(
        note_id=requirement.note_id,
        source_id=source.source_id,
        raw_sha256=source.raw_sha256,
        image_sha256=requirement.image_sha256,
        proposed_sha256=hashlib.sha256(proposed.encode()).hexdigest(),
        state=state,
        reason=reason,
    )


def _replay_proposal(raw, edits):
    if not isinstance(edits, tuple) or len(edits) > 128:
        raise ValueError("feedback check requires at most128 frozen raw edits")
    checked = tuple(ExactEdit.model_validate(edit) for edit in edits)
    proposed, mapping = replay_with_map(raw, checked)
    if len(proposed) > 6000:
        raise ValueError("feedback proposal exceeds6000codepoints; no truncation")
    return proposed, mapping


def _assess(proposed, expected, mapping):
    start = _boundary(mapping, expected.start)
    end = _boundary(mapping, expected.end)
    if start is None or end is None:
        return "unresolved_mapping", "A larger edit hides the named raw span boundaries."
    if proposed[start:end] != expected.replacement:
        return "not_addressed", "The full named local reading differs from the requested reading."
    return "addressed_in_proposal", "The exact named local reading maps to its full original span."


def _boundary(mapping: tuple[SupportSegment, ...], position: int) -> int | None:
    for segment in mapping:
        value = _segment_boundary(segment, position)
        if value is not None:
            return value
    return None


def _segment_boundary(segment: SupportSegment, position: int) -> int | None:
    ends = {segment.raw_start: segment.derived_start, segment.raw_end: segment.derived_end}
    if position in ends:
        return ends[position]
    if segment.mapping == "exact_copy" and segment.raw_start < position < segment.raw_end:
        return segment.derived_start + position - segment.raw_start
    return None
