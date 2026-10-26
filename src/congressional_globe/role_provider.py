"""Provider boundary for the bounded role-only experiment."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Literal, cast

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from congressional_globe.providers import LOCAL_API_KEY, _ollama_request_lock
from congressional_globe.scoped_dates import DatePacket


class _AdapterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["openai", "ollama"]
    model: str = Field(min_length=1)
    base_url: str | None = None
    timeout: float = Field(default=90, gt=0)
    max_output_tokens: int = Field(default=3000, gt=0)


class RoleProvider:
    """Call one explicitly selected provider and preserve its complete response."""

    def __init__(
        self,
        provider: str,
        model: str,
        base_url: str | None = None,
        timeout: float = 90,
        max_output_tokens: int = 3000,
    ) -> None:
        self._config = _AdapterConfig.model_validate(
            {
                "provider": provider,
                "model": model,
                "base_url": base_url,
                "timeout": timeout,
                "max_output_tokens": max_output_tokens,
            }
        )
        options: dict[str, Any] = {
            "api_key": LOCAL_API_KEY if provider == "ollama" else None,
            "timeout": timeout,
            "max_retries": 0,
        }
        if provider == "ollama":
            options["base_url"] = base_url
        else:
            options["base_url"] = base_url or "https://api.openai.com/v1"
        self._client = OpenAI(**options)

    def call(self, packet: dict, prompt: str, schema: dict) -> dict:
        request_schema = specialize_schema(schema, packet)
        instruction = _scope_instruction(schema)
        scoped_prompt = f"{prompt}\n{instruction}"
        if self._config.provider == "ollama":
            with _ollama_request_lock():
                return self._call_ollama(packet, scoped_prompt, request_schema)
        return self._call_openai(packet, scoped_prompt, request_schema)

    def _call_openai(self, packet: dict, prompt: str, schema: dict) -> dict:
        response = self._client.responses.create(
            model=self._config.model,
            instructions=prompt,
            input=json.dumps(packet, ensure_ascii=False, separators=(",", ":")),
            max_output_tokens=self._config.max_output_tokens,
            reasoning={"effort": "none"},
            text=cast(Any, {"format": _schema_format(schema)}),
        )
        raw = json.dumps(response.model_dump(mode="json"), ensure_ascii=False)
        status = _response_status(response)
        return _result(
            raw,
            response.output_text or "",
            response.usage,
            status,
            _openai_finish_reason(response),
            response.id,
            "refusal" if _has_refusal(response) else None,
        )

    def _call_ollama(self, packet: dict, prompt: str, schema: dict) -> dict:
        system = f"{prompt}\nOutput JSON matching this schema: " + json.dumps(
            schema, ensure_ascii=False, separators=(",", ":")
        )
        response = self._client.chat.completions.create(
            model=self._config.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(packet, ensure_ascii=False)},
            ],
            max_tokens=self._config.max_output_tokens,
            temperature=0,
            reasoning_effort="none",
            response_format={"type": "json_object"},
        )
        choice = response.choices[0]
        finish_reason = choice.finish_reason
        return _result(
            json.dumps(response.model_dump(mode="json"), ensure_ascii=False),
            choice.message.content or "",
            response.usage,
            "incomplete" if finish_reason == "length" else "completed",
            finish_reason,
            response.id,
            "refusal" if getattr(choice.message, "refusal", None) else None,
        )


def _schema_format(schema: dict) -> dict:
    return {"type": "json_schema", "name": "role_result", "strict": True, "schema": schema}


def specialize_schema(schema: dict, packet: dict) -> dict:
    """Constrain reusable role schema enums to IDs present in one request packet."""
    result = deepcopy(schema)
    if "dates" in result["properties"]:
        return _specialize_dates(result, packet)
    properties = result["properties"]["speaker_roles"]["items"]["properties"]
    spans = packet["spans"]
    paragraphs = _ids_of_kinds(spans, {"paragraph"})
    cues = _ids_of_kinds(spans, {"speaker_cue", "person_cue"})
    evidence = _evidence_ids(spans)
    properties["candidate_id"]["enum"] = [*cues, None]
    properties["candidate_id"]["description"] = "A supplied C cue alias, or null."
    properties["target_ids"]["items"]["enum"] = paragraphs
    properties["target_ids"]["items"]["description"] = "A supplied P paragraph alias."
    properties["evidence_ids"]["items"]["enum"] = evidence
    properties["evidence_ids"]["items"]["description"] = "A supplied paragraph or cue alias."
    properties["role"]["enum"] = list(packet["controlled_role_ids"])
    properties["status"]["enum"] = list(packet["statuses"])
    return result


def _scope_instruction(schema: dict) -> str:
    if "dates" in schema["properties"]:
        return (
            "Use only supplied paragraph aliases. Keep dates within host-declared regions. "
            "Every paragraph needs a date proposal or explicit unknown; "
            "do not infer from catalog context."
        )
    return (
        "Use only IDs allowed by the supplied schema enums. candidate_id is a C alias, "
        "never a role label."
    )


def _specialize_dates(schema: dict, packet: dict) -> dict:
    source = DatePacket.model_validate(packet)
    aliases = [paragraph.alias for paragraph in source.paragraphs]
    definitions = schema["$defs"]
    definitions["DateAssignment"]["properties"]["target_ids"]["items"]["enum"] = aliases
    definitions["DateEvidence"]["properties"]["paragraph_id"]["enum"] = aliases
    return schema


def _ids_of_kinds(spans: list[dict], kinds: set[str]) -> list[str]:
    return [span["id"] for span in spans if span["kind"] in kinds]


def _evidence_ids(spans: list[dict]) -> list[str]:
    return [
        span["id"] for span in spans if span["kind"] == "paragraph" or span["kind"].endswith("cue")
    ]


def _response_status(response: Any) -> str:
    if _has_refusal(response):
        return "refusal"
    if response.status == "incomplete":
        return "incomplete"
    return response.status


def _has_refusal(response: Any) -> bool:
    return any(_output_has_refusal(item) for item in response.output)


def _output_has_refusal(item: Any) -> bool:
    if getattr(item, "type", None) == "refusal":
        return True
    return any(
        getattr(content, "type", None) == "refusal" for content in getattr(item, "content", [])
    )


def _openai_finish_reason(response: Any) -> str | None:
    details = getattr(response, "incomplete_details", None)
    return getattr(details, "reason", None)


def _result(
    raw: str,
    output: str,
    usage: Any,
    status: str,
    finish_reason: str | None,
    request_id: str | None,
    refusal: str | None,
) -> dict:
    return {
        "raw_response": raw,
        "output_text": output,
        "usage": _usage(usage),
        "status": refusal or status,
        "provider_request_id": request_id,
        "finish_reason": finish_reason,
    }


def _usage(usage: Any) -> dict:
    if usage is None:
        return {"input_tokens": None, "cached_input_tokens": None, "output_tokens": None}
    input_tokens = getattr(usage, "input_tokens", getattr(usage, "prompt_tokens", None))
    output_tokens = getattr(usage, "output_tokens", getattr(usage, "completion_tokens", None))
    details = getattr(usage, "input_tokens_details", None)
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", None)
    if cached is None and prompt_details is not None:
        cached = getattr(prompt_details, "cached_tokens", None)
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached,
        "output_tokens": output_tokens,
    }
