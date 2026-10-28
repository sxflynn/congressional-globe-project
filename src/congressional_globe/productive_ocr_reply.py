"""Strict productive OCR v2 reply contract and host-side semantic replay."""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from congressional_globe.bracket_cues import BracketSource, compare_brackets
from congressional_globe.deterministic_models import ExactEdit, replay_with_map
from congressional_globe.productive_ocr_binding import inverse_quote_support, unique_quote_span


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Inspection(Strict):
    paragraph_alias: str = Field(pattern=r"^P([1-9]|[12][0-9]|3[0-2])$")
    image_alias: Literal["I1"]
    completeness: Literal["complete", "partial", "not_inspected"]
    image_suitability: Literal["clear", "unclear", "missing", "irrelevant"]
    reason: str | None = Field(min_length=1)


class Anchor(Strict):
    paragraph_alias: str = Field(pattern=r"^P([1-9]|[12][0-9]|3[0-2])$")
    scope: Literal["quote", "whole_paragraph"]
    raw_quote: str | None


class Finding(Strict):
    finding_id: str = Field(min_length=1)
    anchor: Anchor
    affected_layer: Literal["raw", "static", "saved_proposal"]
    affected_quote: str | None = Field(min_length=1)
    category: Literal[
        "detector_missed_damage",
        "incorrect_static_edit",
        "name_place_concern",
        "number_concern",
        "unsupported_saved_proposal",
        "source_uncertainty",
        "other_damage",
    ]
    resolution: Literal["proposed", "unresolved"]
    proposed_reading: str | None
    image_alias: Literal["I1"]
    basis: Literal["visible_print", "image_unclear", "image_unavailable", "image_irrelevant"]
    explanation: str = Field(min_length=1)


class Patch(Strict):
    finding_id: str = Field(min_length=1)
    paragraph_alias: str = Field(pattern=r"^P([1-9]|[12][0-9]|3[0-2])$")
    raw_quote: str = Field(min_length=1)
    replacement: str
    image_alias: Literal["I1"]
    reason: str = Field(min_length=1)


class Uncertainty(Strict):
    raw_quote: str | None = Field(min_length=1)
    reason: str = Field(min_length=1)


class TargetReading(Strict):
    paragraph_alias: str = Field(pattern=r"^P([1-9]|[12][0-9]|3[0-2])$")
    image_alias: Literal["I1"]
    reading_status: Literal["proposed", "unchanged", "withheld"]
    proposed_text: str | None = Field(default=None, min_length=1, max_length=6000)
    uncertainties: list[Uncertainty] = Field(max_length=32)
    reason: str | None = Field(min_length=1)


class SelfCheck(Strict):
    paragraph_alias: str = Field(pattern=r"^P([1-9]|[12][0-9]|3[0-2])$")
    coverage: Literal["complete", "partial", "not_inspected"]
    checked_content: list[
        Literal[
            "all_words",
            "names_places",
            "numbers",
            "punctuation",
            "printed_repetition",
            "bracketed_cues",
            "target_context_boundaries",
            "unflagged_text",
            "static_edits",
        ]
    ] = Field(max_length=9)
    remaining_concerns: list[str] = Field(max_length=32)

    @model_validator(mode="after")
    def unique_checks(self) -> SelfCheck:
        if len(self.checked_content) != len(set(self.checked_content)):
            raise ValueError("duplicate self-check category")
        return self


class Reply(Strict):
    contract: Literal["ocr-productive-repair-reply-v2"]
    unit_id: str = Field(min_length=1)
    role: Literal["productive_repair_and_self_check", "audit_saved_proposal"]
    status: Literal["findings", "no_finding", "incomplete", "unresolved"]
    inspections: list[Inspection] = Field(min_length=1, max_length=32)
    findings: list[Finding] = Field(max_length=32)
    patches: list[Patch] = Field(max_length=32)
    reason: str | None = Field(min_length=1)
    target_readings: list[TargetReading] = Field(max_length=32)
    self_check: list[SelfCheck] = Field(min_length=1, max_length=32)


def _targets(host_payload: dict, role: str) -> dict[str, dict]:
    payload = host_payload["payload"]
    rows = [dict(row) for row in payload["paragraphs"] if row["role"] == "target"]
    targets = _target_map(rows)
    if role == "audit_saved_proposal":
        _attach_saved_proposal(payload, targets)
    return targets


