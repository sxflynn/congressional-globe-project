from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from urllib.error import URLError

import pytest

from congressional_globe import vision_probe as probe

DIGEST = "a" * 64


class Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class FakeOllama:
    def __init__(self, chat_contents: list[str] | None = None, bad_digest: bool = False):
        self.calls: list[tuple[str, dict | None]] = []
        self.chat_contents = chat_contents or [_judgment()]
        self.bad_digest = bad_digest

    def __call__(self, request, timeout: int) -> Response:
        url = request.full_url
        body = None if request.data is None else json.loads(request.data)
        self.calls.append((url, body))
        value = self._api_value(url)
        return Response(json.dumps(value).encode())

    def _api_value(self, url: str) -> dict:
        routes = {
            "/api/tags": self._tags,
            "/api/ps": lambda: {"models": []},
            "/api/version": lambda: {"version": "0.1-test"},
            "/api/show": lambda: {
                "details": {"family": "qwen3_5"},
                "capabilities": ["completion", "vision"],
            },
            "/api/chat": self._chat,
        }
        for path, handler in routes.items():
            if url.endswith(path):
                return handler()
        raise AssertionError(f"unexpected URL: {url}")

    def _tags(self) -> dict:
        digest = "b" * 64 if self.bad_digest else DIGEST
        return {
            "models": [
                {"name": probe.MODEL_DEFAULT, "digest": digest, "details": {"runner": "mlx"}}
            ]
        }

    def _chat(self) -> dict:
        content = self.chat_contents.pop(0)
        return {
            "message": {"content": content},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 11,
            "eval_count": 7,
        }


def _judgment(status: str = "correct", text: str = "hello") -> str:
    return json.dumps(
        {"status": status, "transcription": text, "confidence": "high", "reason": "clear"}
    )


def _packet(tmp_path: Path, monkeypatch, cases: list[dict] | None = None) -> Path:
    monkeypatch.setattr(probe, "REPO_ROOT", tmp_path)
    image = b"synthetic-jpeg-bytes"
    (tmp_path / "crop.jpg").write_bytes(image)
    rows = cases or [
        {
            "id": "case-one",
            "task": "transcribe",
            "ocr": "helo",
            "image": "crop.jpg",
            "image_sha256": hashlib.sha256(image).hexdigest(),
            "expected_text": "hello",
            "expected_status": "correct",
        }
    ]
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"version": "v1", "prompt": "Judge the crop.", "cases": rows}))
    return path


def _expected_only(case: dict) -> dict:
    return {
        key: case[key]
        for key in (
            "id",
            "task",
            "ocr",
            "image",
            "image_sha256",
            "expected_text",
            "expected_status",
        )
    }


def test_offline_default_validates_without_network_or_output(tmp_path, monkeypatch):
    path = _packet(tmp_path, monkeypatch)
    monkeypatch.setattr(probe, "urlopen", lambda *_args, **_kwargs: pytest.fail("network called"))
    output = tmp_path / "output"

    result = probe.run_probe(path, output, expected_digest=DIGEST)

    assert result["status"] == "offline_only"
    assert result["case_count"] == 1
    assert not output.exists()


def test_live_saves_preflight_request_raw_response_and_expected_stays_out_of_request(
    tmp_path, monkeypatch
):
    path = _packet(tmp_path, monkeypatch)
    fake = FakeOllama()
    monkeypatch.setattr(probe, "urlopen", fake)
    output = tmp_path / "run"

    result = probe.run_probe(path, output, expected_digest=DIGEST, live=True)

    assert result["status"] == "complete"
    assert result["preflight"]["family"] == "qwen3_5"
    assert (output / "preflight/tags.json").exists()
    assert (output / "cases/case-one/response.raw").exists()
    request = json.loads((output / "cases/case-one/request.json").read_text())
    assert request["think"] is False
    assert request["keep_alive"] == "5m"
    assert request["options"] == {"temperature": 0, "num_predict": 256, "num_ctx": 8192}
    assert request["messages"][1]["images"] == [base64.b64encode(b"synthetic-jpeg-bytes").decode()]
    assert "expected_text" not in json.dumps(request)
    assert "expected_status" not in json.dumps(request)
    assert len(fake.calls) == 5
    saved = json.loads((output / "cases/case-one/result.json").read_text())
    assert saved["input_tokens"] == 11
    assert saved["output_tokens"] == 7
    assert saved["evaluation"] == {"status_matches": True, "text_matches": True}


