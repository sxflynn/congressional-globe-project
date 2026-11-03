"""Offline deterministic-first routing; signals select paragraphs, never accepted text."""

import copy
import re
from typing import Literal

from pydantic import Field

from congressional_globe.bracket_cues import Contract
from congressional_globe.deterministic_lexicon import lookup
from congressional_globe.deterministic_models import derived_support
from congressional_globe.deterministic_repair import DeterministicResult, verify_result
from congressional_globe.deterministic_rules import Resources
from congressional_globe.productive_ocr_host import (
    EvidenceRegistry,
    canonical_json,
    sha256_bytes,
    validate_host,
)

TEXT_HOST = "ocr-productive-repair-host-input-v3"
TEXT_REPLY = "ocr-productive-repair-text-reply-v3"
# Retained only for explicit reconstruction of pre-HR015v3 routing records.
NUMBER_WORDS = frozenset(
    [
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        "twenty",
        "thirty",
        "forty",
        "fifty",
        "sixty",
        "seventy",
        "eighty",
        "ninety",
        "hundred",
        "thousand",
        "million",
        "billion",
        "trillion",
        "first",
        "second",
        "third",
        "fourth",
        "fifth",
        "sixth",
        "seventh",
        "eighth",
        "ninth",
        "tenth",
        "eleventh",
        "twelfth",
        "thirteenth",
        "fourteenth",
        "fifteenth",
        "sixteenth",
        "seventeenth",
        "eighteenth",
        "nineteenth",
        "twentieth",
        "thirtieth",
        "fortieth",
        "fiftieth",
        "sixtieth",
        "seventieth",
        "eightieth",
        "ninetieth",
        "hundredth",
        "thousandth",
        "millionth",
        "billionth",
        "half",
        "halves",
        "quarter",
        "quarters",
        "dozen",
        "score",
        "once",
        "twice",
        "thrice",
        "nil",
        "nought",
        "zeroth",
    ]
)
NUMBER_FORMS = re.compile(r"\d[^\s]*|[^\W\d_]+", re.UNICODE)
ROMAN_FORM = re.compile(r"[ivxlcdm]+", re.IGNORECASE)
LEGACY_COVERAGE_GAPS = (
    "Numeric detection is conservative but incomplete: damaged or unusual written forms, "
    "non-English spellings and contextual quantities can be missed. Ambiguous Roman/word "
    "forms still route. Every detected number routes, including raw numbers later repaired. "
    "Unflagged and apparent-success audits remain required; no familiarity exemption."
)
COVERAGE_GAPS = (
    "Numeric-notation detection is conservative but incomplete; unusual/damaged numeric "
    "forms can be missed. Detected digit-bearing and ambiguous Roman notation still route, "
    "including raw numbers later repaired. Spelled-out number words use ordinary "
    "post-repair spelling checks; their numerical meaning alone does not route them. "
    "Unfamiliar/unassessed words, independent name flags and success/unflagged audits remain."
)
TEXT_PROMPT = (
    "Inspect the complete assigned target paragraphs against the registered image, including "
    "all numbers, names, genuine hyphens, unflagged words and apparent software successes. "
    "Flags are inspection hints, not verified errors. Static text is the guarded software "
    "proposal, not truth. Return one full corrected text per target, preserving supported "
    "historical writing and literal bracket passages. Never return just a flagged word or "
    "context paragraph. Supply no offsets or edit lists. If any target cannot be completely "
    "read or remains uncertain, return null text, incomplete coverage and a concrete reason. "
    "Use only the declared text-reply-v3 JSON schema. No source reading is accepted by this reply."
)
TEXT_PROMPT_V4 = TEXT_PROMPT.replace(
    "Use only the declared text-reply-v3 JSON schema.",
    "Return the text-reply-v3 JSON reply using the supplied conformance-v4 schema.",
) + (
    ' For a complete reading, set coverage to "complete", corrected_text to the entire '
    "reading, and reason to JSON null (not a string). Do not add a completion comment "
    'such as "No further action required." For an incomplete or uncertain reading, set '
    'coverage to "incomplete", corrected_text to JSON null, and reason to a nonempty '
    "explanation. Never provide a complete reading while reporting uncertainty."
)


class ParagraphRoute(Contract):
    source_id: str
    raw_sha256: str
    deterministic_sha256: str
    deterministic_result_sha256: str
    name_list_state: Literal["available", "not_assessed"]
    signals: list[dict] = Field(max_length=128)
    selection: Literal["secondary_inspection", "audit_only"]
    coverage_gaps: str = COVERAGE_GAPS


