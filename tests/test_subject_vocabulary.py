"""Tests for the packaged draft subject vocabulary."""

import json
from importlib.resources import files

import pytest
from pydantic import ValidationError

from congressional_globe.subject_vocabulary import load_draft_vocabulary
from congressional_globe.subjects import SubjectVocabulary


def test_packaged_vocabulary_has_expected_draft_identity_and_ids() -> None:
    vocabulary = load_draft_vocabulary()

    assert vocabulary.version == "v2-subjects-draft-1"
    assert vocabulary.schema_version == "1"
    assert vocabulary.status == "draft"
    assert [item.subject_id for item in vocabulary.definitions] == [
        "subj.reconstruction",
        "subj.citizenship",
        "subj.civil_rights",
        "subj.voting_rights",
        "subj.constitutional_change",
        "subj.taxation",
        "subj.military_affairs",
        "subj.congressional_procedure",
        "subj.infrastructure",
        "subj.public_compensation",
    ]
    assert len(vocabulary.digest) == 64


def test_candidate_cues_have_scope_boundaries_and_no_generic_amendment_alias() -> None:
    vocabulary = load_draft_vocabulary()
    by_id = {item.subject_id: item for item in vocabulary.definitions}

    assert "elective franchise" in by_id["subj.voting_rights"].aliases
    assert "right of suffrage" in by_id["subj.voting_rights"].aliases
    constitutional = by_id["subj.constitutional_change"]
    assert "amendment" not in constitutional.aliases
    assert any("routine bill amendment" in item for item in constitutional.exclusion)
    assert all(item.inclusion and item.exclusion for item in vocabulary.definitions)


def test_schema_rejects_invalid_resource_boundaries() -> None:
    raw = json.loads(
        files("congressional_globe")
        .joinpath("data/subject_vocabulary_draft.json")
        .read_text(encoding="utf-8")
    )
    raw["status"] = "approved"

    with pytest.raises(ValidationError):
        SubjectVocabulary.model_validate(raw)
