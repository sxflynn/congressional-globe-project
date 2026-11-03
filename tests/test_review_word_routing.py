"""HR015v3: written quantities use words; unresolved repaired words still select AI."""

import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

from congressional_globe import productive_ocr_measurement_scoped as scoped
from congressional_globe.deterministic_repair import analyze_paragraph
from congressional_globe.deterministic_rules import Resources
from congressional_globe.productive_ocr_measurement_inputs import load_scoped_inputs
from congressional_globe.productive_ocr_routing import route_paragraph

HELPERS = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_text.py")))
DET = HELPERS["DET"]


@pytest.mark.parametrize(
    "form", ["one", "two", "three", "thirteenth", "twenty-first", "half", "dozen", "once", "Two"]
)
def test_spelling_passing_number_word_alone_is_not_a_numeric_trigger(form):
    source = DET["_input"](form + ".")
    words = DET["_lexicon"]([form, "twenty", "first"])
    result = analyze_paragraph(source, Resources(words=words))
    route = route_paragraph(result, Resources(words=words), "P1")
    assert not route.signals
    assert route.selection == "audit_only"
    assert "ordinary" in route.coverage_gaps


def test_actual_two_or_three_rule_differs_from_preserved_historical_reconstruction():
    source = DET["_input"]("two or three.")
    resources = Resources(words=DET["_lexicon"](["two", "or", "three"]))
    result = analyze_paragraph(source, resources)
    current = route_paragraph(result, resources, "P1")
    legacy = route_paragraph(result, resources, "P1", legacy_written_numbers=True)
    assert current.selection == "audit_only" and not current.signals
    assert legacy.selection == "secondary_inspection"
    assert all("written_number_or_ambiguous_quantity" in s["flags"] for s in legacy.signals)
    assert current.deterministic_result_sha256 == legacy.deterministic_result_sha256


@pytest.mark.parametrize("with_dictionary", [True, False])
def test_unknown_or_unassessed_number_word_still_gets_word_inspection(with_dictionary):
    source = DET["_input"]("thirteentli.")
    resources = Resources(words=DET["_lexicon"](["thirteenth"]) if with_dictionary else None)
    route = route_paragraph(analyze_paragraph(source, resources), resources, "P1")
    assert route.selection == "secondary_inspection"
    assert all(s["category"] == "word" for s in route.signals)
    expected = "post_repair_word_unfamiliar" if with_dictionary else "post_repair_word_not_assessed"
    assert any(expected in s["flags"] for s in route.signals)


def test_successful_software_join_does_not_hide_a_different_remaining_bad_word():
    source = DET["_input"](
        "golden oppor- tunity propei-ty.", ["golden oppor-", "tunity propei-ty."]
    )
    resources = DET["_resources"](source, ["golden", "opportunity"])
    result = analyze_paragraph(source, resources)
    assert result.proposed_text == "golden opportunity propei-ty."
    route = route_paragraph(result, resources, "P1")
    assert route.selection == "secondary_inspection"
    word_signals = [s for s in route.signals if "post_repair_word_unfamiliar" in s["flags"]]
    assert word_signals
    assert all(s["raw_start"] >= source.source.raw_text.index("propei") for s in word_signals)
    assert {s["paragraph_alias"] for s in route.signals} == {"P1"}


def test_real_saved_brown_passage_still_nominates_unrepaired_property_word():
    results = HELPERS["saved_results"]()
    result = next(r for r in results if "private propei-ty" in r.input.source.raw_text)
    resources = HELPERS["saved_resources"](result)
    route = route_paragraph(result, resources, "P1")
    assert "propei-ty" in result.proposed_text
    assert route.selection == "secondary_inspection"
    assert any("post_repair_word_unfamiliar" in s["flags"] for s in route.signals)


@pytest.mark.parametrize("form", ["1862", "21st", "CCCXI", "II", "½", "Ⅳ"])
def test_numeric_notation_still_routes_despite_dictionary_pass(form):
    source = DET["_input"](form + ".")
    resources = Resources(words=DET["_lexicon"]([form]))
    route = route_paragraph(analyze_paragraph(source, resources), resources, "P1")
    assert route.selection == "secondary_inspection"
    assert any(s["category"] == "number" for s in route.signals)


def test_frozen_experiment_request_bytes_remain_unchanged_by_current_routing():
    groups = [
        scoped.PROFILES,
        scoped.S1_PROFILES,
        scoped.S2_PROFILES,
        scoped.D1_PROFILES,
        scoped.D2_PROFILES,
        scoped.COMPACT_PROFILES,
        scoped.LONG_PROFILES,
        scoped.LEAN_PROFILES,
        scoped.WHOLE_PROFILES,
        scoped.APPENDIX_PROFILES,
        scoped.IMAGE_PROFILES,
        scoped.REGION_PROFILES,
    ]
    for profiles in groups:
        spec = SimpleNamespace(contract=profiles[0])
        _, projection, _ = load_scoped_inputs(Path("."), spec)
        assert projection.body_sha256 == scoped.authority(spec)[1]
