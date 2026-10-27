"""Focused contract tests for the role-only provider adapter."""

import json
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest
from jsonschema import Draft202012Validator

from congressional_globe import role_provider
from congressional_globe.role_aliases import ROLE_RESULT_SCHEMA
from congressional_globe.role_v2 import role_result_schema, validate_role_result_v2


def _dump_response(**values):
    response = NS(**values)
    response.model_dump = lambda mode: {"id": response.id, "status": response.status}
    return response


def test_openai_preserves_raw_incomplete_response_and_unknown_usage(monkeypatch):
    recorded = {}
    response = _dump_response(
        id="req-1",
        status="incomplete",
        output_text='{"partial":',
        output=[],
        usage=None,
        incomplete_details=NS(reason="max_output_tokens"),
    )

    class Client:
        def __init__(self, **kwargs):
            recorded["client"] = kwargs
            self.responses = NS(create=self.create)

        def create(self, **kwargs):
            recorded["request"] = kwargs
            return response

    monkeypatch.setattr(role_provider, "OpenAI", Client)
    provider = role_provider.RoleProvider("openai", "gpt-5.4-mini", max_output_tokens=17)
    result = provider.call(
        {
            "spans": [{"id": "P1", "kind": "paragraph"}, {"id": "C1", "kind": "speaker_cue"}],
            "controlled_role_ids": ["floor_speaker"],
            "statuses": ["proposed", "unknown"],
        },
        "classify",
        ROLE_RESULT_SCHEMA,
    )
    assert recorded["client"]["max_retries"] == 0
    assert recorded["request"]["max_output_tokens"] == 17
    sent_fields = recorded["request"]["text"]["format"]["schema"]["properties"]["speaker_roles"][
        "items"
    ]["properties"]
    assert sent_fields["candidate_id"]["enum"] == ["C1", None]
    assert result["raw_response"] == '{"id": "req-1", "status": "incomplete"}'
    assert result["output_text"] == '{"partial":'
    assert result["status"] == "incomplete"
    assert result["finish_reason"] == "max_output_tokens"
    assert result["usage"] == {
        "input_tokens": None,
        "cached_input_tokens": None,
        "output_tokens": None,
    }


def test_openai_refusal_is_exposed_without_parsing(monkeypatch):
    options = {}
    refusal = NS(type="refusal")
    message = NS(type="message", content=[refusal])
    response = _dump_response(
        id="req-2",
        status="completed",
        output_text="I cannot help",
        output=[message],
        usage=NS(input_tokens=5, output_tokens=2, input_tokens_details=NS(cached_tokens=1)),
        incomplete_details=None,
    )

    class Client:
        def __init__(self, **kwargs):
            options.update(kwargs)
            self.responses = NS(create=lambda **args: response)

    monkeypatch.setattr(role_provider, "OpenAI", Client)
    packet = {
        "spans": [{"id": "P1", "kind": "paragraph"}],
        "controlled_role_ids": ["floor_speaker"],
        "statuses": ["unknown"],
    }
    result = role_provider.RoleProvider("openai", "model").call(packet, "p", ROLE_RESULT_SCHEMA)
    assert options["base_url"] == "https://api.openai.com/v1"
    assert result["status"] == "refusal"
    assert result["usage"] == {"input_tokens": 5, "cached_input_tokens": 1, "output_tokens": 2}


def test_ollama_uses_lock_contract_and_normalizes_chat_usage(monkeypatch):
    call = {}
    response = NS(
        id="ollama-1",
        choices=[NS(message=NS(content='{"roles": []}', refusal=None), finish_reason="stop")],
        usage=NS(prompt_tokens=9, completion_tokens=4, prompt_tokens_details=NS(cached_tokens=3)),
    )
    response.model_dump = lambda mode: {"id": response.id, "choices": []}

    class Client:
        def __init__(self, **kwargs):
            call["client"] = kwargs
            self.chat = NS(completions=NS(create=self.create))

        def create(self, **kwargs):
            call["request"] = kwargs
            return response

    class Lock:
        def __enter__(self):
            call["locked"] = True

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(role_provider, "OpenAI", Client)
    monkeypatch.setattr(role_provider, "_ollama_request_lock", Lock)
    result = role_provider.RoleProvider("ollama", "qwen", "http://localhost:11434").call(
        {
            "spans": [{"id": "P1", "kind": "paragraph"}],
            "controlled_role_ids": ["floor_speaker"],
            "statuses": ["unknown"],
        },
        "prompt",
        ROLE_RESULT_SCHEMA,
    )
    assert call["locked"] is True
    assert call["client"]["max_retries"] == 0
    assert call["request"]["temperature"] == 0
    assert result["usage"] == {"input_tokens": 9, "cached_input_tokens": 3, "output_tokens": 4}
    assert result["provider_request_id"] == "ollama-1"


def test_invalid_provider_configuration_is_rejected():
    with pytest.raises(ValueError):
        role_provider.RoleProvider("other", "model")


