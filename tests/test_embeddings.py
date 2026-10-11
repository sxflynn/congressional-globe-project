"""Embedding boundary tests use mocked transport and never contact a model."""

import hashlib
import json
from io import BytesIO

import pytest
from pydantic import ValidationError

from congressional_globe.embeddings import (
    EmbeddingBatch,
    EmbeddingConfig,
    OllamaEmbeddingProvider,
    Passage,
    PassageSource,
)


def _passage(**overrides):
    values = {
        "passage_id": "p1",
        "text": "A sourced passage.",
        "text_layer": "raw_ocr",
        "source": PassageSource(
            item_identifier="globe_1866",
            part_number=1,
            paragraph_ids=["para-1"],
            scan_leaves=[12],
            printed_pages=["42"],
            hocr_page_ids=["page_12"],
            hocr_line_ids=["line_1"],
        ),
    }
    values.update(overrides)
    return Passage.model_validate(values)


def test_passage_hashes_text_and_keeps_unknowns_explicit():
    passage = _passage()
    assert passage.text_sha256 == hashlib.sha256(passage.text.encode()).hexdigest()
    assert passage.metadata.date is None
    assert passage.metadata.date_status == "unknown"
    assert passage.source.paragraph_ids == ["para-1"]
    assert passage.metadata.congress_number is None


@pytest.mark.parametrize(
    ("status", "value"),
    [("known", None), ("unknown", "1866-01-01"), ("mixed", "Speaker")],
)
def test_passage_metadata_rejects_inconsistent_status(status, value):
    from congressional_globe.embeddings import PassageMetadata

    with pytest.raises(ValidationError, match="date must be populated"):
        PassageMetadata(date=value, date_status=status)


def test_passage_rejects_mismatched_hash_and_invalid_part():
    with pytest.raises(ValidationError, match="text_sha256"):
        _passage(text_sha256="0" * 64)
    with pytest.raises(ValidationError):
        PassageSource(item_identifier="x", part_number=6, paragraph_ids=["p"], scan_leaves=[1])


def test_provider_sends_explicit_dimensions_and_no_truncation(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["body"] = json.loads(request.data)
        seen["timeout"] = timeout
        return BytesIO(
            b'{"model":"qwen3-embedding:4b","embeddings": [[3.0, 4.0]], "prompt_eval_count": 2}'
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(
        "congressional_globe.embeddings._ollama_request_lock", lambda: _NullContext()
    )
    provider = OllamaEmbeddingProvider("qwen3-embedding:4b", dimensions=2, timeout_seconds=7)
    result = provider.embed(["passage"], purpose="document")
    assert seen["body"] == {
        "model": "qwen3-embedding:4b",
        "input": ["passage"],
        "dimensions": 2,
        "truncate": False,
    }
    assert seen["timeout"] == 7
    assert result.prompt_eval_count == 2
    assert result.embeddings == [[0.6, 0.8]]
    assert result.config.timeout_seconds == 7
    assert result.config.endpoint == "http://localhost:11434/api/embed"


def test_provider_hashes_prefixed_query_and_validates_returned_vectors(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["body"] = json.loads(request.data)
        return BytesIO(b'{"model":"model","embeddings": [[0.6, 0.8]]}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(
        "congressional_globe.embeddings._ollama_request_lock", lambda: _NullContext()
    )
    provider = OllamaEmbeddingProvider("model", dimensions=2, query_prefix="Task: ")
    result = provider.embed(["query"], purpose="query")
    assert seen["body"]["input"] == ["Task: query"]
    assert result.input_hashes == [hashlib.sha256(b"Task: query").hexdigest()]
    with pytest.raises(ValueError, match="purpose"):
        provider.embed(["x"], purpose="other")


@pytest.mark.parametrize(
    ("vectors", "error"),
    [([], "count"), ([[1.0]], "dimension"), ([[float("nan"), 1.0]], "non-finite")],
)
def test_batch_rejects_count_dimension_and_nonfinite(vectors, error):
    with pytest.raises(ValidationError, match=error):
        EmbeddingBatch(
            config=EmbeddingConfig(backend="test", model="m", dimensions=2),
            input_hashes=["hash"],
            embeddings=vectors,
        )


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (b'{"model":"m","embeddings":[["bad", 1]]}', "float"),
        (b'{"model":"other","embeddings":[[1, 0]]}', "requested"),
        (b'{"model":"m","embeddings":[[0, 0]]}', "zero-norm"),
        (b'{"model":"m","embeddings":[[1, 0], [1, 0]]}', "count"),
    ],
)
def test_provider_rejects_malformed_identity_and_vectors(monkeypatch, response, error):
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: BytesIO(response))
    monkeypatch.setattr(
        "congressional_globe.embeddings._ollama_request_lock", lambda: _NullContext()
    )
    provider = OllamaEmbeddingProvider("m", dimensions=2)
    with pytest.raises((ValidationError, ValueError), match=error):
        provider.embed(["x"], purpose="document")


class _NullContext:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None