def test_json_mode_uses_prompt_schema_and_is_part_of_resume_basis(tmp_path, monkeypatch):
    path = _packet(tmp_path, monkeypatch)
    output = tmp_path / "json-run"
    monkeypatch.setattr(probe, "urlopen", FakeOllama())

    result = probe.run_probe(
        path, output, expected_digest=DIGEST, live=True, response_format="json"
    )

    assert result["status"] == "complete"
    request = json.loads((output / "cases/case-one/request.json").read_text())
    assert request["format"] == "json"
    assert '"status"' in request["messages"][0]["content"]
    assert json.loads((output / "manifest.json").read_text())["config"]["response_format"] == "json"
    with pytest.raises(ValueError, match="different input/config/code basis"):
        probe.run_probe(path, output, expected_digest=DIGEST, live=True, response_format="schema")


def test_digest_mismatch_stops_before_chat_and_records_raw_preflight(tmp_path, monkeypatch):
    path = _packet(tmp_path, monkeypatch)
    fake = FakeOllama(bad_digest=True)
    monkeypatch.setattr(probe, "urlopen", fake)

    with pytest.raises(ValueError, match="digest"):
        probe.run_probe(path, tmp_path / "run", expected_digest=DIGEST, live=True)

    assert not any(url.endswith("/api/chat") for url, _ in fake.calls)
    assert (tmp_path / "run/preflight/tags.json").exists()


def test_invalid_judgment_continues_and_preserves_usage(tmp_path, monkeypatch):
    rows = [
        {"id": "bad", "task": "t", "ocr": "x", "expected_text": "x", "expected_status": "correct"},
        {"id": "good", "task": "t", "ocr": "y", "expected_text": "y", "expected_status": "correct"},
    ]
    path = _packet(tmp_path, monkeypatch, rows)
    fake = FakeOllama(["{bad json", _judgment(text="y")])
    monkeypatch.setattr(probe, "urlopen", fake)

    result = probe.run_probe(path, tmp_path / "run", expected_digest=DIGEST, live=True)

    assert result["status"] == "complete"
    assert [item["status"] for item in result["results"]] == ["invalid_schema", "valid"]
    assert result["results"][0]["input_tokens"] == 11
    assert result["results"][0]["done_reason"] == "stop"
    assert sum(url.endswith("/api/chat") for url, _ in fake.calls) == 2


def test_completed_compatible_run_resumes_without_network(tmp_path, monkeypatch):
    path = _packet(tmp_path, monkeypatch)
    output = tmp_path / "run"
    monkeypatch.setattr(probe, "urlopen", FakeOllama())
    probe.run_probe(path, output, expected_digest=DIGEST, live=True)
    monkeypatch.setattr(
        probe, "urlopen", lambda *_args, **_kwargs: pytest.fail("network called on replay")
    )

    result = probe.run_probe(path, output, expected_digest=DIGEST, live=True)

    assert result["status"] == "complete"
    assert result["completed"] == 1


def test_interrupted_intent_without_response_blocks_replay(tmp_path, monkeypatch):
    path = _packet(tmp_path, monkeypatch)
    output = tmp_path / "run"
    fake = FakeOllama()

    def interrupted(request, timeout: int) -> Response:
        if request.full_url.endswith("/api/chat"):
            raise KeyboardInterrupt
        return fake(request, timeout)

    monkeypatch.setattr(probe, "urlopen", interrupted)
    with pytest.raises(KeyboardInterrupt):
        probe.run_probe(path, output, expected_digest=DIGEST, live=True)
    monkeypatch.setattr(
        probe, "urlopen", lambda *_args, **_kwargs: pytest.fail("network called on replay")
    )

    with pytest.raises(probe.ResumeBlocked, match="execution state is unknown"):
        probe.run_probe(path, output, expected_digest=DIGEST, live=True)


def test_transport_failure_stops_without_retry_and_returns_failure(tmp_path, monkeypatch):
    path = _packet(tmp_path, monkeypatch)
    fake = FakeOllama()

    def failing_chat(request, timeout: int) -> Response:
        if request.full_url.endswith("/api/chat"):
            raise URLError("offline")
        return fake(request, timeout)

    monkeypatch.setattr(probe, "urlopen", failing_chat)
    result = probe.run_probe(path, tmp_path / "run", expected_digest=DIGEST, live=True)

    assert result["status"] == "failed"
    assert sum(url.endswith("/api/chat") for url, _ in fake.calls) == 0
    assert result["results"][0]["status"] == "execution_unknown"


def test_input_image_hash_mismatch_is_rejected_before_http(tmp_path, monkeypatch):
    path = _packet(tmp_path, monkeypatch)
    (tmp_path / "crop.jpg").write_bytes(b"changed")
    monkeypatch.setattr(probe, "urlopen", lambda *_args, **_kwargs: pytest.fail("network called"))

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        probe.run_probe(path, tmp_path / "run", expected_digest=DIGEST, live=True)