def test_schema_specialization_limits_aliases_and_preserves_base_schema():
    packet = {
        "spans": [
            {"id": "P1", "kind": "paragraph"},
            {"id": "C1", "kind": "speaker_cue"},
            {"id": "C2", "kind": "person_cue"},
            {"id": "X1", "kind": "date_cue"},
        ],
        "controlled_role_ids": ["floor_speaker", "petition_presenter"],
        "statuses": ["proposed", "unknown"],
    }
    specialized = role_provider.specialize_schema(ROLE_RESULT_SCHEMA, packet)
    fields = specialized["properties"]["speaker_roles"]["items"]["properties"]
    assert fields["candidate_id"]["enum"] == ["C1", "C2", None]
    assert fields["target_ids"]["items"]["enum"] == ["P1"]
    assert fields["evidence_ids"]["items"]["enum"] == ["P1", "C1", "C2", "X1"]
    assert fields["role"]["enum"] == packet["controlled_role_ids"]
    assert fields["status"]["enum"] == packet["statuses"]
    assert (
        "enum"
        not in ROLE_RESULT_SCHEMA["properties"]["speaker_roles"]["items"]["properties"][
            "candidate_id"
        ]
    )


def test_schema_specialization_allows_only_null_when_no_person_cues():
    packet = {
        "spans": [{"id": "P1", "kind": "paragraph"}],
        "controlled_role_ids": ["unknown"],
        "statuses": ["unknown"],
    }
    fields = role_provider.specialize_schema(ROLE_RESULT_SCHEMA, packet)["properties"][
        "speaker_roles"
    ]["items"]["properties"]
    assert fields["candidate_id"]["enum"] == [None]
    assert fields["target_ids"]["items"]["enum"] == ["P1"]


def test_ollama_length_finish_reason_is_incomplete(monkeypatch):
    response = NS(
        id="ollama-truncated",
        choices=[NS(message=NS(content='{"partial":', refusal=None), finish_reason="length")],
        usage=None,
    )
    response.model_dump = lambda mode: {"id": response.id}

    class Client:
        def __init__(self, **kwargs):
            self.chat = NS(completions=NS(create=lambda **args: response))

    monkeypatch.setattr(role_provider, "OpenAI", Client)
    monkeypatch.setattr(role_provider, "_ollama_request_lock", lambda: _NullLock())
    packet = {
        "spans": [{"id": "P1", "kind": "paragraph"}],
        "controlled_role_ids": ["floor_speaker"],
        "statuses": ["unknown"],
    }
    result = role_provider.RoleProvider("ollama", "qwen", "http://localhost").call(
        packet, "p", ROLE_RESULT_SCHEMA
    )
    assert result["status"] == "incomplete"
    assert result["finish_reason"] == "length"
    assert result["output_text"] == '{"partial":'


class _NullLock:
    def __enter__(self):
        return None

    def __exit__(self, *args):
        return False


def _v2_packet() -> dict:
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


def _v2_result(status: str) -> dict:
    row = {
        "candidate_id": None,
        "evidence_ids": ["P1"],
        "target_ids": ["P1"],
        "role": "floor_speaker",
        "status": status,
        "basis": "Synthetic bounded example.",
    }
    if status == "proposed":
        row.update(candidate_id="C1", evidence_ids=["C1"])
    elif status == "mixed":
        row.update(candidate_id="C1", evidence_ids=["P1", "C1"])
    elif status == "needs_review":
        row.update(evidence_ids=[])
    return {"speaker_roles": [row]}


def _v2_with(status: str, **overrides) -> dict:
    return {"speaker_roles": [{**_v2_result(status)["speaker_roles"][0], **overrides}]}


def _v2_branch_fields(schema: dict) -> dict:
    branches = schema["properties"]["speaker_roles"]["items"]["oneOf"]
    return branches[0]["allOf"][0]["properties"]


def test_role_v2_specialization_binds_every_status_branch_without_mutation():
    packet = _v2_packet()
    original = deepcopy(role_result_schema())
    schema = role_provider.specialize_schema(role_result_schema(), packet)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    for status in packet["statuses"]:
        result = _v2_result(status)
        assert validator.is_valid(result), list(validator.iter_errors(result))
        assert validate_role_result_v2(result, packet)["speaker_roles"][0]["status"] == status
    branches = schema["properties"]["speaker_roles"]["items"]["oneOf"]
    assert len(branches) == 4
    for branch in branches:
        fields = branch["allOf"][0]["properties"]
        assert fields["candidate_id"]["enum"] == ["C1", None]
        assert fields["target_ids"]["items"]["enum"] == ["P1", "P2"]
        assert fields["evidence_ids"]["items"]["enum"] == ["P1", "P2", "C1"]
        assert fields["role"]["enum"] == packet["controlled_role_ids"]
        assert fields["status"]["enum"] == packet["statuses"]
    assert original == role_result_schema()


