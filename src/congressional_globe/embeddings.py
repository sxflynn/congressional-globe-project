"""Model-independent, source-linked passage embeddings and Ollama transport."""

from __future__ import annotations

import hashlib
import json
import math
import urllib.error
import urllib.request
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from congressional_globe.providers import _ollama_request_lock


class PassageSource(BaseModel):
    """Stable references to the source paragraphs and available page anchors."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_identifier: str
    part_number: int = Field(ge=1, le=5)
    paragraph_ids: list[str] = Field(min_length=1)
    scan_leaves: list[int] = Field(min_length=1, description="Zero-based IA scan leaves")
    printed_pages: list[str] = Field(default_factory=list)
    hocr_page_ids: list[str] = Field(default_factory=list)
    hocr_line_ids: list[str] = Field(default_factory=list)


class PassageMetadata(BaseModel):
    """Explicitly nullable observations; null means unknown, not an inference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    congress_number: int | None = Field(default=None, ge=1)
    session_number: int | None = Field(default=None, ge=1)
    year: int | None = Field(default=None, ge=1789)
    date: str | None = None
    date_status: Literal["known", "unknown", "mixed", "conflicting"] = "unknown"
    speaker: str | None = None
    speaker_status: Literal["known", "unknown", "mixed", "conflicting"] = "unknown"
    chamber: str | None = None
    chamber_status: Literal["known", "unknown", "mixed", "conflicting"] = "unknown"
    topic_hints: list[str] = Field(default_factory=list)
    verified_subject_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_known_values(self) -> PassageMetadata:
        _validate_status_value(self.date_status, self.date, "date")
        _validate_status_value(self.speaker_status, self.speaker, "speaker")
        _validate_status_value(self.chamber_status, self.chamber, "chamber")
        return self


class Passage(BaseModel):
    """A retrieval view over unchanged text with exact paragraph/source identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    passage_id: str
    text: str = Field(min_length=1)
    text_layer: str
    text_sha256: str | None = None
    source: PassageSource
    metadata: PassageMetadata = Field(default_factory=PassageMetadata)

    @model_validator(mode="after")
    def validate_text_hash(self) -> Passage:
        actual = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        if self.text_sha256 is not None and self.text_sha256 != actual:
            raise ValueError("text_sha256 does not match passage text")
        object.__setattr__(self, "text_sha256", actual)
        return self


class EmbeddingConfig(BaseModel):
    """Frozen identity settings needed to keep vector spaces separate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend: str
    model: str
    revision: str | None = None
    dimensions: int = Field(gt=0)
    normalization: str = "l2"
    truncation: str = "provider_native_dimensions"
    document_prefix: str = ""
    query_prefix: str = ""
    timeout_seconds: float = Field(default=120, gt=0)
    endpoint: str | None = None

    @property
    def digest(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class EmbeddingBatch(BaseModel):
    """Validated vectors and the exact embedding configuration identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    config: EmbeddingConfig
    input_hashes: list[str]
    embeddings: list[list[float]]
    prompt_eval_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_vectors(self) -> EmbeddingBatch:
        _validate_vector_batch(self.input_hashes, self.embeddings, self.config.dimensions)
        return self


class EmbeddingProvider(Protocol):
    """Provider-neutral document/query embedding boundary."""

    @property
    def config(self) -> EmbeddingConfig: ...

    def embed(self, texts: list[str], *, purpose: str) -> EmbeddingBatch: ...


class OllamaEmbedResponse(BaseModel):
    """Validated Ollama wire response before any vector transformation."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    model: str
    embeddings: list[list[float]]
    prompt_eval_count: int | None = Field(default=None, ge=0)
    total_duration: int | None = Field(default=None, ge=0)
    load_duration: int | None = Field(default=None, ge=0)


class OllamaEmbeddingProvider:
    """Sequential Ollama /api/embed adapter; refuses implicit input truncation."""

    def __init__(
        self,
        model: str,
        *,
        dimensions: int,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 120,
        revision: str | None = None,
        query_prefix: str = "",
    ) -> None:
        self._url = base_url.rstrip("/") + "/api/embed"
        self._timeout = timeout_seconds
        self._config = EmbeddingConfig(
            backend="ollama_api_embed",
            model=model,
            revision=revision,
            dimensions=dimensions,
            query_prefix=query_prefix,
            timeout_seconds=timeout_seconds,
            endpoint=self._url,
        )

    @property
    def config(self) -> EmbeddingConfig:
        return self._config

    def embed(self, texts: list[str], *, purpose: str) -> EmbeddingBatch:
        if not texts or any(not text.strip() for text in texts):
            raise ValueError("embedding input must contain non-empty texts")
        prefix = _prefix(self._config, purpose)
        inputs = [prefix + text for text in texts]
        payload = json.dumps(
            {
                "model": self._config.model,
                "input": inputs,
                "dimensions": self._config.dimensions,
                "truncate": False,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self._url, data=payload, headers={"Content-Type": "application/json"}
        )
        with _ollama_request_lock():
            response = _request_json(request, self._timeout)
        if response.model != self._config.model:
            raise ValueError(
                f"Ollama returned model {response.model!r}; requested {self._config.model!r}"
            )
        _validate_vector_batch(inputs, response.embeddings, self._config.dimensions)
        return EmbeddingBatch(
            config=self._config,
            input_hashes=[hashlib.sha256(text.encode()).hexdigest() for text in inputs],
            embeddings=_l2_normalize(response.embeddings),
            prompt_eval_count=response.prompt_eval_count,
        )


def _prefix(config: EmbeddingConfig, purpose: str) -> str:
    if purpose == "document":
        return config.document_prefix
    if purpose == "query":
        return config.query_prefix
    raise ValueError("purpose must be 'document' or 'query'")


def _request_json(request: urllib.request.Request, timeout: float) -> OllamaEmbedResponse:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Ollama embedding request failed: {error}") from error
    return OllamaEmbedResponse.model_validate(result)


def _l2_normalize(vectors: list[list[float]]) -> list[list[float]]:
    return [_normalize(vector) for vector in vectors]


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        raise ValueError("Ollama returned a zero-norm embedding")
    return [value / norm for value in vector]


def _validate_vector_batch(hashes: list[str], vectors: list[list[float]], dimensions: int) -> None:
    if len(hashes) != len(vectors):
        raise ValueError("embedding count does not match input count")
    for vector in vectors:
        _validate_vector(vector, dimensions)


def _validate_vector(vector: list[float], dimensions: int) -> None:
    if len(vector) != dimensions:
        raise ValueError("embedding dimension does not match configuration")
    if any(not math.isfinite(value) for value in vector):
        raise ValueError("embedding contains a non-finite value")


def _validate_status_value(status: str, value: str | None, field_name: str) -> None:
    if (status == "known") != (value is not None):
        raise ValueError(f"{field_name} must be populated only when status is known")
