"""Bounded offline-only codec for the T79 diagnostic column proposal.

Production request compilation does not use this module. A separately bounded D1
measurement imports it for lossless wire comparison. Decoding requires an
independently held original provider and its canonical SHA-256, not a self-hash
supplied by the compact input. Shape/replay validity is not source authenticity.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from congressional_globe.productive_ocr_host import (
    Box,
    Diagnostics,
    Edit,
    SavedProposal,
    Signal,
    StrictModel,
    canonical_json,
    sha256_bytes,
)

COMPACT_CONTRACT = "ocr-productive-repair-input-v3-column-proposal"
MAX_SERIALIZED_BYTES = 2 * 1024 * 1024
MAX_JSON_DEPTH = 32
SIGNAL_COLUMNS = tuple(sorted(Signal.model_fields))
Alias = Annotated[str, Field(pattern=r"^P([1-9]|[12][0-9]|3[0-2])$")]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Row = Annotated[list[Any], Field(min_length=len(SIGNAL_COLUMNS), max_length=len(SIGNAL_COLUMNS))]


class ProviderParagraph(StrictModel):
    paragraph_alias: Alias
    role: Literal["target", "context"]
    raw_text: str = Field(max_length=6000)
    static_text: str = Field(max_length=6000)
    static_edits: list[Edit] = Field(max_length=128)


class ProviderRegion(StrictModel):
    paragraph_alias: Alias
    crop_region: Box


class ProviderFields(StrictModel):
    reply_contract: Literal["ocr-productive-repair-reply-v2"]
    unit_id: str = Field(min_length=1)
    role: Literal["productive_repair_and_self_check", "audit_saved_proposal"]
    image_alias: Literal["I1"]
    target_regions: list[ProviderRegion] = Field(min_length=1, max_length=32)
    context_regions: list[ProviderRegion] = Field(max_length=32)
    paragraphs: list[ProviderParagraph] = Field(min_length=1, max_length=32)
    saved_proposal: SavedProposal | None

    @model_validator(mode="after")
    def scope_text_limits(self) -> ProviderFields:
        for role, limit in (("target", 6000), ("context", 2000)):
            paragraphs = [row for row in self.paragraphs if row.role == role]
            _scope_limit(paragraphs, limit)
        return self


def _scope_limit(paragraphs: list[ProviderParagraph], limit: int) -> None:
    raw = sum(len(row.raw_text) for row in paragraphs)
    static = sum(len(row.static_text) for row in paragraphs)
    if raw > limit or static > limit:
        raise ValueError("aggregate source text exceeds the existing role scope limit")


class ProviderV2(ProviderFields):
    contract: Literal["ocr-productive-repair-input-v2"]
    diagnostics: Diagnostics


class SignalTable(StrictModel):
    columns: list[str] = Field(max_length=len(SIGNAL_COLUMNS))
    route_reasons: list[Annotated[str, Field(min_length=1)]] = Field(max_length=128)
    rows: list[Row] = Field(max_length=128)

    @model_validator(mode="after")
    def valid_encoding(self) -> SignalTable:
        expected = list(SIGNAL_COLUMNS) if self.rows else []
        if self.columns != expected:
            raise ValueError("signal columns must exactly match the canonical ordered fields")
        if self.route_reasons != sorted(set(self.route_reasons)):
            raise ValueError("route reasons must be sorted and unique")
        _decode_signals(self)
        return self


class CompactDiagnostics(StrictModel):
    status: Literal["not_run", "frozen"]
    detector_sha256: Hash | None
    configuration_sha256: Hash | None
    negative_targets: list[Alias] = Field(max_length=32)
    signal_table: SignalTable


class CompactProvider(ProviderFields):
    contract: Literal["ocr-productive-repair-input-v3-column-proposal"]
    diagnostics: CompactDiagnostics


def _reason_index(value: Any, reasons: list[str]) -> int:
    if type(value) is not int or not 0 <= value < len(reasons):
        raise ValueError("route reason index must be a strict integer within the reason table")
    return value


def _decode_row(columns: list[str], row: list, reasons: list[str]) -> tuple[dict, int]:
    values = dict(zip(columns, row, strict=True))
    index = _reason_index(values["route_reason"], reasons)
    values["route_reason"] = reasons[index]
    signal = Signal.model_validate(values)
    return signal.model_dump(mode="json"), index


def _decode_signals(table: SignalTable) -> list[dict]:
    decoded, used = [], set()
    for row in table.rows:
        signal, index = _decode_row(table.columns, row, table.route_reasons)
        decoded.append(signal)
        used.add(index)
    if used != set(range(len(table.route_reasons))):
        raise ValueError("every route reason must be used by a signal row")
    return decoded


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate JSON object keys are forbidden")
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _children(value: Any):
    if isinstance(value, dict):
        return value.values()
    if isinstance(value, list):
        return value
    return []


def _bounded_tree(value: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ValueError("JSON nesting exceeds the offline codec depth limit")
    for child in _children(value):
        _bounded_tree(child, depth + 1)


def _check_size(text: str) -> None:
    if (
        not isinstance(text, str)
        or len(text) > MAX_SERIALIZED_BYTES
        or len(text.encode("utf-8")) > MAX_SERIALIZED_BYTES
    ):
        raise ValueError("serialized input exceeds the offline codec byte limit or is not text")


def _parse(text: str) -> Any:
    _check_size(text)
    try:
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        _bounded_tree(value)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid or excessively nested codec JSON") from exc
    return value


def _serialize(value: dict) -> str:
    result = canonical_json(value).decode("utf-8")
    _check_size(result)
    return result


def _reference(original_json: str, expected_provider_sha256: str) -> tuple[dict, str]:
    original = ProviderV2.model_validate(_parse(original_json)).model_dump(mode="json")
    canonical = _serialize(original)
    if sha256_bytes(canonical.encode()) != expected_provider_sha256:
        raise ValueError("original provider differs from its independently held canonical SHA-256")
    return original, canonical


def _table(signals: list[dict]) -> dict:
    columns = list(SIGNAL_COLUMNS) if signals else []
    reasons = sorted({signal["route_reason"] for signal in signals})
    indices = {reason: index for index, reason in enumerate(reasons)}
    rows = [_encode_row(signal, columns, indices) for signal in signals]
    return {"columns": columns, "route_reasons": reasons, "rows": rows}


def _encode_row(signal: dict, columns: list[str], indices: dict[str, int]) -> list:
    return [indices[signal[key]] if key == "route_reason" else signal[key] for key in columns]


def encode_provider(original_json: str, expected_provider_sha256: str) -> str:
    """Return canonical proposal bytes from a separately pinned original provider."""
    original, _canonical = _reference(original_json, expected_provider_sha256)
    signals = original["diagnostics"].pop("signals")
    original["diagnostics"]["signal_table"] = _table(signals)
    original["contract"] = COMPACT_CONTRACT
    compact = CompactProvider.model_validate(original)
    return _serialize(compact.model_dump(mode="json"))


def decode_provider(compact_json: str, original_json: str, expected_provider_sha256: str) -> str:
    """Restore only the exact independently bound provider, rejecting coherent tampering.

    The caller must obtain the original/hash from trusted evidence separately;
    accepting both from the compact input would not authenticate anything.
    """
    _original, expected = _reference(original_json, expected_provider_sha256)
    compact = CompactProvider.model_validate(_parse(compact_json))
    restored = compact.model_dump(mode="json")
    table = restored["diagnostics"].pop("signal_table")
    restored["diagnostics"]["signals"] = _decode_signals(SignalTable.model_validate(table))
    restored["contract"] = "ocr-productive-repair-input-v2"
    decoded = _serialize(ProviderV2.model_validate(restored).model_dump(mode="json"))
    if decoded != expected:
        raise ValueError("decoded provider differs from the independently bound original")
    return decoded