def test_role_v2_specialization_supports_serialized_schema_branches():
    frozen = json.loads(json.dumps(role_result_schema()))
    schema = role_provider.specialize_schema(frozen, _v2_packet())
    Draft202012Validator.check_schema(schema)
    for branch in schema["properties"]["speaker_roles"]["items"]["oneOf"]:
        assert branch["allOf"][0]["properties"]["target_ids"]["items"]["enum"] == ["P1", "P2"]


def test_role_v2_specialization_rejects_unbound_wrong_kind_and_duplicate_aliases():
    packet = _v2_packet()
    validator = Draft202012Validator(role_provider.specialize_schema(role_result_schema(), packet))
    cases = [
        (_v2_with("proposed", candidate_id="C9"), False, "supplied speaker/person cue"),
        (_v2_with("mixed", target_ids=["P9"]), False, "wrong kind or an unknown alias"),
        (_v2_with("mixed", evidence_ids=["C9"]), False, "wrong kind or an unknown alias"),
        (_v2_with("unknown", candidate_id="C1"), False, "cannot name"),
        (_v2_with("unknown", evidence_ids=["C1"]), False, "wrong kind or an unknown alias"),
        (_v2_with("mixed", target_ids=["P1", "P1"]), True, "duplicate aliases"),
    ]
    for result, schema_valid, message in cases:
        assert validator.is_valid(result) is schema_valid
        with pytest.raises(ValueError, match=message):
            validate_role_result_v2(result, packet)


def test_role_v2_openai_request_sends_specialized_schema_and_validates(monkeypatch):
    captured = {}
    packet = _v2_packet()
    output = json.dumps(_v2_result("unknown"))
    response = _dump_response(
        id="v2-openai",
        status="completed",
        output_text=output,
        output=[],
        usage=None,
        incomplete_details=None,
    )

    class Client:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.responses = NS(create=self.create)

        def create(self, **kwargs):
            captured["request"] = kwargs
            return response

    monkeypatch.setattr(role_provider, "OpenAI", Client)
    result = role_provider.RoleProvider("openai", "model").call(
        packet, "classify", role_result_schema()
    )
    sent = captured["request"]["text"]["format"]["schema"]
    assert _v2_branch_fields(sent)["candidate_id"]["enum"] == ["C1", None]
    assert captured["request"]["text"]["format"]["strict"] is True
    assert result["status"] == "completed"
    assert result["raw_response"] == '{"id": "v2-openai", "status": "completed"}'
    assert validate_role_result_v2(json.loads(result["output_text"]), packet)


def test_role_v2_ollama_request_sends_specialized_schema_and_validates(monkeypatch):
    captured = {}
    packet = _v2_packet()
    output = json.dumps(_v2_result("unknown"))
    response = NS(
        id="v2-ollama",
        choices=[NS(message=NS(content=output, refusal=None), finish_reason="stop")],
        usage=None,
    )
    response.model_dump = lambda mode: {"id": response.id, "choices": []}

    class Client:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.chat = NS(completions=NS(create=self.create))

        def create(self, **kwargs):
            captured["request"] = kwargs
            return response

    monkeypatch.setattr(role_provider, "OpenAI", Client)
    monkeypatch.setattr(role_provider, "_ollama_request_lock", lambda: _NullLock())
    result = role_provider.RoleProvider("ollama", "qwen", "http://localhost").call(
        packet, "classify", role_result_schema()
    )
    sent = json.loads(
        captured["request"]["messages"][0]["content"].split(
            "Output JSON matching this schema: ", 1
        )[1]
    )
    assert _v2_branch_fields(sent)["candidate_id"]["enum"] == ["C1", None]
    assert result["status"] == "completed"
    assert validate_role_result_v2(json.loads(result["output_text"]), packet)


def test_role_v2_incomplete_and_refusal_keep_raw_response_behavior(monkeypatch):
    packet = _v2_packet()
    incomplete = _dump_response(
        id="v2-incomplete",
        status="incomplete",
        output_text='{"speaker_roles": [',
        output=[],
        usage=None,
        incomplete_details=NS(reason="max_output_tokens"),
    )
    refusal = _dump_response(
        id="v2-refusal",
        status="completed",
        output_text="I cannot help",
        output=[NS(type="message", content=[NS(type="refusal")])],
        usage=None,
        incomplete_details=None,
    )

    class Client:
        def __init__(self, **kwargs):
            self.responses = NS(create=self.create)
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            return (incomplete, refusal)[self.calls - 1]

    monkeypatch.setattr(role_provider, "OpenAI", Client)
    provider = role_provider.RoleProvider("openai", "model")
    first = provider.call(packet, "classify", role_result_schema())
    second = provider.call(packet, "classify", role_result_schema())
    assert first["status"] == "incomplete"
    assert first["output_text"] == '{"speaker_roles": ['
    assert first["raw_response"] == '{"id": "v2-incomplete", "status": "incomplete"}'
    assert second["status"] == "refusal"
    assert second["output_text"] == "I cannot help"