def _target_map(rows: list[dict]) -> dict[str, dict]:
    targets = {row["alias"]: row for row in rows}
    if not rows or len(targets) != len(rows):
        raise ValueError("validated host payload requires unique declared targets")
    return targets


def _attach_saved_proposal(payload: dict, targets: dict) -> None:
    proposal = payload.get("saved_proposal")
    if proposal is None:
        raise ValueError("saved-proposal audit requires a frozen proposal")
    saved = {row["paragraph_alias"]: row for row in proposal["paragraphs"]}
    if set(saved) != set(targets):
        raise ValueError("saved proposal must cover each target")
    for alias, row in targets.items():
        row["saved_proposal_text"] = saved[alias]["text"]
        row["saved_proposal_edits"] = saved[alias]["raw_edits"]


def _layer(row: dict, name: str) -> str:
    if name == "raw":
        return row["raw"]["text"]
    if name == "static":
        return row["static"]["text"]
    if name == "saved_proposal" and "saved_proposal_text" in row:
        return row["saved_proposal_text"]
    raise ValueError("requested layer is unavailable")


def _layer_edits(row: dict, name: str) -> tuple[ExactEdit, ...]:
    edits = row["saved_proposal_edits"] if name == "saved_proposal" else row["static"]["edits"]
    return tuple(
        ExactEdit(
            start=edit["raw_start"],
            end=edit["raw_end"],
            raw_quote=edit["expected"],
            replacement=edit["replacement"],
            rule_id=edit["edit_id"],
        )
        for edit in edits
    )


def _full_check(alias: str, inspections: dict, checks: dict) -> bool:
    inspection, check = inspections.get(alias), checks.get(alias)
    required = {
        "all_words",
        "names_places",
        "numbers",
        "punctuation",
        "printed_repetition",
        "bracketed_cues",
        "target_context_boundaries",
        "unflagged_text",
        "static_edits",
    }
    return bool(
        inspection
        and inspection.completeness == "complete"
        and inspection.image_suitability == "clear"
        and check
        and check.coverage == "complete"
        and required <= set(check.checked_content)
        and not check.remaining_concerns
    )


def _reply_structure(parsed: Reply, targets: dict, role: str) -> tuple[dict, dict, dict]:
    inspections = _alias_map(parsed.inspections, set(targets), "inspection")
    checks = _alias_map(parsed.self_check, set(targets), "self-check")
    readings = _reply_readings(parsed, targets, role)
    return inspections, checks, readings


def _alias_map(items: list, aliases: set, name: str) -> dict:
    result = {item.paragraph_alias: item for item in items}
    if len(result) != len(items) or set(result) != aliases:
        raise ValueError(f"{name} must cover each target exactly once")
    return result


def _reply_readings(parsed: Reply, targets: dict, role: str) -> dict:
    if role == "audit_saved_proposal":
        _check_audit_shape(parsed)
        return {}
    readings = _alias_map(parsed.target_readings, set(targets), "reading")
    return readings


def _check_audit_shape(parsed: Reply) -> None:
    if parsed.target_readings or parsed.patches:
        raise ValueError("saved-proposal audit cannot introduce readings or patches")


def _anchor_span(finding: Finding, raw: str) -> tuple[int, int]:
    anchor = finding.anchor
    if anchor.scope == "quote":
        if not anchor.raw_quote or not anchor.raw_quote.strip():
            raise ValueError("quote anchor must be nonblank")
        return unique_quote_span(raw, anchor.raw_quote)
    if anchor.raw_quote is not None:
        raise ValueError("whole-paragraph anchor has no quote")
    return 0, len(raw)


def _finding_quote_support(
    finding: Finding, row: dict, raw: str, anchor: tuple[int, int]
) -> tuple[int, int, int, int]:
    if finding.affected_quote is None:
        return _whole_paragraph_support(finding, anchor)
    if finding.affected_layer == "raw":
        return _raw_quote_support(finding, raw, anchor)
    return _derived_quote_support(finding, row, raw, anchor)


def _whole_paragraph_support(
    finding: Finding, anchor: tuple[int, int]
) -> tuple[int, int, int, int]:
    if finding.resolution != "unresolved" or finding.anchor.scope != "whole_paragraph":
        raise ValueError("null affected quote only supports unresolved whole-paragraph findings")
    return 0, 0, *anchor