def _number_kind(word, legacy_written_numbers=False):
    if any(character.isnumeric() for character in word):
        return "digit_bearing_number_or_identifier"
    return _letter_number_kind(word, legacy_written_numbers)


def _letter_number_kind(word, legacy_written_numbers):
    if legacy_written_numbers and word.casefold() in NUMBER_WORDS:
        return "written_number_or_ambiguous_quantity"
    if ROMAN_FORM.fullmatch(word):
        return "roman_number_or_ambiguous_word"
    return None


def _number_spans(text: str, legacy_written_numbers=False):
    for match in NUMBER_FORMS.finditer(text):
        kind = _number_kind(match.group(), legacy_written_numbers)
        if kind is not None:
            yield match.start(), match.end(), kind


def _signal(raw, alias, low, high, category, flags):
    record = dict(
        paragraph_alias=alias,
        raw_start=low,
        raw_end=high,
        raw_quote=raw[low:high],
        category=category,
        flags=flags,
        route_reason="Inspect the entire target against the image; this is not a verified error.",
    )
    return {"signal_id": sha256_bytes(canonical_json(record)), **record}


def _lookup_flags(token, resources):
    flags = []
    if "word" in token.categories and token.membership != "known":
        flags.append("post_repair_word_" + token.membership)
    if "name_place_candidate" in token.categories:
        state = lookup(resources.names, token.text)
        if state != "known":
            flags.append("name_list_" + state)
    return flags


def _lookup_signals(result, resources, alias):
    raw = result.input.source.raw_text
    for token in result.proposed_tokens:
        flags = _lookup_flags(token, resources)
        if flags:
            yield _signal(raw, alias, token.raw_start, token.raw_end, "word", flags)


def _numeric_signals(result, alias, legacy_written_numbers=False):
    raw = result.input.source.raw_text
    for low, high, kind in _number_spans(raw, legacy_written_numbers):
        yield _signal(raw, alias, low, high, "number", [kind, "all_numbers_raw"])
    for low, high, kind in _number_spans(result.proposed_text, legacy_written_numbers):
        start, end = derived_support(result.support_map, low, high)
        yield _signal(raw, alias, start, end, "number", [kind, "all_numbers_post_repair"])


def route_paragraph(
    result: DeterministicResult, resources: Resources, alias: str, *, legacy_written_numbers=False
) -> ParagraphRoute:
    """Route post-repair words; legacy mode only reconstructs immutable old evidence."""
    verify_result(result, resources)
    signals = [
        *_lookup_signals(result, resources, alias),
        *_numeric_signals(result, alias, legacy_written_numbers),
    ]
    unique = {signal["signal_id"]: signal for signal in signals}
    return ParagraphRoute(
        source_id=result.input.source.source_id,
        raw_sha256=result.input.source.raw_sha256,
        deterministic_sha256=result.proposed_sha256,
        deterministic_result_sha256=sha256_bytes(result.model_dump_json().encode()),
        name_list_state=result.name_lookup,
        signals=list(unique.values()),
        selection="secondary_inspection" if unique else "audit_only",
        coverage_gaps=LEGACY_COVERAGE_GAPS if legacy_written_numbers else COVERAGE_GAPS,
    )


def _register(registry, value):
    data = canonical_json(value)
    identity = sha256_bytes(data)
    registry.files[identity] = data
    return identity


def _install_first_pass(paragraph, result, registry):
    source = result.input.source
    if (paragraph["source_id"], paragraph["raw"]["sha256"]) != (
        source.source_id,
        source.raw_sha256,
    ):
        raise ValueError("first pass belongs to another source")
    paragraph["static"] = dict(
        text=result.proposed_text,
        sha256=result.proposed_sha256,
        edits=[
            dict(
                edit_id=f"software-{i}",
                raw_start=e.start,
                raw_end=e.end,
                expected=e.raw_quote,
                replacement=e.replacement,
                reason=e.rule_id,
            )
            for i, e in enumerate(result.proposed_edits)
        ],
        rule_sha256=_register(registry, result.model_dump(mode="json")),
        lexicon_sha256=_register(registry, [x.model_dump(mode="json") for x in result.lexicons]),
    )


