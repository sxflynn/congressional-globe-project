"""Opt-in schema guidance for the observed S5 failure; host rules stay unchanged."""

from __future__ import annotations

import copy


def _branches(definition: dict, alternatives: list[dict]) -> dict:
    branches = []
    for properties in alternatives:
        branch = copy.deepcopy(definition)
        branch["properties"].update(properties)
        branches.append(branch)
    return {"oneOf": branches}


def specialize_conformance(schema: dict) -> None:
    """Encode local conditional obligations; exact source replay still requires the host."""
    definitions = schema["$defs"]
    definitions["Anchor"] = _branches(
        definitions["Anchor"],
        [
            {"scope": {"const": "quote"}, "raw_quote": {"type": "string", "minLength": 1}},
            {"scope": {"const": "whole_paragraph"}, "raw_quote": {"type": "null"}},
        ],
    )
    definitions["Finding"] = _branches(
        definitions["Finding"],
        [
            {
                "resolution": {"const": "proposed"},
                "basis": {"const": "visible_print"},
                "proposed_reading": {"type": "string"},
                "affected_quote": {"type": "string", "minLength": 1},
            },
            {"resolution": {"const": "unresolved"}},
        ],
    )
    schema["properties"]["status"]["description"] = (
        "findings requires findings; no_finding requires empty findings and patches, "
        "unchanged raw readings and no concerns. incomplete/unresolved require reasons, "
        "withheld null readings and no patches."
    )
    definitions["SelfCheck"]["description"] = (
        "Complete successful inspection requires all nine checked_content categories exactly "
        "once and empty remaining_concerns. Report unexamined or uncertain scope honestly."
    )
    definitions["Patch"]["description"] = (
        "Every change from RAW needs a linked patch, including retained static repairs. "
        "All nonoverlapping raw patches must reproduce the entire proposed_text exactly."
    )
