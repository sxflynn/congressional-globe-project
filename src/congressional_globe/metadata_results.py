"""Existing metadata contracts and source-linked, proposal-only result exports."""

from __future__ import annotations

from copy import deepcopy
from typing import Literal

from congressional_globe.role_aliases import (
    ROLE_RESULT_SCHEMA,
    FrozenInput,
    prepare_aliases,
    validate_alias_result,
)
from congressional_globe.role_v2 import role_result_schema, validate_role_result_v2
from congressional_globe.scoped_dates import DatePacket, date_result_schema, source_mapped_dates

MetadataContract = Literal["role-v1", "role-v2", "scoped-date-v1"]


def metadata_schema(contract: MetadataContract) -> dict:
    schemas = {
        "role-v1": ROLE_RESULT_SCHEMA,
        "role-v2": role_result_schema(),
        "scoped-date-v1": date_result_schema(),
    }
    return deepcopy(schemas[contract])


def verify_metadata_packet(packet: dict, frozen: dict, contract: MetadataContract) -> None:
    if contract == "scoped-date-v1":
        expected = DatePacket.model_validate(frozen).model_dump()
    else:
        expected = prepare_aliases(frozen)["input"]
    if expected != packet:
        raise ValueError("Prepared packet does not match validated frozen source")


def packet_text(packet: dict, contract: MetadataContract) -> str:
    if contract == "scoped-date-v1":
        return "\n\n".join(p.raw_text for p in DatePacket.model_validate(packet).paragraphs)
    return packet["raw_text"]


def validated_metadata(result: dict, packet: dict, contract: MetadataContract) -> dict:
    if contract == "scoped-date-v1":
        mapped = source_mapped_dates(result, packet)
        return {"date_proposals": {"dates": mapped["dates"]}}
    validators = {"role-v1": validate_alias_result, "role-v2": validate_role_result_v2}
    return {"role_proposals": validators[contract](result, packet)}


def mapped_metadata(result: dict, packet: dict, frozen: dict, contract: MetadataContract) -> dict:
    verify_metadata_packet(packet, frozen, contract)
    if contract == "scoped-date-v1":
        return source_mapped_dates(result, packet)
    return _mapped_roles(result, packet, frozen, contract)


def _unannotated(validated: dict, packet: dict) -> list[str]:
    assigned = {alias for item in validated["speaker_roles"] for alias in item["target_ids"]}
    return [alias for alias in _paragraph_aliases(packet) if alias not in assigned]


def _paragraph_aliases(packet: dict) -> list[str]:
    return [span["id"] for span in packet["spans"] if span["kind"] == "paragraph"]


def _mapped_roles(result: dict, packet: dict, frozen: dict, contract: MetadataContract) -> dict:
    validated = validated_metadata(result, packet, contract)["role_proposals"]
    source = FrozenInput.model_validate(frozen)
    aliases = prepare_aliases(frozen)["alias_map"]
    return {
        "schema_version": f"source-mapped-{contract}",
        "window_id": source.window_id,
        "offset_convention": "unicode_codepoints_half_open_within_raw_window",
        "source_anchor": source.source_anchor,
        "raw_text": source.raw_text,
        "raw_sha256": source.raw_sha256,
        "spans": [{"alias": alias, **record["span"]} for alias, record in aliases.items()],
        **validated,
        "unannotated_target_ids": _unannotated(validated, packet),
        "historical_status": "proposal_only_not_human_reviewed",
    }
