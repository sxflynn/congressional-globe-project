"""Source-bound bracket candidates preserve literal text without inventing events."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from congressional_globe.bracket_cues import (
    RULE_SHA256,
    BracketComparison,
    BracketReport,
    BracketSource,
    annotate_brackets,
    compare_brackets,
)


def _source(text, source_id="fixture:0:paragraph-1"):
    return BracketSource(
        source_id=source_id, raw_text=text, raw_sha256=hashlib.sha256(text.encode()).hexdigest()
    )


def test_real_exposed_hammer_passage_maps_exact_original_source():
    packet = json.loads(Path("docs/review-packets/HR-010-v1.json").read_text())
    item = packet["questions"][0]["evidence"][1]
    raw = "[Here the hammer fell.]"
    assert item["text"].count(raw) == 2
    source = _source(raw, "congressionalglo00unit:873:par_000873_000007")
    assert source.raw_sha256 == "42641e430e0060ec06561d5dc2ad29ba1854ee5e26dc44089947da821226f1ef"
    report = annotate_brackets(source)
    (cue,) = report.annotations
    assert (cue.start, cue.end, cue.text) == (0, len(raw), raw)
    assert cue.literal_cue == "hammer_fell"
    assert cue.kind == "event_cue"
    assert cue.status == "literal_candidate"
    assert report.source.raw_text == raw


@pytest.mark.parametrize(
    "text,kind,cue",
    [
        ("[Laughter.]", "event_cue", "laughter"),
        ("[ lots\nof LAUGHTER. ]", "event_cue", "laughter"),
        ("[Loud applause.]", "event_cue", "applause"),
        ("[42]", "numeric_marker", "unknown"),
        ("[42, 43]", "numeric_marker", "unknown"),
        ("[sic.]", "editorial_marker", "unknown"),
        ("[unclear]", "editorial_marker", "unknown"),
        ("[?]", "editorial_marker", "unknown"),
        ("[...]", "editorial_marker", "unknown"),
        ("[]", "unknown", "unknown"),
        ("[Laughter?]", "unknown", "unknown"),
        ("[No laughter.]", "unknown", "unknown"),
        ("[Laughter and applause.]", "unknown", "unknown"),
        ("[A word about laughter]", "unknown", "unknown"),
        ("[Mr. Smith laughs.]", "unknown", "unknown"),
    ],
)
def test_literal_rules_do_not_promote_unknown_words_to_events(text, kind, cue):
    report = annotate_brackets(_source(text))
    (annotation,) = report.annotations
    assert annotation.kind == kind
    assert annotation.literal_cue == cue
    assert annotation.text == text
    assert not report.issues


def test_unicode_offsets_duplicates_and_id_stability():
    raw = "é🙂 [Laughter.] and [Laughter.]"
    report = annotate_brackets(_source(raw))
    first, second = report.annotations
    assert first.start == 3
    assert first.annotation_id != second.annotation_id
    assert [raw[a.start : a.end] for a in report.annotations] == ["[Laughter.]", "[Laughter.]"]
    assert report == annotate_brackets(_source(raw))
    assert (
        first.annotation_id
        != annotate_brackets(_source(raw, "fixture:1:paragraph-1")).annotations[0].annotation_id
    )
    assert report.rules_sha256 == RULE_SHA256


@pytest.mark.parametrize(
    "text,codes",
    [
        ("[Laughter.", ["unmatched_open"]),
        ("Laughter.]", ["unmatched_close"]),
        ("[[Laughter.]]", ["nested_brackets"]),
        ("[[x]", ["unmatched_open", "nested_brackets"]),
        ("[A [Laughter.] B]", ["nested_brackets"]),
        ("][", ["unmatched_close", "unmatched_open"]),
    ],
)
def test_malformed_or_nested_regions_are_not_event_candidates(text, codes):
    report = annotate_brackets(_source(text))
    assert not report.annotations
    assert [issue.code for issue in report.issues] == codes
    assert report.inspection_state == "needs_review"
    assert all(text[i.start : i.end] == i.text for i in report.issues)


def test_malformed_region_does_not_swallow_following_balanced_candidate():
    report = annotate_brackets(_source("[[bad]] [Laughter.] stray] [sic]"))
    assert [a.text for a in report.annotations] == ["[Laughter.]", "[sic]"]
    assert [i.code for i in report.issues] == ["nested_brackets", "unmatched_close"]
    assert report.inspection_state == "needs_review"


@pytest.mark.parametrize(
    "field,value",
    [
        ("text", "[Applause.]"),
        ("start", 1),
        ("end", 1),
        ("literal_cue", "applause"),
        ("kind", "unknown"),
        ("annotation_id", "0" * 64),
        ("raw_sha256", "0" * 64),
        ("source_id", "fixture:9:other"),
    ],
)
def test_report_revalidation_rejects_tampered_annotation(field, value):
    data = annotate_brackets(_source("[Laughter.]")).model_dump(mode="json")
    data["annotations"][0][field] = value
    with pytest.raises(ValidationError):
        BracketReport.model_validate_json(json.dumps(data))


def test_report_revalidation_rejects_missing_candidates_and_false_issue():
    data = annotate_brackets(_source("[Laughter.]")).model_dump(mode="json")
    data["annotations"] = []
    with pytest.raises(ValidationError):
        BracketReport.model_validate_json(json.dumps(data))
    data = annotate_brackets(_source("]")).model_dump(mode="json")
    data["issues"][0]["text"] = "["
    with pytest.raises(ValidationError):
        BracketReport.model_validate_json(json.dumps(data))


def test_source_hash_bounds_and_copy_bypass_are_rejected():
    with pytest.raises(ValidationError):
        BracketSource(source_id="fixture:0:p", raw_text="x", raw_sha256="0" * 64)
    with pytest.raises(ValidationError):
        _source("x" * 6001)
    with pytest.raises(ValidationError):
        _source("[]" * 257)
    bad = _source("[Laughter.]").model_copy(update={"raw_text": "[Applause.]"})
    with pytest.raises(ValidationError):
        annotate_brackets(bad)


@pytest.mark.parametrize(
    "proposed",
    [
        "The speaker continued.",
        "The speaker continued. [Applause.]",
        "The speaker continued. [laughter.]",
        "The speaker continued. [Laughter.] [Laughter.]",
    ],
)
def test_deleted_changed_normalized_or_duplicated_cue_requires_attention(proposed):
    check = compare_brackets(_source("The speaker continued. [Laughter.]"), proposed)
    assert check.status == "changed_literal_sequence"


def test_external_word_repairs_can_shift_bracket_offsets_without_changing_literal_sequence():
    check = compare_brackets(
        _source("Tlie speaker said GCO. [Here the hammer fell.]"),
        "The speaker said 660. [Here the hammer fell.]",
    )
    assert check.status == "same_literal_sequence"
    assert check.proposed_quotes == ("[Here the hammer fell.]",)
    assert check.source_report.source.raw_text.startswith("Tlie")
    assert BracketComparison.model_validate_json(check.model_dump_json()) == check


def test_malformed_proposal_is_review_needed_and_not_repaired():
    check = compare_brackets(_source("[Laughter.]"), "[Laughter.")
    assert check.status == "needs_review"
    assert check.proposed_text == "[Laughter."
    assert check.proposed_issues[0].code == "unmatched_open"


def test_comparison_rejects_tampered_status_hash_and_inferred_fields():
    check = compare_brackets(_source("[Laughter.]"), "[Applause.]")
    for update in [
        {"status": "same_literal_sequence"},
        {"proposed_sha256": "0" * 64},
        {"speaker": "Mr. Smith"},
    ]:
        data = {**check.model_dump(mode="json"), **update}
        with pytest.raises(ValidationError):
            BracketComparison.model_validate_json(json.dumps(data))


def test_empty_source_and_non_square_brackets_do_not_claim_no_events():
    report = annotate_brackets(_source("(Laughter.) \uff3bApplause.\uff3d"))
    assert not report.annotations
    assert report.inspection_state == "complete"
    assert not annotate_brackets(_source("")).annotations


def test_proposed_text_bounds_and_nested_report_copy_are_revalidated():
    source = _source("[Laughter.]")
    with pytest.raises(ValueError):
        compare_brackets(source, "[]" * 257)
    report = annotate_brackets(source).model_copy(update={"annotations": ()})
    check = compare_brackets(source, "[Laughter.]")
    with pytest.raises(ValidationError):
        BracketComparison.model_validate(check.model_copy(update={"source_report": report}))
