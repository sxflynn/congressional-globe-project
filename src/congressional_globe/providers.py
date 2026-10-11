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
    finish_reason: str | None = None
    output_status: str | None = None


class ProviderOutputError(ValueError):
    """A provider returned output that could not safely be accepted."""

    def __init__(
        self,
        message: str,
        *,
        raw_response: str,
        usage: dict[str, int],
        finish_reason: str | None,
        output_status: str | None,
    ) -> None:
        super().__init__(message)
        self.raw_response = raw_response
        self.usage = usage
        self.finish_reason = finish_reason
        self.output_status = output_status


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
        choice = response.choices[0]
        content = choice.message.content or ""
        finish_reason = choice.finish_reason
        usage = response.usage
        tokens = (
            {}
            if usage is None
            else {"input_tokens": usage.prompt_tokens, "output_tokens": usage.completion_tokens}
        )
        return _validated_result(content, tokens, finish_reason, None)


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
        details = getattr(response, "incomplete_details", None)
        incomplete_reason = getattr(details, "reason", None)
        status = response.status
        output_text = response.output_text or ""
        finish_reason = incomplete_reason
        return _validated_result(output_text, tokens, finish_reason, status)


def _validated_result(
    raw_response: str,
    usage: dict[str, int],
    finish_reason: str | None,
    output_status: str | None,
) -> ProviderResult:
    _reject_truncated(raw_response, usage, finish_reason, output_status)
    _reject_incomplete_status(raw_response, usage, finish_reason, output_status)
    cleanup = _parse_cleanup(raw_response, usage, finish_reason, output_status)
    return ProviderResult(cleanup, raw_response, usage, finish_reason, output_status)


def _reject_truncated(
    raw_response: str,
    usage: dict[str, int],
    finish_reason: str | None,
    output_status: str | None,
) -> None:
    if finish_reason == "length" or output_status == "incomplete":
        raise ProviderOutputError(
            "Provider output was truncated "
            f"(finish_reason={finish_reason!r}, status={output_status!r})",
            raw_response=raw_response,
            usage=usage,
            finish_reason=finish_reason,
            output_status=output_status,
        )


def _reject_incomplete_status(
    raw_response: str,
    usage: dict[str, int],
    finish_reason: str | None,
    output_status: str | None,
) -> None:
    if output_status is not None and output_status != "completed":
        raise ProviderOutputError(
            f"Provider response did not complete (status={output_status!r})",
            raw_response=raw_response,
            usage=usage,
            finish_reason=finish_reason,
            output_status=output_status,
        )


def _parse_cleanup(
    raw_response: str,
    usage: dict[str, int],
    finish_reason: str | None,
    output_status: str | None,
) -> CleanupResult:
    if not raw_response.strip():
        raise ProviderOutputError(
            "Provider returned empty content "
            f"(finish_reason={finish_reason!r}, status={output_status!r})",
            raw_response=raw_response,
            usage=usage,
            finish_reason=finish_reason,
            output_status=output_status,
        )
    try:
        cleanup = CleanupResult.model_validate_json(raw_response)
    except ValueError as error:
        raise ProviderOutputError(
            f"Provider returned invalid cleanup JSON: {error}",
            raw_response=raw_response,
            usage=usage,
            finish_reason=finish_reason,
            output_status=output_status,
        ) from error
    return cleanup


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
