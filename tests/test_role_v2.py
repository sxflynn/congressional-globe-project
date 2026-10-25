import pytest
from jsonschema import Draft202012Validator

from congressional_globe.role_v2 import role_result_schema, validate_role_result_v2


def packet() -> dict:
    return {
        "window_id": "w1",
        "spans": [
            {"id": "P1", "kind": "paragraph"},
            {"id": "P2", "kind": "paragraph"},
            {"id": "C1", "kind": "speaker_cue"},
        ],
        "controlled_role_ids": ["floor_speaker", "person_mentioned"],
        "statuses": ["proposed", "unknown", "mixed", "needs_review"],
    }


def record(**overrides: object) -> dict:
    row = {
        "candidate_id": None,
        "evidence_ids": ["P1"],
        "target_ids": ["P1"],
        "role": "floor_speaker",
        "status": "unknown",
        "basis": "The paragraph identifies a speaking turn but supplies no name.",
    }
    row.update(overrides)
    return {"speaker_roles": [row]}


def test_unknown_identity_can_cite_paragraph_without_naming_candidate() -> None:
    result = validate_role_result_v2(record(), packet())
    assert result["speaker_roles"][0]["candidate_id"] is None
    assert result["speaker_roles"][0]["evidence_ids"] == ["P1"]


def test_unknown_identity_rejects_named_or_invented_candidate() -> None:
    with pytest.raises(ValueError, match="cannot name"):
        validate_role_result_v2(record(candidate_id="C1"), packet())


def test_unknown_evidence_must_be_a_supplied_paragraph() -> None:
    with pytest.raises(ValueError, match="wrong kind"):
        validate_role_result_v2(record(evidence_ids=["C1"]), packet())
    with pytest.raises(ValueError, match="unknown alias"):
        validate_role_result_v2(record(evidence_ids=["P99"]), packet())


def test_proposed_requires_real_candidate_and_evidence() -> None:
    proposed = record(candidate_id="C1", evidence_ids=["C1"], status="proposed")
    assert validate_role_result_v2(proposed, packet())["speaker_roles"][0]["status"] == "proposed"
    with pytest.raises(ValueError, match="supplied speaker/person cue"):
        validate_role_result_v2(
            record(candidate_id="C9", evidence_ids=["C1"], status="proposed"), packet()
        )
    with pytest.raises(ValueError, match="requires candidate and evidence"):
        validate_role_result_v2(
            record(candidate_id=None, evidence_ids=[], status="proposed"), packet()
        )


def test_schema_and_host_agree_on_all_frozen_statuses() -> None:
    validator = Draft202012Validator(role_result_schema())
    valid = [
        record(candidate_id="C1", evidence_ids=["C1"], status="proposed"),
        record(status="unknown"),
        record(candidate_id="C1", evidence_ids=["P1", "C1"], status="mixed"),
        record(candidate_id=None, evidence_ids=[], status="needs_review"),
    ]
    for result in valid:
        assert validator.is_valid(result)
        assert validate_role_result_v2(result, packet())

    invalid = [
        (record(candidate_id=None, evidence_ids=["P1"], status="proposed"), False),
        (record(candidate_id="C1", evidence_ids=["P1"], status="unknown"), False),
        (record(candidate_id="C9", evidence_ids=["P1"], status="mixed"), True),
        (record(candidate_id="C1", evidence_ids=["C9"], status="needs_review"), True),
        (record(status="future_status"), False),
    ]
    for result, schema_valid in invalid:
        assert validator.is_valid(result) is schema_valid
        with pytest.raises(ValueError):
            validate_role_result_v2(result, packet())


def test_mixed_and_needs_review_keep_v1_permissive_shape() -> None:
    validator = Draft202012Validator(role_result_schema())
    for status in ("mixed", "needs_review"):
        result = record(candidate_id=None, evidence_ids=[], status=status)
        assert validator.is_valid(result)
        assert validate_role_result_v2(result, packet())
