"""Focused validation tests for provider-neutral subject tagging contracts."""

import hashlib

import pytest
from pydantic import ValidationError

from congressional_globe.models import BoundingBox, PrintedPage
from congressional_globe.subjects import (
    EvidenceParagraph,
    SubjectDefinition,
    SubjectEvidence,
    SubjectProposal,
    SubjectReview,
    SubjectVocabulary,
    reviewed_in_scope_subject_ids,
    validate_subject_proposals,
)


def _paragraph() -> EvidenceParagraph:
    return EvidenceParagraph(
        paragraph_id="p-1",
        item_identifier="globe39part1",
        part_number=1,
        scan_leaf=12,
        printed_page=PrintedPage(detected="42"),
        hocr_page_id="page_42",
        hocr_line_ids=["line_1", "line_2"],
        bbox=BoundingBox(left=1, top=2, right=30, bottom=12),
        text_layer="original_ocr",
        text="Debate on civil rights continued.",
    )


def _evidence(paragraph: EvidenceParagraph) -> SubjectEvidence:
    assert paragraph.text_sha256 is not None
    return SubjectEvidence(
        paragraph_id=paragraph.paragraph_id,
        item_identifier=paragraph.item_identifier,
        part_number=paragraph.part_number,
        scan_leaf=paragraph.scan_leaf,
        printed_page=paragraph.printed_page,
        hocr_page_id=paragraph.hocr_page_id,
        hocr_line_ids=paragraph.hocr_line_ids,
        bbox=paragraph.bbox,
        text_layer=paragraph.text_layer,
        text_sha256=paragraph.text_sha256,
        start_char=10,
        end_char=22,
        quote="civil rights",
    )


def _vocabulary() -> SubjectVocabulary:
    return SubjectVocabulary(
        version="draft-1",
        schema_version="subject-schema-1",
        definitions=[
            SubjectDefinition(
                subject_id="subj.civil_rights",
                label="Civil rights",
                scope="Civil rights claims and policy",
            )
        ],
    )


def test_vocabulary_rejects_duplicate_ids() -> None:
    definition = SubjectDefinition(subject_id="x", label="X", scope="scope")
    with pytest.raises(ValidationError, match="unique"):
        SubjectVocabulary(version="1", schema_version="1", definitions=[definition, definition])


def test_evidence_requires_matching_identity_hash_and_exact_unicode_span() -> None:
    paragraph = _paragraph()
    evidence = _evidence(paragraph)
    evidence.validate_against([paragraph])

    with pytest.raises(ValueError, match="quote"):
        evidence.model_copy(update={"quote": "civil right"}).validate_against([paragraph])
    with pytest.raises(ValueError, match="unknown evidence source"):
        evidence.model_copy(update={"scan_leaf": 13}).validate_against([paragraph])
    with pytest.raises(ValidationError, match="text_sha256"):
        EvidenceParagraph.model_validate({**paragraph.model_dump(), "text_sha256": "0" * 64})


def test_model_proposal_requires_versions_and_review_record() -> None:
    paragraph = _paragraph()
    base: dict[str, object] = {
        "proposal_id": "prop-1",
        "subject_id": "subj.civil_rights",
        "vocabulary_version": "draft-1",
        "disposition": "in_scope",
        "evidence": [_evidence(paragraph)],
        "basis": "The paragraph argues for civil rights.",
        "method": "model",
        "schema_version": "subject-schema-1",
    }
    with pytest.raises(ValidationError, match="configuration version"):
        SubjectProposal.model_validate(base)
    proposal = SubjectProposal.model_validate(
        {**base, "model_version": "gpt-mini", "prompt_version": "tag-v1"}
    )
    assert proposal.review_status == "pending"
    with pytest.raises(ValidationError, match="human review record"):
        SubjectProposal.model_validate({**proposal.model_dump(), "review_status": "reviewed"})


def test_only_human_reviewed_in_scope_known_subjects_are_returned() -> None:
    paragraph = _paragraph()
    proposal = SubjectProposal(
        proposal_id="prop-1",
        subject_id="subj.civil_rights",
        disposition="in_scope",
        evidence=[_evidence(paragraph)],
        basis="Explicit argument.",
        method="rule",
        rule_version="rules-1",
        vocabulary_version="draft-1",
        schema_version="subject-schema-1",
    )
    review = SubjectReview(
        reviewer_id="human-1",
        reviewed_at="2026-10-12T12:00:00Z",
        decision="in_scope",
        note="Confirmed for this evaluation sample.",
    )
    reviewed = proposal.model_copy(update={"review_status": "reviewed", "review": review})
    assert reviewed_in_scope_subject_ids([proposal], _vocabulary(), [paragraph]) == set()
    assert reviewed_in_scope_subject_ids([reviewed], _vocabulary(), [paragraph]) == {
        "subj.civil_rights"
    }
    with pytest.raises(ValueError, match="absent from"):
        reviewed_in_scope_subject_ids(
            [reviewed.model_copy(update={"subject_id": "unknown-id"})],
            _vocabulary(),
            [paragraph],
        )


def test_paragraph_hash_is_derived_from_exact_text() -> None:
    paragraph = _paragraph()
    assert paragraph.text_sha256 == hashlib.sha256(paragraph.text.encode()).hexdigest()


def test_proposal_validation_binds_vocabulary_and_all_source_anchors() -> None:
    paragraph = _paragraph()
    proposal = SubjectProposal(
        proposal_id="prop-1",
        subject_id="subj.civil_rights",
        vocabulary_version="draft-1",
        disposition="in_scope",
        evidence=[_evidence(paragraph)],
        basis="Explicit argument.",
        method="rule",
        rule_version="rules-1",
        schema_version="subject-schema-1",
    )
    with pytest.raises(ValueError, match="identity"):
        bad_evidence = proposal.evidence[0].model_copy(update={"hocr_page_id": "wrong"})
        validate_subject_proposals(
            [proposal.model_copy(update={"evidence": [bad_evidence]})],
            _vocabulary(),
            [paragraph],
        )
    with pytest.raises(ValueError, match="vocabulary version"):
        validate_subject_proposals(
            [proposal.model_copy(update={"vocabulary_version": "old"})],
            _vocabulary(),
            [paragraph],
        )
    with pytest.raises(ValueError, match="subject ID"):
        validate_subject_proposals(
            [proposal.model_copy(update={"subject_id": "missing"})],
            _vocabulary(),
            [paragraph],
        )
    with pytest.raises(ValueError, match="proposal IDs must be unique"):
        validate_subject_proposals([proposal, proposal], _vocabulary(), [paragraph])


def test_same_local_paragraph_id_is_safe_across_distinct_sources() -> None:
    first = _paragraph()
    second = first.model_copy(update={"item_identifier": "other_item", "scan_leaf": 13})
    evidence = _evidence(second)
    evidence.validate_against([first, second])
    with pytest.raises(ValueError, match="ambiguous"):
        evidence.validate_against([second, second])


def test_vocabulary_rejects_blank_aliases() -> None:
    with pytest.raises(ValidationError, match="must not be blank"):
        SubjectDefinition(
            subject_id="subj.empty",
            label="Blank alias",
            scope="Test scope",
            aliases=["   "],
        )


def test_vocabulary_digest_tracks_content_not_just_version() -> None:
    first = _vocabulary()
    changed = first.model_copy(
        update={
            "definitions": [
                first.definitions[0].model_copy(update={"aliases": ["elective franchise"]})
            ]
        }
    )
    assert first.version == changed.version
    assert first.digest != changed.digest
