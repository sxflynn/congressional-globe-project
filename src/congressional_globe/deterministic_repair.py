"""Bounded deterministic proposals/signals, separate from historical acceptance."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from congressional_globe.bracket_cues import (
    BracketComparison,
    BracketReport,
    Contract,
    annotate_brackets,
    compare_brackets,
)
from congressional_globe.deterministic_lexicon import LexiconIdentity
from congressional_globe.deterministic_models import (
    ExactEdit,
    ParagraphInput,
    SupportSegment,
    derived_support,
    digest,
    replay_with_map,
)
from congressional_globe.deterministic_rules import (
    RULE_VERSION,
    Resources,
    SplitFinding,
    TokenFinding,
    proposed_edits,
    split_findings,
    token_findings,
)
from congressional_globe.scan_models import Sha256

IMPLEMENTATION_SHA256 = hashlib.sha256(
    json.dumps(
        {
            name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in [
                "deterministic_models.py",
                "deterministic_lexicon.py",
                "deterministic_geometry.py",
                "deterministic_rules.py",
                "deterministic_repair.py",
                "bracket_cues.py",
            ]
        },
        sort_keys=True,
    ).encode()
).hexdigest()


class DeterministicResult(Contract):
    contract: Literal["bounded-deterministic-proposal-v1"] = "bounded-deterministic-proposal-v1"
    rule_version: Literal["bounded-lexical-linewrap-v1"] = RULE_VERSION
    implementation_sha256: Sha256 = IMPLEMENTATION_SHA256
    input: ParagraphInput
    lexicons: tuple[LexiconIdentity, ...] = Field(max_length=3)
    geometry_registry_sha256: Sha256 | None
    proposed_text: str = Field(max_length=6000)
    proposed_sha256: Sha256
    proposed_edits: tuple[ExactEdit, ...] = Field(max_length=128)
    support_map: tuple[SupportSegment, ...] = Field(max_length=257)
    splits: tuple[SplitFinding, ...] = Field(max_length=2048)
    raw_tokens: tuple[TokenFinding, ...] = Field(max_length=6000)
    proposed_tokens: tuple[TokenFinding, ...] = Field(max_length=6000)
    brackets: BracketReport
    bracket_preservation: BracketComparison
    word_lookup: Literal["available", "not_assessed"]
    name_lookup: Literal["available", "not_assessed"]
    place_lookup: Literal["available", "not_assessed"]
    detector_state: Literal["signals_present", "no_rule_signals"]
    acceptance: Literal["unreviewed_deterministic_proposal"] = "unreviewed_deterministic_proposal"
    source_quality: Literal["not_verified"] = "not_verified"

    @model_validator(mode="after")
    def verify_structure(self) -> "DeterministicResult":
        proposed, mapping = replay_with_map(self.input.source.raw_text, self.proposed_edits)
        if (proposed, mapping, digest(proposed)) != (
            self.proposed_text,
            self.support_map,
            self.proposed_sha256,
        ):
            raise ValueError("proposed text/map does not replay from raw")
        _verify_brackets(self)
        _verify_token_spans(self)
        return self


def _verify_brackets(result: DeterministicResult) -> None:
    if result.brackets != annotate_brackets(result.input.source):
        raise ValueError("bracket source mismatch")
    if result.bracket_preservation != compare_brackets(result.input.source, result.proposed_text):
        raise ValueError("bracket preservation mismatch")


def _verify_token_spans(result: DeterministicResult) -> None:
    raw = result.input.source.raw_text
    _, raw_map = replay_with_map(raw, ())
    for token in result.raw_tokens:
        _verify_token(token, raw, raw_map, raw, "raw")
    for token in result.proposed_tokens:
        _verify_token(token, result.proposed_text, result.support_map, raw, "proposed")


def _verify_token(token: TokenFinding, text: str, mapping: tuple, raw: str, layer: str) -> None:
    if token.layer != layer or text[token.start : token.end] != token.text:
        raise ValueError("token layer quote mismatch")
    low, high = derived_support(mapping, token.start, token.end)
    if (low, high, raw[low:high]) != (token.raw_start, token.raw_end, token.raw_quote):
        raise ValueError("token raw support mismatch")


def _state(
    raw: tuple[TokenFinding, ...], proposed: tuple[TokenFinding, ...], splits: tuple
) -> Literal["signals_present", "no_rule_signals"]:
    if splits or any(token.signals for token in (*raw, *proposed)):
        return "signals_present"
    return "no_rule_signals"


def analyze_paragraph(source: ParagraphInput, resources: Resources) -> DeterministicResult:
    """Return proposals and routing candidates only; performs no provider or file writes."""
    source = ParagraphInput.model_validate(source)
    _check_geometry(source, resources)
    splits = split_findings(source, resources)
    edits = proposed_edits(splits)
    proposed, mapping = replay_with_map(source.source.raw_text, edits)
    _, raw_map = replay_with_map(source.source.raw_text, ())
    raw_tokens = token_findings(
        source.source.raw_text, source.source.raw_text, "raw", raw_map, resources
    )
    proposed_tokens = token_findings(
        source.source.raw_text, proposed, "proposed", mapping, resources
    )
    return _result(source, resources, splits, edits, proposed, mapping, raw_tokens, proposed_tokens)


def _check_geometry(source: ParagraphInput, resources: Resources) -> None:
    if source.line_status == "declared_exact" and resources.geometry is not None:
        resources.geometry.matches(source)


def _result(
    source, resources, splits, edits, proposed, mapping, raw_tokens, proposed_tokens
) -> DeterministicResult:
    return DeterministicResult(
        input=source,
        lexicons=resources.identities(),
        geometry_registry_sha256=resources.geometry.expected_sha256 if resources.geometry else None,
        proposed_text=proposed,
        proposed_sha256=digest(proposed),
        proposed_edits=edits,
        support_map=mapping,
        splits=splits,
        raw_tokens=raw_tokens,
        proposed_tokens=proposed_tokens,
        brackets=annotate_brackets(source.source),
        bracket_preservation=compare_brackets(source.source, proposed),
        word_lookup="available" if resources.words else "not_assessed",
        name_lookup="available" if resources.names else "not_assessed",
        place_lookup="available" if resources.places else "not_assessed",
        detector_state=_state(raw_tokens, proposed_tokens, splits),
    )


def verify_result(result: DeterministicResult, resources: Resources) -> None:
    """Recompute classification/edit decisions using actual pinned lookup/geometry resources."""
    checked = DeterministicResult.model_validate(result)
    if checked != analyze_paragraph(checked.input, resources):
        raise ValueError("result does not reproduce with declared resources/rules")
