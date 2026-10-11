"""Provider adapters; the cleanup runner does not depend on vendor APIs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol, cast

from openai import OpenAI

from congressional_globe.ai import SYSTEM_PROMPT
from congressional_globe.models import CleanupResult, strict_json_schema

LOCAL_API_KEY = "ollama"


@dataclass(frozen=True)
class ProviderResult:
    cleanup: CleanupResult
    raw_response: str


class CleanupProvider(Protocol):
    def clean(self, text: str) -> ProviderResult: ...


class OllamaProvider:
    """Most compatible local path: OpenAI-style Chat Completions, one call at a time."""

    def __init__(self, model: str, base_url: str) -> None:
        self._client = OpenAI(base_url=base_url, api_key=LOCAL_API_KEY)
        self._model = model

    def clean(self, text: str) -> ProviderResult:
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
        return ProviderResult(CleanupResult.model_validate_json(content), content)


class OpenAIResponsesProvider:
    def __init__(self, model: str) -> None:
        self._client = OpenAI()
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
        return ProviderResult(
            CleanupResult.model_validate_json(response.output_text), response.output_text
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