def _raw_quote_support(
    finding: Finding, raw: str, anchor: tuple[int, int]
) -> tuple[int, int, int, int]:
    if finding.affected_quote is None:
        raise ValueError("raw affected quote is required")
    expected = finding.anchor.raw_quote if finding.anchor.scope == "quote" else raw
    if finding.affected_quote != expected:
        raise ValueError("raw affected quote must equal the full declared raw anchor")
    start, end = unique_quote_span(raw, finding.affected_quote)
    if start < anchor[0] or end > anchor[1]:
        raise ValueError("raw affected quote escapes declared anchor")
    return start, end, start, end


def _derived_quote_support(
    finding: Finding, row: dict, raw: str, anchor: tuple[int, int]
) -> tuple[int, int, int, int]:
    quote = finding.affected_quote
    if quote is None:
        raise ValueError("derived affected quote is required")
    layer = _layer(row, finding.affected_layer)
    span = inverse_quote_support(raw, layer, quote, _layer_edits(row, finding.affected_layer))
    if span[2] < anchor[0] or span[3] > anchor[1]:
        raise ValueError("derived quote support escapes declared raw anchor")
    return span


def _bind_findings(parsed: Reply, targets: dict) -> tuple[list[dict], dict]:
    mapped, supports = [], {}
    ids = [finding.finding_id for finding in parsed.findings]
    if len(ids) != len(set(ids)):
        raise ValueError("finding IDs must be unique")
    for finding in parsed.findings:
        alias = finding.anchor.paragraph_alias
        if alias not in targets:
            raise ValueError("finding anchors must name target paragraphs")
        row = targets[alias]
        raw = _layer(row, "raw")
        anchor = _anchor_span(finding, raw)
        x, y, raw_start, raw_end = _finding_quote_support(finding, row, raw, anchor)
        _validate_proposed_finding(finding)
        supports[finding.finding_id] = (alias, raw_start, raw_end, finding)
        mapped.append(_mapped_finding(finding, row, (x, y), (raw_start, raw_end)))
    return mapped, supports


def _validate_proposed_finding(finding: Finding) -> None:
    if finding.resolution == "proposed" and (
        finding.basis != "visible_print" or finding.proposed_reading is None
    ):
        raise ValueError("proposed finding requires visible-print basis and reading")


def _mapped_finding(
    finding: Finding, row: dict, layer_span: tuple[int, int], raw_span: tuple[int, int]
) -> dict:
    return {
        "finding": finding.model_dump(mode="json"),
        "layer_span": list(layer_span),
        "raw_support": list(raw_span),
        "raw_sha256": row["raw"]["sha256"],
    }


def _bind_patches(parsed: Reply, targets: dict, supports: dict) -> dict:
    bound = {alias: [] for alias in targets}
    for patch in parsed.patches:
        _bind_patch(patch, targets, supports, bound)
    return bound


def _bind_patch(patch: Patch, targets: dict, supports: dict, bound: dict) -> None:
    if patch.finding_id not in supports or patch.paragraph_alias not in targets:
        raise ValueError("patch has dangling finding or non-target alias")
    alias, low, high, finding = supports[patch.finding_id]
    _check_patch_link(patch, alias, low, high, finding)
    raw = _layer(targets[alias], "raw")
    start, end = unique_quote_span(raw, patch.raw_quote)
    if start < low or end > high or patch.raw_quote == patch.replacement:
        raise ValueError("patch is outside finding support or is a no-op")
    bound[alias].append((start, end, patch.replacement, patch))


def _check_patch_link(patch: Patch, alias: str, low: int, high: int, finding: Finding) -> None:
    if (
        alias != patch.paragraph_alias
        or finding.resolution != "proposed"
        or finding.basis != "visible_print"
    ):
        raise ValueError("patch requires a same-target proposed visible-print finding")


def _host_image_ready(payload: dict, targets: dict) -> bool:
    image = payload.get("image")
    if image is None or not _image_status_ready(image):
        return False
    bindings = _image_bindings(image)
    paragraphs = _paragraph_map(payload)
    if set(bindings) != set(paragraphs) or not set(targets) <= set(bindings):
        return False
    return all(_binding_covers_target(bindings[alias], row) for alias, row in targets.items())


