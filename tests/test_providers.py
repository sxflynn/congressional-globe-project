from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace

import pytest

from congressional_globe import providers


def test_ollama_requests_from_separate_providers_are_serialized(monkeypatch) -> None:
    state = {"active": 0, "maximum": 0}
    guard = threading.Lock()

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **_kwargs):
            with guard:
                state["active"] += 1
                state["maximum"] = max(state["maximum"], state["active"])
            time.sleep(0.03)
            with guard:
                state["active"] -= 1
            message = SimpleNamespace(
                content=json.dumps(
                    {"edits": [], "needs_image_review": False, "review_reason": None}
                )
            )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=message, finish_reason="stop")], usage=None
            )

    monkeypatch.setattr(providers, "OpenAI", FakeClient)
    first = providers.OllamaProvider("model-a", "http://local")
    second = providers.OllamaProvider("model-b", "http://local")
    threads = [
        threading.Thread(target=provider.clean, args=("text",)) for provider in (first, second)
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert state["maximum"] == 1


@pytest.mark.parametrize(
    ("content", "finish_reason", "error_fragment"),
    [
        ("{broken", "stop", "invalid cleanup JSON"),
        ("", "stop", "empty content"),
        ('{"edits":', "length", "truncated"),
    ],
)
def test_ollama_preserves_raw_output_and_metadata_on_rejection(
    monkeypatch, content: str, finish_reason: str, error_fragment: str
) -> None:
    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **_kwargs):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=content), finish_reason=finish_reason
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=13, completion_tokens=4),
            )

    monkeypatch.setattr(providers, "OpenAI", FakeClient)
    provider = providers.OllamaProvider("test", "http://local")

    with pytest.raises(providers.ProviderOutputError, match=error_fragment) as error:
        provider.clean("source")

    assert error.value.raw_response == content
    assert error.value.usage == {"input_tokens": 13, "output_tokens": 4}
    assert error.value.finish_reason == finish_reason


def test_ollama_success_returns_finish_metadata(monkeypatch) -> None:
    content = json.dumps({"edits": [], "needs_image_review": False, "review_reason": None})

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **_kwargs):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="stop")
                ],
                usage=SimpleNamespace(prompt_tokens=13, completion_tokens=4),
            )

    monkeypatch.setattr(providers, "OpenAI", FakeClient)
    result = providers.OllamaProvider("test", "http://local").clean("source")

    assert result.raw_response == content
    assert result.finish_reason == "stop"
    assert result.output_status is None
    assert result.usage == {"input_tokens": 13, "output_tokens": 4}


@pytest.mark.parametrize("status", ["incomplete", "failed"])
def test_responses_provider_rejects_noncompleted_status_and_keeps_metadata(
    monkeypatch, status: str
) -> None:
    content = '{"edits": []}'

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            self.responses = SimpleNamespace(create=self.create)

        def create(self, **_kwargs):
            return SimpleNamespace(
                usage=SimpleNamespace(input_tokens=17, output_tokens=2),
                incomplete_details=SimpleNamespace(reason="max_output_tokens"),
                status=status,
                output_text=content,
            )

    monkeypatch.setattr(providers, "OpenAI", FakeClient)
    provider = providers.OpenAIResponsesProvider("test")

    with pytest.raises(providers.ProviderOutputError) as error:
        provider.clean("source")

    assert error.value.raw_response == content
    assert error.value.usage == {"input_tokens": 17, "output_tokens": 2}
    assert error.value.output_status == status
    assert error.value.finish_reason == "max_output_tokens"
