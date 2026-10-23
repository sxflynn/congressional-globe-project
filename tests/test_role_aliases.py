import hashlib

import pytest

from congressional_globe.role_aliases import prepare_aliases, validate_alias_result


def frozen_row() -> dict:
    raw_text = "Mr. Adams spoke."
    return {
        "schema_version": "span-selection-input-v1",
        "offset_convention": "unicode_codepoints_half_open",
        "window_id": "w1",
        "source_anchor": {"item_identifier": "source-long-id"},
        "raw_text": raw_text,
        "raw_sha256": hashlib.sha256(raw_text.encode()).hexdigest(),
        "spans": [
            {
                "span_id": "long-paragraph-id",
                "kind": "paragraph",
                "text": raw_text,
                "start": 0,
                "end": len(raw_text),
                "source_paragraph_id": "p-long",
                "cue_origin": None,
            },
            {
                "span_id": "long-cue-id",
                "kind": "speaker_cue",
                "text": "Mr. Adams",
                "start": 0,
                "end": 9,
                "source_paragraph_id": "p-long",
                "cue_origin": "speakers",
            },
            {
                "span_id": "long-date-id",
                "kind": "date_cue",
                "text": "spoke",
                "start": 10,
                "end": 15,
                "source_paragraph_id": "p-long",
                "cue_origin": "dates",
            },
        ],
        "controlled_topic_ids": ["topic"],
        "controlled_role_ids": ["floor_speaker", "other"],
        "statuses": ["proposed", "unknown"],
    }


def test_prepare_uses_short_ids_and_keeps_full_host_mapping() -> None:
    prepared = prepare_aliases(frozen_row())
    assert prepared["input"]["spans"][0]["id"] == "P1"
    assert prepared["input"]["spans"][1]["id"] == "C1"
    assert "source_anchor" not in prepared["input"]
    assert prepared["alias_map"]["C1"]["span"]["span_id"] == "long-cue-id"
    assert prepared["alias_map"]["C1"]["source_anchor"] == frozen_row()["source_anchor"]


@pytest.mark.parametrize("mutation", ["hash", "offset", "duplicate"])
def test_rejects_malformed_frozen_rows(mutation: str) -> None:
    row = frozen_row()
    if mutation == "hash":
        row["raw_sha256"] = "0" * 64
    elif mutation == "offset":
        row["spans"][0]["end"] -= 1
    else:
        row["spans"][1]["span_id"] = row["spans"][0]["span_id"]
    with pytest.raises(ValueError):
        prepare_aliases(row)


def test_role_output_requires_cue_evidence_and_unknown_stays_anonymous() -> None:
    packet = prepare_aliases(frozen_row())["input"]
    result = {
        "speaker_roles": [
            {
                "candidate_id": "C1",
                "evidence_ids": ["C1", "P1"],
                "target_ids": ["P1"],
                "role": "floor_speaker",
                "status": "proposed",
                "basis": "Explicit speaker cue.",
            }
        ]
    }
    assert validate_alias_result(result, packet) == result
    unknown = {
        "speaker_roles": [
            {
                "candidate_id": None,
                "evidence_ids": [],
                "target_ids": ["P1"],
                "role": "other",
                "status": "unknown",
                "basis": "No attributable speaker cue.",
            }
        ]
    }
    assert validate_alias_result(unknown, packet) == unknown
    bad = {"speaker_roles": [{**result["speaker_roles"][0], "candidate_id": "P1"}]}
    with pytest.raises(ValueError, match="speaker/person cue"):
        validate_alias_result(bad, packet)
    bad_date_candidate = {"speaker_roles": [{**result["speaker_roles"][0], "candidate_id": "C2"}]}
    with pytest.raises(ValueError, match="speaker/person cue"):
        validate_alias_result(bad_date_candidate, packet)
    bad_evidence = {"speaker_roles": [{**result["speaker_roles"][0], "evidence_ids": ["invented"]}]}
    with pytest.raises(ValueError, match="evidence_ids"):
        validate_alias_result(bad_evidence, packet)
    bad_target = {"speaker_roles": [{**result["speaker_roles"][0], "target_ids": ["invented"]}]}
    with pytest.raises(ValueError, match="target_ids"):
        validate_alias_result(bad_target, packet)
    bad_proposed = {"speaker_roles": [{**result["speaker_roles"][0], "candidate_id": None}]}
    with pytest.raises(ValueError, match="requires a candidate"):
        validate_alias_result(bad_proposed, packet)
    bad_unknown = {"speaker_roles": [{**unknown["speaker_roles"][0], "candidate_id": "C1"}]}
    with pytest.raises(ValueError, match="unknown role"):
        validate_alias_result(bad_unknown, packet)
