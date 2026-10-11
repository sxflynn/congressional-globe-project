"""Provider adapters; the cleanup runner does not depend on vendor APIs."""

from __future__ import annotations

import fcntl
import json
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from openai import OpenAI

from congressional_globe.ai import SYSTEM_PROMPT
from congressional_globe.models import CleanupResult, strict_json_schema

LOCAL_API_KEY = "ollama"


@dataclass(frozen=True)
class ProviderResult:
    cleanup: CleanupResult
    raw_response: str
    usage: dict[str, int] = field(default_factory=dict)


class CleanupProvider(Protocol):
    def clean(self, text: str) -> ProviderResult: ...


class OllamaProvider:
    """Most compatible local path: OpenAI-style Chat Completions, one call at a time."""

    def __init__(self, model: str, base_url: str, timeout_seconds: float = 60) -> None:
        self._client = OpenAI(
            base_url=base_url, api_key=LOCAL_API_KEY, timeout=timeout_seconds, max_retries=0
        )
        self._model = model

    def clean(self, text: str) -> ProviderResult:
        with _ollama_request_lock():
            return self._clean(text)

    def _clean(self, text: str) -> ProviderResult:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _local_prompt()},
                {"role": "user", "content": text},
            ],
            temperature=0,
            max_tokens=512,
            reasoning_effort="none",
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            finish_reason = response.choices[0].finish_reason
            raise ValueError(
                f"Local provider returned empty content (finish_reason={finish_reason!r})"
            )
        usage = response.usage
        tokens = (
            {}
            if usage is None
            else {"input_tokens": usage.prompt_tokens, "output_tokens": usage.completion_tokens}
        )
        return ProviderResult(CleanupResult.model_validate_json(content), content, tokens)


@contextmanager
def _ollama_request_lock():
    lock_path = f"{tempfile.gettempdir()}/congressional-globe-ollama-request.lock"
    with open(lock_path, "a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


class OpenAIResponsesProvider:
    def __init__(self, model: str, timeout_seconds: float = 60) -> None:
        self._client = OpenAI(timeout=timeout_seconds, max_retries=0)
        self._model = model

    def clean(self, text: str) -> ProviderResult:
        response = self._client.responses.create(
            model=self._model,
            instructions=SYSTEM_PROMPT,
            input=text,
            temperature=0,
            reasoning={"effort": "none"},
            text=cast(Any, {"format": _format()}),
        )
        usage = response.usage
        tokens = (
            {}
            if usage is None
            else {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}
        )
        return ProviderResult(
            CleanupResult.model_validate_json(response.output_text), response.output_text, tokens
        )


def _local_prompt() -> str:
    return (
        f"{SYSTEM_PROMPT} Output JSON only. It must validate against this schema: "
        f"{json.dumps(strict_json_schema(CleanupResult), separators=(',', ':'))}"
    )


def _format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "name": "cleanup_result",
        "strict": True,
        "schema": strict_json_schema(CleanupResult),
    }
