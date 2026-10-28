"""Small, exact-source deterministic proposals never become accepted readings."""

import hashlib
import json
from dataclasses import replace

import pytest
from pydantic import ValidationError

from congressional_globe.bracket_cues import BracketSource
from congressional_globe.deterministic_geometry import GeometryRegistry
from congressional_globe.deterministic_lexicon import Lexicon, LexiconSpec
from congressional_globe.deterministic_models import (
    ExactEdit,
    OCRLine,
    ParagraphInput,
    derived_support,
    digest,
    replay_with_map,
)
from congressional_globe.deterministic_repair import (
    DeterministicResult,
    analyze_paragraph,
    verify_result,
)
from congressional_globe.deterministic_rules import Resources


def _lexicon(words, purpose="words"):
    data = ("\n".join(words) + "\n").encode()
    spec = LexiconSpec(
        label="synthetic fixture",
        purpose=purpose,
        sha256=hashlib.sha256(data).hexdigest(),
        provenance="Invented words for software test",
        limitations="No source truth or historical coverage",
    )
    return Lexicon(spec=spec, data=data)


def _input(raw, parts=None):
    lines = []
    cursor = 0
    for i, text in enumerate(parts or []):
        lines.append(OCRLine(line_id=f"L{i}", start=cursor, end=cursor + len(text), text=text))
        cursor += len(text) + 1
    return ParagraphInput(
        source=BracketSource(source_id="fixture:0:p", raw_text=raw, raw_sha256=digest(raw)),
        static_text=raw,
        static_sha256=digest(raw),
        static_edits=(),
        lines=tuple(lines),
        line_status="declared_exact" if parts else "unavailable",
        line_reason=None if parts else "No line evidence supplied",
        line_evidence_sha256="a" * 64 if parts else None,
    )


def _geometry(source):
    payload = [
        {
            "source_id": source.source.source_id,
            "raw_sha256": source.source.raw_sha256,
            "page_line_sha256": source.line_evidence_sha256,
            "lines": [x.model_dump(mode="json") for x in source.lines],
        }
    ]
    data = json.dumps(payload).encode()
    return GeometryRegistry(data=data, expected_sha256=hashlib.sha256(data).hexdigest())


def _resources(source, words):
    return Resources(words=_lexicon(words), geometry=_geometry(source) if source.lines else None)


def test_re_gard_join_is_exact_proposal_with_reversible_raw_support():
    source = _input("We re- gard 660.", ["We re-", "gard 660."])
    resources = _resources(source, ["we", "regard"])
    result = analyze_paragraph(source, resources)
    assert result.proposed_text == "We regard 660."
    (edit,) = result.proposed_edits
    assert edit.raw_quote == "re- gard"
    token = next(x for x in result.proposed_tokens if x.text == "regard")
    assert token.raw_quote == "re- gard"
    assert source.source.raw_text[token.raw_start : token.raw_end] == "re- gard"
    assert token.membership == "known"
    assert result.acceptance == "unreviewed_deterministic_proposal"
    assert result.source_quality == "not_verified"
    verify_result(result, resources)


@pytest.mark.parametrize(
    "raw,parts,words,reason",
    [
        ("re- gard", None, ["regard"], "line_geometry_unavailable"),
        ("re- gard", ["re- gard"], ["regard"], "not_at_adjacent_line_boundary"),
        ("re- cover", ["re-", "cover"], ["recover", "re", "cover"], "standalone_parts_ambiguous"),
        ("well- known", ["well-", "known"], ["wellknown", "well-known"], "known_hyphenated_form"),
        ("Wash- ington", ["Wash-", "ington"], ["washington"], "uppercase_or_nonlowercase"),
        ("xy- zed", ["xy-", "zed"], ["other"], "joined_form_not_known"),
        ("[re- gard]", ["[re-", "gard]"], ["regard"], "protected_bracket_span"),
        ("[re- gard", ["[re-", "gard"], ["regard"], "malformed_bracket_structure"),
    ],
)
def test_wrap_guards_retain_text_with_explicit_reason(raw, parts, words, reason):
    source = _input(raw, parts)
    result = analyze_paragraph(source, _resources(source, words))
    assert result.proposed_text == raw
    assert not result.proposed_edits
    assert result.splits[0].reason == reason


def test_missing_registry_cannot_turn_declared_line_status_into_a_join():
    source = _input("re- gard", ["re-", "gard"])
    result = analyze_paragraph(source, Resources(words=_lexicon(["regard"])))
    assert not result.proposed_edits
    assert result.splits[0].reason == "line_geometry_unavailable"


def test_forged_line_split_disagrees_with_independent_registry():
    actual = _input("re- gard", ["re- gard"])
    forged = _input("re- gard", ["re-", "gard"])
    with pytest.raises(ValueError, match="pinned geometry"):
        analyze_paragraph(forged, Resources(words=_lexicon(["regard"]), geometry=_geometry(actual)))


def test_lexicon_and_geometry_bytes_must_match_pinned_hashes():
    lex = _lexicon(["regard"])
    with pytest.raises(ValueError, match="fingerprint"):
        replace(lex, data=b"other\n")
    source = _input("re- gard", ["re-", "gard"])
    registry = _geometry(source)
    with pytest.raises(ValueError, match="fingerprint"):
        replace(registry, data=registry.data + b" ")
    with pytest.raises(ValueError, match="purpose"):
        Resources(words=_lexicon(["regard"], "names"))


