"""Human-note obligations must be checked against actual raw support, not slogans."""

import json
from pathlib import Path

import pytest

from congressional_globe.bracket_cues import BracketSource
from congressional_globe.deterministic_models import ExactEdit
from congressional_globe.repair_feedback import (
    FeedbackRequirement,
    check_feedback,
    feedback_instruction,
)

BASE = Path("artifacts/hr012-feedback-20261029-01")


def case(index):
    row = json.loads((BASE / "case-proposals.json").read_bytes())[index]
    requirement = FeedbackRequirement.model_validate(
        {
            key: value
            for key, value in json.loads((BASE / "required-followup.json").read_bytes())[
                "source_cases"
            ][index].items()
            if key != "unit_id"
        }
    )
    return (
        row,
        BracketSource.model_validate(row["source"]),
        Path(row["image_path"]).read_bytes(),
        requirement,
    )


@pytest.mark.parametrize("index", [0, 1])
def test_prior_unchanged_or_partial_output_cannot_claim_feedback_was_fixed(index):
    row, source, image, requirement = case(index)
    prior = json.loads(
        Path("artifacts/deterministic-sample-20261028-01/results.json").read_bytes()
    )[index]
    edits = tuple(ExactEdit.model_validate(e) for e in prior["proposed_edits"])
    checked = check_feedback(source, image, requirement, edits)
    assert checked.state == "not_addressed"
    assert checked.note_id == row["human_note_id"]
    instruction = feedback_instruction(source, image, requirement)
    assert requirement.expected_edit.raw_quote in instruction
    assert requirement.expected_edit.replacement in instruction
    assert source.raw_sha256 in instruction
    assert "all other supported errors" in instruction


@pytest.mark.parametrize("index", [0, 1])
def test_separate_source_checked_copy_addresses_only_named_feedback_not_whole_reading(index):
    row, source, image, requirement = case(index)
    edits = tuple(ExactEdit.model_validate(e) for e in row["all_edits_from_raw"])
    checked = check_feedback(source, image, requirement, edits)
    assert checked.state == "addressed_in_proposal"
    assert checked.proposed_sha256 == row["derived_sha256"]
    assert checked.scope == "named_feedback_only_not_whole_reading_acceptance"
    assert source.raw_text == row["source"]["raw_text"]


def test_equivalent_smaller_apostrophe_deletion_has_exact_context_support():
    _, source, image, requirement = case(0)
    pos = source.raw_text.index("' ")
    edit = ExactEdit(start=pos, end=pos + 2, raw_quote="' ", replacement="", rule_id="fixture")
    assert check_feedback(source, image, requirement, (edit,)).state == "addressed_in_proposal"


def test_equivalent_subword_letter_and_hyphen_change_can_address_property():
    _, source, image, requirement = case(1)
    pos = source.raw_text.index("i-ty")
    edit = ExactEdit(start=pos, end=pos + 2, raw_quote="i-", replacement="r", rule_id="fixture")
    assert check_feedback(source, image, requirement, (edit,)).state == "addressed_in_proposal"


def test_deleting_larger_passage_and_adding_expected_word_is_not_a_local_fix():
    _, source, image, requirement = case(1)
    edit = ExactEdit(
        start=0,
        end=len(source.raw_text),
        raw_quote=source.raw_text,
        replacement="property",
        rule_id="bad fixture",
    )
    assert check_feedback(source, image, requirement, (edit,)).state == "unresolved_mapping"


def test_repeated_requested_word_is_not_the_requested_local_reading():
    _, source, image, requirement = case(1)
    edit = requirement.expected_edit.model_copy(update={"replacement": "property property"})
    assert check_feedback(source, image, requirement, (edit,)).state == "not_addressed"


def test_wrong_source_image_and_expected_span_are_rejected_before_instructions_or_checks():
    _, source, image, requirement = case(1)
    with pytest.raises(ValueError, match="image"):
        feedback_instruction(source, image + b"x", requirement)
    with pytest.raises(ValueError, match="another source"):
        check_feedback(source.model_copy(update={"source_id": "other:1:p"}), image, requirement, ())
    bad = requirement.expected_edit.model_copy(update={"raw_quote": "different"})
    with pytest.raises(ValueError, match="exact raw quote"):
        check_feedback(source, image, requirement.model_copy(update={"expected_edit": bad}), ())


def test_extra_unsupported_words_inside_named_edit_cannot_pass_local_check():
    _, source, image, requirement = case(1)
    bad = requirement.expected_edit.model_copy(update={"replacement": "property invented"})
    assert check_feedback(source, image, requirement, (bad,)).state == "not_addressed"


def test_replacement_with_missing_context_words_cannot_claim_mark_was_removed_safely():
    _, source, image, requirement = case(0)
    bad = requirement.expected_edit.model_copy(update={"replacement": "loyal"})
    assert check_feedback(source, image, requirement, (bad,)).state == "not_addressed"


def test_proposal_limits_and_no_context_deletion_requirement_fail_closed():
    _, source, image, requirement = case(1)
    oversized = requirement.expected_edit.model_copy(update={"replacement": "x" * 6001})
    with pytest.raises(ValueError, match="6000codepoints"):
        check_feedback(source, image, requirement, (oversized,))
    with pytest.raises(ValueError, match="128"):
        check_feedback(source, image, requirement, (requirement.expected_edit,) * 129)
    deletion = requirement.expected_edit.model_copy(update={"replacement": ""})
    with pytest.raises(ValueError, match="surrounding-context"):
        check_feedback(
            source, image, requirement.model_copy(update={"expected_edit": deletion}), ()
        )