def _paragraph_map(payload: dict) -> dict:
    return {paragraph["alias"]: paragraph for paragraph in payload["paragraphs"]}


def _image_status_ready(image: dict | None) -> bool:
    return bool(
        image
        and image["registration_status"] == "verified"
        and image["legibility_status"] == "checked"
    )


def _image_bindings(image: dict) -> dict:
    return {item["paragraph_alias"]: item for item in image["bindings"]}


def _binding_covers_target(binding: dict, row: dict) -> bool:
    raw = row["raw"]
    return (
        binding["raw_sha256"] == raw["sha256"]
        and binding["raw_start"] == 0
        and binding["raw_end"] == len(raw["text"])
    )


def _check_reading_uncertainties(reading: TargetReading, raw: str) -> None:
    for uncertainty in reading.uncertainties:
        if uncertainty.raw_quote is not None:
            unique_quote_span(raw, uncertainty.raw_quote)


def _check_finding_reading_links(parsed: Reply, targets: dict, bound: dict) -> None:
    for finding in parsed.findings:
        if finding.resolution != "proposed":
            continue
        _check_one_finding_reading(finding, targets, bound)


def _check_one_finding_reading(finding: Finding, targets: dict, bound: dict) -> None:
    alias = finding.anchor.paragraph_alias
    row = targets[alias]
    raw = _layer(row, "raw")
    start, end = _anchor_span(finding, raw)
    linked = [item for item in bound[alias] if item[3].finding_id == finding.finding_id]
    edits = tuple(
        ExactEdit(
            start=patch_start - start,
            end=patch_end - start,
            raw_quote=raw[patch_start:patch_end],
            replacement=replacement,
            rule_id="productive_reply",
        )
        for patch_start, patch_end, replacement, _patch in sorted(
            linked, key=lambda item: (item[0], item[1])
        )
    )
    reconstructed, _ = replay_with_map(raw[start:end], edits)
    if finding.proposed_reading != reconstructed:
        raise ValueError("finding proposed reading contradicts its linked raw patches")


def _readings(
    parsed: Reply, targets: dict, readings: dict, inspections: dict, checks: dict, bound: dict
) -> dict:
    mapped = {}
    for alias, reading in readings.items():
        mapped[alias] = _validate_one_reading(
            parsed, alias, targets[alias], reading, inspections, checks, bound[alias]
        )
    return mapped


def _validate_one_reading(
    parsed: Reply,
    alias: str,
    row: dict,
    reading: TargetReading,
    inspections: dict,
    checks: dict,
    patches: list,
) -> dict:
    patches.sort(key=lambda item: (item[0], item[1]))
    if any(patches[i][0] < patches[i - 1][1] for i in range(1, len(patches))):
        raise ValueError("patches overlap")
    _check_reading_uncertainties(reading, _layer(row, "raw"))
    if parsed.status in {"incomplete", "unresolved"}:
        _check_withheld(parsed, reading, patches)
        return {}
    if reading.uncertainties:
        raise ValueError("target uncertainties require an unresolved or incomplete reply")
    if not _full_check(alias, inspections, checks):
        raise ValueError("findings/no_finding requires complete inspection and full self-check")
    _check_no_unresolved(alias, parsed.findings)
    return _replayed_reading(parsed, row, reading, patches)


def _check_withheld(parsed: Reply, reading: TargetReading, patches: list) -> None:
    if (
        not parsed.reason
        or not reading.reason
        or reading.reading_status != "withheld"
        or reading.proposed_text is not None
        or patches
    ):
        raise ValueError(
            "incomplete/unresolved reply must withhold readings and contain no patches"
        )


def _check_no_unresolved(alias: str, findings: list[Finding]) -> None:
    if any(
        item.resolution == "unresolved" and item.anchor.paragraph_alias == alias
        for item in findings
    ):
        raise ValueError("unresolved concern prevents full reading")