def test_unavailable_resource_is_not_a_dictionary_miss_or_a_clean_result():
    source = _input("ordinary words")
    result = analyze_paragraph(source, Resources())
    assert result.word_lookup == "not_assessed"
    assert all(x.membership == "not_assessed" for x in result.raw_tokens)
    assert all("word_not_in_vocabulary" not in x.signals for x in result.raw_tokens)
    assert result.source_quality == "not_verified"


def test_known_words_can_be_detector_negative_without_being_source_verified():
    source = _input("The public doubt remains.")
    result = analyze_paragraph(
        source, Resources(words=_lexicon(["the", "public", "doubt", "remains"]))
    )
    assert result.detector_state == "no_rule_signals"
    assert all(x.routes == ("whole_unit_audit_only",) for x in result.raw_tokens)
    assert result.source_quality == "not_verified"


def test_known_names_and_plausible_numbers_still_get_verification_routes():
    source = _input("Mr. Fessenden has 1866 votes. Chapter I and MD.")
    words = _lexicon(["mr", "fessenden", "has", "1866", "votes", "chapter", "i", "and", "md"])
    result = analyze_paragraph(source, Resources(words=words))
    by_text = {x.text: x for x in result.raw_tokens}
    name = by_text["Fessenden"]
    assert name.membership == "known"
    assert "name_place_image_check_candidate" in name.routes
    numeric = [x for x in result.raw_tokens if "number" in x.categories]
    assert {x.text for x in numeric} == {"1866", "I", "MD"}
    assert all("number_image_check_candidate" in x.routes for x in numeric)
    assert result.name_lookup == "not_assessed"


@pytest.mark.parametrize("raw,token", [("H2O", "H2O"), ("item A123", "A123"), ("ra}", "}")])
def test_pattern_flags_are_candidates_without_global_substitution(raw, token):
    result = analyze_paragraph(_input(raw), Resources(words=_lexicon(["ra", "item"])))
    flagged = next(x for x in result.raw_tokens if x.text == token)
    assert "pattern_image_check_candidate" in flagged.routes
    assert result.proposed_text == raw


def test_all_caps_alone_does_not_identify_a_person():
    result = analyze_paragraph(_input("THE BILL"), Resources(words=_lexicon(["the", "bill"])))
    assert all("name_place_candidate" not in x.categories for x in result.raw_tokens)


def test_local_name_place_hints_stay_separate_from_word_lookup_and_authority():
    source = _input("Mr. Fessenden visited Sioux City.")
    resources = Resources(
        words=_lexicon(["mr", "visited"]),
        names=_lexicon(["fessenden"], "names"),
        places=_lexicon(["sioux", "city"], "places"),
    )
    result = analyze_paragraph(source, resources)
    assert result.name_lookup == "available" and result.place_lookup == "available"
    assert any("lexical_name_hint" in x.signals for x in result.raw_tokens)
    assert any("lexical_place_hint" in x.signals for x in result.raw_tokens)
    assert result.source_quality == "not_verified"


def test_static_layer_replay_and_line_coverage_reject_malformed_inputs():
    source = _input("re- gard", ["re-", "gard"])
    with pytest.raises(ValidationError):
        ParagraphInput.model_validate(
            source.model_copy(update={"static_text": "regard", "static_sha256": digest("regard")})
        )
    wrong = source.lines[0].model_copy(update={"text": "other"})
    with pytest.raises(ValidationError):
        ParagraphInput.model_validate(source.model_copy(update={"lines": (wrong, source.lines[1])}))


@pytest.mark.parametrize(
    "edits",
    [
        (ExactEdit(start=0, end=2, raw_quote="xx", replacement="r", rule_id="bad"),),
        (ExactEdit(start=0, end=2, raw_quote="re", replacement="re", rule_id="bad"),),
        (
            ExactEdit(start=0, end=2, raw_quote="re", replacement="r", rule_id="bad"),
            ExactEdit(start=1, end=2, raw_quote="e", replacement="x", rule_id="bad"),
        ),
    ],
)
def test_invalid_edit_ledgers_are_rejected(edits):
    with pytest.raises(ValueError):
        replay_with_map("re- gard", edits)


def test_result_roundtrip_and_tampered_support_or_classification_rejection():
    source = _input("re- gard", ["re-", "gard"])
    resources = _resources(source, ["regard"])
    result = analyze_paragraph(source, resources)
    assert DeterministicResult.model_validate_json(result.model_dump_json()) == result
    data = result.model_dump(mode="json")
    data["proposed_tokens"][0]["raw_quote"] = "regard"
    with pytest.raises(ValidationError):
        DeterministicResult.model_validate_json(json.dumps(data))
    data = result.model_dump(mode="json")
    data["proposed_tokens"][0]["membership"] = "unfamiliar"
    parsed = DeterministicResult.model_validate_json(json.dumps(data))
    with pytest.raises(ValueError, match="resources"):
        verify_result(parsed, resources)


def test_support_intervals_include_full_replaced_raw_span_and_keep_unicode():
    edit = ExactEdit(start=2, end=10, raw_quote="re- gard", replacement="regard", rule_id="fixture")
    text, mapping = replay_with_map("é re- gard end", (edit,))
    assert text == "é regard end"
    assert derived_support(mapping, 2, 8) == (2, 10)
    assert derived_support(mapping, 9, 12) == (11, 14)