def prepare_text_host(
    host,
    registry: EvidenceRegistry,
    results,
    resources: Resources,
    requirements=(),
    *,
    conformance_v4: bool = False,
    legacy_written_numbers: bool = False,
):
    """Reuse a validated packet's exact image/context; freeze one request per assigned unit.

    Selection of this bounded unit (including audit-only paragraphs) is the caller's
    existing pilot assignment. This function never expands it or starts a request.
    """
    host = copy.deepcopy(validate_host(host, registry))
    payload = host["payload"]
    if payload["role"] != "productive_repair_and_self_check":
        raise ValueError("saved-proposal audits retain their existing v2 contract")
    targets = [p for p in payload["paragraphs"] if p["role"] == "target"]
    _check_assigned_results(targets, results)
    routes = []
    for paragraph in targets:
        result = results[paragraph["alias"]]
        routes.append(
            route_paragraph(
                result, resources, paragraph["alias"], legacy_written_numbers=legacy_written_numbers
            )
        )
        _install_first_pass(paragraph, result, registry)
    prompt = _feedback_prompt(payload, registry, results, requirements, conformance_v4)
    _install_diagnostics(payload, routes, registry, legacy_written_numbers)
    payload["contract"] = TEXT_HOST
    from congressional_globe.productive_ocr_runner import code_identity

    payload["code_sha256"] = _register(registry, code_identity())
    payload["prompt_sha256"] = sha256_bytes(prompt.encode())
    registry.files[payload["prompt_sha256"]] = prompt.encode()
    from congressional_globe.productive_ocr_projection import derive_reply_schema

    schema = derive_reply_schema(host, conformance_v4=conformance_v4)
    payload["response_schema_sha256"] = schema.schema_sha256
    registry.files[schema.schema_sha256] = schema.schema_text.encode()
    host["packet_sha256"] = sha256_bytes(canonical_json(payload))
    return validate_host(host, registry), tuple(routes)


def _install_diagnostics(payload, routes, registry, legacy_written_numbers):
    # Preserve feedback-conditioned signals and their source-bound provenance.
    old = payload["diagnostics"]
    signals = _merge_signals(old, routes)
    signaled = {s["paragraph_alias"] for s in signals.values()}
    config = {"routes": [r.model_dump(mode="json") for r in routes], "prior_diagnostics": old}
    negatives = _negative_targets(payload, signaled)
    payload["diagnostics"] = dict(
        status="frozen",
        detector_sha256=_register(
            registry,
            dict(
                rule="all-numbers-two-stage-v3"
                if legacy_written_numbers
                else "numeric-notation-and-post-repair-words-v4"
            ),
        ),
        configuration_sha256=_register(registry, config),
        signals=list(signals.values()),
        negative_targets=negatives,
    )


def _negative_targets(payload, signaled):
    targets = [p["alias"] for p in payload["paragraphs"] if p["role"] == "target"]
    return [alias for alias in targets if alias not in signaled]


def _check_assigned_results(targets, results):
    if set(results) != {p["alias"] for p in targets}:
        raise ValueError("first pass must cover exactly the assigned targets")


def _feedback_prompt(payload, registry, results, requirements, conformance_v4):
    from congressional_globe.repair_feedback import feedback_instruction

    paragraphs = {p["source_id"]: p for p in payload["paragraphs"] if p["role"] == "target"}
    instructions = [TEXT_PROMPT_V4 if conformance_v4 else TEXT_PROMPT]
    for requirement in requirements:
        paragraph = paragraphs[requirement.source_id]
        source = results[paragraph["alias"]].input.source
        image = registry.image_bytes[payload["image"]["sha256"]]
        instructions.append(feedback_instruction(source, image, requirement))
        edit = requirement.expected_edit
        signal = _signal(
            source.raw_text,
            paragraph["alias"],
            edit.start,
            edit.end,
            "other",
            ["required_local_reading:" + edit.replacement, "human_note:" + requirement.note_id],
        )
        payload["diagnostics"]["signals"].append(signal)
    return "\n\n".join(instructions)


def _merge_signals(old, routes):
    signals = {s["signal_id"]: s for s in old["signals"] if _is_feedback(s)}
    for route in routes:
        signals.update({s["signal_id"]: s for s in route.signals})
    return signals


def _is_feedback(signal):
    explicit = {"isolated_quote", "internal_hyphen_damage", "unverified_review_candidate"}
    if explicit.intersection(signal["flags"]):
        return True
    return any(flag.startswith("required_local_reading:") for flag in signal["flags"])