def _replayed_reading(parsed: Reply, row: dict, reading: TargetReading, patches: list) -> dict:
    raw = _layer(row, "raw")
    edits = tuple(
        ExactEdit(
            start=a, end=b, raw_quote=raw[a:b], replacement=replacement, rule_id="productive_reply"
        )
        for a, b, replacement, _ in patches
    )
    replay, support_map = replay_with_map(raw, edits)
    if replay != reading.proposed_text:
        raise ValueError("full reading does not exactly replay from raw patches")
    _check_reading_status(reading, patches)
    _check_no_finding(parsed, reading, replay, raw)
    comparison = compare_brackets(
        BracketSource(source_id=row["source_id"], raw_text=raw, raw_sha256=row["raw"]["sha256"]),
        replay,
    )
    return {
        "text": replay,
        "sha256": hashlib.sha256(replay.encode()).hexdigest(),
        "raw_sha256": row["raw"]["sha256"],
        "patches": [
            {"start": a, "end": b, "replacement": replacement, "finding_id": patch.finding_id}
            for a, b, replacement, patch in patches
        ],
        "support_map": [segment.model_dump(mode="json") for segment in support_map],
        "bracket_concern": comparison.model_dump(mode="json"),
    }


def _check_reading_status(reading: TargetReading, patches: list) -> None:
    expected = "proposed" if patches else "unchanged"
    if reading.reading_status != expected:
        raise ValueError("reading status disagrees with patches")


def _check_no_finding(parsed: Reply, reading: TargetReading, replay: str, raw: str) -> None:
    if parsed.status == "no_finding" and (
        parsed.findings or parsed.patches or replay != raw or reading.uncertainties
    ):
        raise ValueError("no_finding requires exact unchanged raw and no concerns")


def _validate_status(parsed: Reply) -> None:
    _validate_finding_status(parsed)
    _validate_no_finding_status(parsed)
    _validate_unresolved_status(parsed)


def _validate_finding_status(parsed: Reply) -> None:
    if parsed.status == "findings" and not parsed.findings:
        raise ValueError("findings status requires findings")


def _validate_no_finding_status(parsed: Reply) -> None:
    if parsed.status == "no_finding" and (parsed.findings or parsed.patches):
        raise ValueError("no_finding must have empty findings and patches")


def _validate_unresolved_status(parsed: Reply) -> None:
    if parsed.status in {"incomplete", "unresolved"} and not parsed.reason:
        raise ValueError("incomplete/unresolved requires a reason")


def validate_reply(output_text: str, host_payload: dict) -> dict:
    """Validate provider text against host-frozen targets and return mapped proposals."""
    try:
        parsed = Reply.model_validate_json(output_text)
    except Exception as exc:
        raise ValueError(f"invalid productive OCR reply: {exc}") from exc
    return _validated_reply(output_text, parsed, host_payload)


def _validated_reply(output_text: str, parsed: Reply, host_payload: dict) -> dict:
    payload = host_payload["payload"]
    role = payload["role"]
    targets = _targets(host_payload, role)
    if parsed.unit_id != payload["unit_id"] or parsed.role != role:
        raise ValueError("reply unit or role does not match host payload")
    inspections, checks, readings = _reply_structure(parsed, targets, role)
    mapped_findings, supports = _bind_findings(parsed, targets)
    bound = _bind_patches(parsed, targets, supports)
    _check_finding_reading_links(parsed, targets, bound)
    _check_audit_completeness(parsed, targets, inspections, checks)
    _require_productive_image(parsed, payload, targets)
    mapped_readings = _readings(parsed, targets, readings, inspections, checks, bound)
    _validate_status(parsed)
    return _reply_result(output_text, parsed, mapped_findings, mapped_readings)


def _check_audit_completeness(
    parsed: Reply, targets: dict, inspections: dict, checks: dict
) -> None:
    if parsed.role != "audit_saved_proposal":
        return
    if parsed.status not in {"findings", "no_finding"}:
        return
    _check_audit_targets(targets, inspections, checks)


def _check_audit_targets(targets, inspections, checks) -> None:
    for alias in targets:
        if not _full_check(alias, inspections, checks):
            raise ValueError("complete audit requires full inspection and self-check")


def _require_productive_image(parsed: Reply, payload: dict, targets: dict) -> None:
    if parsed.status in {"findings", "no_finding"} and not _host_image_ready(payload, targets):
        raise ValueError("complete reply requires host-verified target image bindings")


def _reply_result(output_text: str, parsed: Reply, findings: list, readings: dict) -> dict:
    return {
        "original_reply_text": output_text,
        "model_proposal": parsed.model_dump(mode="json"),
        "source_mapped_findings": findings,
        "proposed_readings": readings,
        "historical_status": "proposal_only_not_human_reviewed",
        "quality_status": "not_established_by_structural_validation",
    }
