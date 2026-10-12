"""Deterministic candidate matching against a supplied subject vocabulary."""

from __future__ import annotations

import hashlib
import re

from congressional_globe.subjects import (
    EvidenceParagraph,
    SubjectEvidence,
    SubjectProposal,
    SubjectVocabulary,
    validate_subject_proposals,
)

_JOIN = re.compile(r"-\s+(?=[^\W_])", re.UNICODE)
_RULE_VERSION = "subject-cues-1"
_UNCERTAINTY = "A cue hit does not establish substantive subject scope."


def _matching_view(text: str) -> tuple[str, list[int]]:
    """Casefold text per source character and optionally join hyphenated wraps."""
    chars: list[str] = []
    offsets: list[int] = []
    index = 0
    while index < len(text):
        joined = _JOIN.match(text, index)
        if joined is not None and index > 0 and text[index - 1].isalnum():
            index = joined.end()
            continue
        folded = text[index].casefold()
        chars.extend(folded)
        offsets.extend([index] * len(folded))
        index += 1
    return "".join(chars), offsets


def _word_character(char: str) -> bool:
    return char.isalnum() or char == "_"


def _has_boundaries(text: str, start: int, end: int) -> bool:
    return (start == 0 or not _word_character(text[start - 1])) and (
        end == len(text) or not _word_character(text[end])
    )


def _evidence(paragraph: EvidenceParagraph, raw_start: int, raw_end: int) -> SubjectEvidence:
    quote = paragraph.text[raw_start:raw_end]
    return SubjectEvidence(
        paragraph_id=paragraph.paragraph_id,
        item_identifier=paragraph.item_identifier,
        part_number=paragraph.part_number,
        scan_leaf=paragraph.scan_leaf,
        printed_page=paragraph.printed_page,
        hocr_page_id=paragraph.hocr_page_id,
        hocr_line_ids=list(paragraph.hocr_line_ids),
        bbox=paragraph.bbox,
        text_layer=paragraph.text_layer,
        text_sha256=paragraph.text_sha256 or "",
        start_char=raw_start,
        end_char=raw_end,
        quote=quote,
    )


def _paragraph_matches(paragraph: EvidenceParagraph, aliases: list[str]) -> list[SubjectEvidence]:
    view, offsets = _matching_view(paragraph.text)
    found: dict[tuple[int, int], SubjectEvidence] = {}
    for alias in aliases:
        found.update(_alias_matches(paragraph, view, offsets, alias))
    return [found[key] for key in sorted(found)]


def _alias_matches(
    paragraph: EvidenceParagraph, view: str, offsets: list[int], alias: str
) -> dict[tuple[int, int], SubjectEvidence]:
    found: dict[tuple[int, int], SubjectEvidence] = {}
    needle = alias.casefold()
    if not needle:
        return found
    position = view.find(needle)
    while position >= 0:
        finish = position + len(needle)
        if _has_boundaries(view, position, finish):
            raw_start = offsets[position]
            raw_end = offsets[finish - 1] + 1
            found[(raw_start, raw_end)] = _evidence(paragraph, raw_start, raw_end)
        position = view.find(needle, position + 1)
    return found


def _proposal_id(vocabulary: SubjectVocabulary, subject_id: str, evidence: SubjectEvidence) -> str:
    key = "\0".join((vocabulary.digest, _RULE_VERSION, subject_id, evidence.model_dump_json()))
    return "rule:" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def _basis(evidence: SubjectEvidence) -> str:
    if _JOIN.search(evidence.quote):
        return "Alias cue matched with the hyphenated-wrap joining heuristic."
    return "Case-insensitive vocabulary alias cue; human scope review required."


def match_subject_cues(
    paragraphs: list[EvidenceParagraph], vocabulary: SubjectVocabulary
) -> list[SubjectProposal]:
    """Emit pending mention-only proposals for exact vocabulary cue spans.

    Paragraph text is never modified. A cue hit is evidence of a mention only;
    human review is required before any in-scope assignment can be made.
    """
    proposals = [
        proposal
        for paragraph in paragraphs
        for proposal in _paragraph_proposals(paragraph, vocabulary)
    ]
    order = {_source_key(paragraph): index for index, paragraph in enumerate(paragraphs)}
    proposals.sort(key=lambda item: _proposal_order(item, order))
    validate_subject_proposals(proposals, vocabulary, paragraphs)
    return proposals


def _paragraph_proposals(
    paragraph: EvidenceParagraph, vocabulary: SubjectVocabulary
) -> list[SubjectProposal]:
    proposals: list[SubjectProposal] = []
    for definition in vocabulary.definitions:
        for item in _paragraph_matches(paragraph, definition.aliases):
            proposals.append(_proposal(vocabulary, definition.subject_id, item))
    return proposals


def _proposal(
    vocabulary: SubjectVocabulary, subject_id: str, evidence: SubjectEvidence
) -> SubjectProposal:
    return SubjectProposal(
        proposal_id=_proposal_id(vocabulary, subject_id, evidence),
        subject_id=subject_id,
        vocabulary_version=vocabulary.version,
        disposition="mention_only",
        evidence=[evidence],
        basis=_basis(evidence),
        uncertainty=_UNCERTAINTY,
        method="rule",
        rule_version=_RULE_VERSION,
        schema_version=vocabulary.schema_version,
        review_status="pending",
    )


def _proposal_order(
    proposal: SubjectProposal, source_order: dict[tuple[str, int, int, str, str], int]
) -> tuple[int, int, str, int]:
    evidence = proposal.evidence[0]
    return (
        source_order[_source_key(evidence)],
        evidence.start_char,
        proposal.subject_id,
        evidence.end_char,
    )


def _source_key(source: EvidenceParagraph | SubjectEvidence) -> tuple[str, int, int, str, str]:
    return (
        source.item_identifier,
        source.part_number,
        source.scan_leaf,
        source.paragraph_id,
        source.text_layer,
    )
