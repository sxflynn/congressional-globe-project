"""Focused checks for deterministic subject cue evidence extraction."""

import pytest

from congressional_globe.models import PrintedPage
from congressional_globe.subject_matching import match_subject_cues
from congressional_globe.subjects import (
    EvidenceParagraph,
    SubjectDefinition,
    SubjectVocabulary,
)


def paragraph(text: str, paragraph_id: str = "p1") -> EvidenceParagraph:
    return EvidenceParagraph(
        paragraph_id=paragraph_id,
        item_identifier="globe",
        part_number=1,
        scan_leaf=10,
        printed_page=PrintedPage(detected="7"),
        hocr_page_id="page-1",
        hocr_line_ids=["line-1"],
        text_layer="original_ocr",
        text=text,
    )


def vocabulary(*aliases: str) -> SubjectVocabulary:
    return SubjectVocabulary(
        version="draft-1",
        schema_version="1",
        definitions=[
            SubjectDefinition(
                subject_id="subj.voting_rights",
                label="Voting rights",
                scope="Discussion of suffrage",
                aliases=list(aliases),
            )
        ],
    )


def test_casefold_expansion_keeps_original_unicode_offsets() -> None:
    source = paragraph("Straße and STRASSE")

    proposals = match_subject_cues([source], vocabulary("strasse"))

    assert [(item.evidence[0].start_char, item.evidence[0].end_char) for item in proposals] == [
        (0, 6),
        (11, 18),
    ]
    assert [item.evidence[0].quote for item in proposals] == ["Straße", "STRASSE"]


def test_hyphenated_line_wrap_maps_to_exact_raw_span() -> None:
    source = paragraph("elective fran-\nchise was discussed")

    proposals = match_subject_cues([source], vocabulary("elective franchise"))

    evidence = proposals[0].evidence[0]
    assert evidence.quote == "elective fran-\nchise"
    assert source.text[evidence.start_char : evidence.end_char] == evidence.quote


def test_word_boundaries_reject_substrings_but_allow_whole_phrase() -> None:
    source = paragraph("Indiana has a reserved seat; the Indian reserve was debated.")

    proposals = match_subject_cues([source], vocabulary("Indian", "reserve", "Indian reserve"))

    assert [item.evidence[0].quote for item in proposals] == [
        "Indian",
        "Indian reserve",
        "reserve",
    ]
    assert all("Indiana" not in item.evidence[0].quote for item in proposals)
    assert all("reserved" not in item.evidence[0].quote for item in proposals)


def test_proposals_are_pending_mention_only_and_source_is_unchanged() -> None:
    source = paragraph("The elective franchise was considered.")
    original = source.text

    proposals = match_subject_cues([source], vocabulary("elective franchise"))

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.disposition == "mention_only"
    assert proposal.method == "rule"
    assert proposal.review_status == "pending"
    assert proposal.review is None
    assert proposal.evidence[0].paragraph_id == source.paragraph_id
    assert proposal.evidence[0].text_sha256 == source.text_sha256
    assert source.text == original


def test_alias_free_vocabulary_is_empty_and_results_are_deterministic() -> None:
    source = paragraph("tax tax", "p2")
    vocab = vocabulary()

    first = match_subject_cues([source], vocab)
    second = match_subject_cues([source], vocab)

    assert [item.proposal_id for item in first] == [item.proposal_id for item in second]
    assert first == second == []


def test_proposal_identity_includes_source_identity() -> None:
    first_source = paragraph("Tax policy.", "same-id")
    second_source = first_source.model_copy(
        update={"item_identifier": "another-item", "scan_leaf": 11}
    )

    proposals = match_subject_cues([first_source, second_source], vocabulary("tax"))

    assert len(proposals) == 2
    assert proposals[0].proposal_id != proposals[1].proposal_id
    for proposal, source in zip(proposals, [first_source, second_source], strict=True):
        proposal.evidence[0].validate_against([source])


def test_duplicate_source_identity_is_rejected_without_cue_hits() -> None:
    source = paragraph("No cue here.")

    with pytest.raises(ValueError, match="source paragraph identities"):
        match_subject_cues([source, source.model_copy()], vocabulary("absent"))


def test_proposal_id_binds_vocabulary_content_digest() -> None:
    source = paragraph("Tax policy.")
    base = vocabulary("tax")
    changed_aliases = base.model_copy(
        update={
            "definitions": [base.definitions[0].model_copy(update={"aliases": ["tax", "revenue"]})]
        }
    )
    changed_scope = base.model_copy(
        update={
            "definitions": [base.definitions[0].model_copy(update={"scope": "Different scope"})]
        }
    )

    base_id = match_subject_cues([source], base)[0].proposal_id
    assert match_subject_cues([source], changed_aliases)[0].proposal_id != base_id
    assert match_subject_cues([source], changed_scope)[0].proposal_id != base_id
