"""Focused contract tests for the role-only provider adapter."""

from types import SimpleNamespace as NS

import pytest

from congressional_globe import role_provider
from congressional_globe.role_aliases import ROLE_RESULT_SCHEMA


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
