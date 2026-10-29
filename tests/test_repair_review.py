"""Missed-error regressions: signals are not repairs or historical acceptance."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from congressional_globe.bracket_cues import BracketSource
from congressional_globe.deterministic_lexicon import Lexicon, LexiconSpec
from congressional_globe.deterministic_models import digest
from congressional_globe.repair_review import (
    ReviewReport,
    provider_signals,
    review_missed_errors,
    verify_review_report,
)


def source(raw):
    return BracketSource(source_id="fixture:1:p", raw_text=raw, raw_sha256=digest(raw))


def lexicon(words):
    data = ("\n".join(words) + "\n").encode()
    import hashlib

    return Lexicon(
        spec=LexiconSpec(
            label="synthetic word hints",
            purpose="words",
            sha256=hashlib.sha256(data).hexdigest(),
            provenance="Invented local test dictionary",
            limitations="Not historical evidence or permission to change text",
        ),
        data=data,
    )


def paragraph(report, alias="P1"):
    raw = {"text": report.source.raw_text, "sha256": report.source.raw_sha256}
    return {
        "alias": alias,
        "source_id": report.source.source_id,
        "part_number": 1,
        "scan_leaf": 1,
        "role": "target",
        "raw": raw,
        "static": {**raw, "edits": [], "rule_sha256": "a" * 64, "lexicon_sha256": "b" * 64},
    }


def cases():
    return json.loads(Path("artifacts/hr012-feedback-20261029-01/case-proposals.json").read_bytes())


def test_actual_stray_mark_gets_exact_review_route_missing_from_old_tokenizer():
    from congressional_globe.deterministic_rules import TOKEN

    actual = cases()[0]["source"]
    report = review_missed_errors(BracketSource.model_validate(actual))
    (mark,) = [f for f in report.findings if f.kind == "isolated_quote"]
    assert mark.raw_quote == "'"
    assert actual["raw_text"][mark.start - 6 : mark.end + 4] == "loyal ' and"
    assert not any(m.group() == "'" for m in TOKEN.finditer(actual["raw_text"]))
    signal = next(s for s in provider_signals(report, paragraph(report)) if s.category == "other")
    assert signal.raw_quote == "'" and signal.raw_start == mark.start
    assert signal.route_reason.startswith("Inspect the original image")
    assert report.proposed_text == actual["raw_text"]


def test_actual_combined_damage_routes_property_candidate_without_dictionary_acceptance():
    actual = cases()[1]["source"]
    words = lexicon(["property"])
    report = review_missed_errors(BracketSource.model_validate(actual), words)
    (finding,) = report.findings
    assert finding.raw_quote == "propei-ty"
    assert finding.candidate_readings == ("property",)
    assert finding.route == "image_review_required"
    assert report.proposed_text.endswith("propei-ty.")
    assert report.source_quality == "not_verified"
    assert (
        provider_signals(report, paragraph(report), words)[0].flags[0] == "internal_hyphen_damage"
    )
    verify_review_report(ReviewReport.model_validate_json(report.model_dump_json()), words)


@pytest.mark.parametrize(
    "text",
    [
        "don't alter States' rights.",
        "'tis the nation's law.",
        "don\u2019t alter States\u2019 rights.",
    ],
)
def test_attached_genuine_apostrophes_are_not_isolated_marks(text):
    report = review_missed_errors(source(text))
    assert not report.findings
    assert report.proposed_text == text
    assert report.source_quality == "not_verified"


@pytest.mark.parametrize("mark", ["'", "\u2018", "\u2019"])
def test_spaced_quote_marks_route_for_inspection_and_are_never_deleted(mark):
    text = f"He said {mark} yes {mark} and left."
    report = review_missed_errors(source(text))
    assert len(report.findings) == 2
    assert all(f.candidate_readings == () for f in report.findings)
    assert report.proposed_text == text


@pytest.mark.parametrize("text", ["well-known", "state-of-the-art", "twenty-one"])
def test_known_genuine_hyphens_preserved(text):
    report = review_missed_errors(source(text), lexicon([text]))
    assert not report.findings
    assert report.proposed_text == text


def test_unknown_genuine_hyphen_may_be_flagged_but_never_silently_joined():
    report = review_missed_errors(source("well-known"), lexicon(["wellknown"]))
    assert report.findings[0].candidate_readings == ("wellknown",)
    assert report.proposed_text == "well-known"


def test_missing_vocabulary_is_explicit_instead_of_an_empty_clean_result():
    report = review_missed_errors(source("propei-ty"))
    assert report.words is None
    assert report.findings[0].reason == "word_resource_unavailable"
    assert report.findings[0].candidate_readings == ()


def test_long_tokens_keep_the_entire_source_and_route_without_candidate_search():
    text = "a" * 33 + "-" + "b" * 33
    report = review_missed_errors(source(text), lexicon(["other"]))
    assert report.findings[0].reason == "token_exceeds_candidate_limit"
    assert report.findings[0].raw_quote == text


def test_resource_and_finding_overflow_fail_without_partial_reports():
    with pytest.raises(ValidationError):
        review_missed_errors(source(" ' " * 129))
    words = lexicon([letter + "a" for letter in "bcdefghijklmnopqrstuvwxyz"])
    with pytest.raises(ValueError, match="candidate limit"):
        review_missed_errors(source("a-a"), words)


def test_serialized_tamper_and_copied_instances_cannot_change_source_or_candidates():
    words = lexicon(["property"])
    report = review_missed_errors(source("propei-ty"), words)
    finding = report.findings[0].model_copy(update={"candidate_readings": ("properly",)})
    forged = report.model_copy(update={"findings": (finding,)})
    with pytest.raises(ValueError, match="does not reproduce"):
        provider_signals(forged, paragraph(forged), words)
    altered = report.model_copy(update={"proposed_text": "property"})
    with pytest.raises(ValueError, match="preserve original"):
        ReviewReport.model_validate(altered)
    with pytest.raises(ValueError, match="does not reproduce"):
        verify_review_report(report, lexicon(["properly"]))


def test_signal_identity_is_source_bound_and_alias_validation_is_enforced():
    first = review_missed_errors(source("a ' b"))
    other = review_missed_errors(source("c ' d"))
    assert (
        provider_signals(first, paragraph(first))[0].signal_id
        != provider_signals(other, paragraph(other))[0].signal_id
    )
    with pytest.raises(ValidationError):
        provider_signals(first, paragraph(first, "P0"))


def test_valid_alias_pointing_to_different_source_or_context_is_rejected():
    report = review_missed_errors(source("a ' b"))
    wrong = paragraph(report, "P2")
    wrong["source_id"] = "another:1:p"
    with pytest.raises(ValueError, match="exact target source"):
        provider_signals(report, wrong)
    wrong = paragraph(report, "P2")
    wrong["role"] = "context"
    with pytest.raises(ValueError, match="exact target source"):
        provider_signals(report, wrong)


def test_same_raw_bytes_in_distinct_sources_have_different_signal_identity():
    first = review_missed_errors(source("a ' b"))
    second = review_missed_errors(first.source.model_copy(update={"source_id": "another:1:p"}))
    assert (
        provider_signals(first, paragraph(first))[0].signal_id
        != provider_signals(second, paragraph(second))[0].signal_id
    )


def test_quoted_damaged_word_is_not_hidden_by_quotation_marks():
    report = review_missed_errors(source("He wrote 'propei-ty'."), lexicon(["property"]))
    assert report.findings[0].candidate_readings == ("property",)
    assert report.proposed_text == "He wrote 'propei-ty'."


def test_finding_end_must_not_extend_beyond_the_raw_text():
    report = review_missed_errors(source("'"))
    bad = report.findings[0].model_copy(update={"end": 99})
    with pytest.raises(ValueError, match="ordered and disjoint"):
        ReviewReport.model_validate(report.model_copy(update={"findings": (bad,)}))
