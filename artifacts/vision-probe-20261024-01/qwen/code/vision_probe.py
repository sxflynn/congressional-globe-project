"""Bounded, opt-in local Ollama vision probe for frozen scan-crop cases."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, model_validator

from congressional_globe.providers import _ollama_request_lock

REPO_ROOT = Path(__file__).resolve().parents[2]
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
MAX_CASES = 6
MAX_CASE_SECONDS = 90
MAX_BATCH_SECONDS = 600
MAX_OUTPUT_TOKENS = 256
MAX_CONTEXT_TOKENS = 8192
MODEL_DEFAULT = "qwen3.8:27b-mlx"


class ProbeCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    task: str = Field(min_length=1)
    ocr: str
    image: str | None = None
    image_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    expected_text: str | None = None
    expected_status: str = Field(min_length=1)

    @model_validator(mode="after")
    def matching_image_hash(self) -> ProbeCase:
        if (self.image is None) != (self.image_sha256 is None):
            raise ValueError("image and image_sha256 must either both be set or both be null")
        return self


class ProbePacket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    cases: list[ProbeCase] = Field(min_length=1, max_length=MAX_CASES)

    @model_validator(mode="after")
    def unique_case_ids(self) -> ProbePacket:
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("probe case IDs must be unique")
        return self


class VisionJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["correct", "unchanged", "uncertain"]
    transcription: str | None
    confidence: Literal["high", "medium", "low"]
    reason: str

    @model_validator(mode="after")
    def uncertain_has_no_transcription(self) -> VisionJudgment:
        if self.status == "uncertain" and self.transcription is not None:
            raise ValueError("uncertain judgments must have a null transcription")
        if self.status != "uncertain" and self.transcription is None:
            raise ValueError("correct and unchanged judgments need a transcription")
        return self


class _Tag(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    model: str | None = None
    digest: str
    details: dict[str, Any] = Field(default_factory=dict)


class _Tags(BaseModel):
    model_config = ConfigDict(extra="allow")

    models: list[_Tag]


class _Ps(BaseModel):
    model_config = ConfigDict(extra="allow")

    models: list[dict[str, Any]] = Field(default_factory=list)


class _Show(BaseModel):
    model_config = ConfigDict(extra="allow")

    capabilities: list[str] = Field(default_factory=list)
    family: str | None = None


class _Version(BaseModel):
    model_config = ConfigDict(extra="allow")

    version: str


class _ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    content: str


class _ChatResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: _ChatMessage
    done: bool
    done_reason: str | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None


class ResumeBlocked(ValueError):
    """A prior launch intent has no response, so execution state is unknown."""


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2).encode() + b"\n")


def _emit(output: Path, event: dict[str, Any]) -> None:
    with (output / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(json.dumps(event, ensure_ascii=False), flush=True)


def _load_packet(path: Path) -> tuple[ProbePacket, bytes, dict[str, bytes]]:
    source = path.read_bytes()
    packet = ProbePacket.model_validate_json(source)
    images = {case.id: _load_image(case) for case in packet.cases if case.image}
    return packet, source, images


def _load_image(case: ProbeCase) -> bytes:
    image_path = (REPO_ROOT / str(case.image)).resolve()
    if not image_path.is_relative_to(REPO_ROOT):
        raise ValueError(f"Case {case.id} image path escapes the repository")
    image = image_path.read_bytes()
    if _sha(image) != case.image_sha256:
        raise ValueError(f"Case {case.id} image SHA-256 mismatch")
    return image


def _config(model: str, expected_digest: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        raise ValueError("expected model digest must be a lowercase SHA-256")
    return {
        "model": model,
        "expected_digest": expected_digest,
        "base_url": OLLAMA_BASE_URL,
        "request_timeout_seconds": MAX_CASE_SECONDS,
        "batch_deadline_seconds": MAX_BATCH_SECONDS,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "num_ctx": MAX_CONTEXT_TOKENS,
        "temperature": 0,
        "think": False,
        "keep_alive": "5m",
        "stream": False,
    }


def _basis(
    packet_path: Path,
    source: bytes,
    packet: ProbePacket,
    images: dict[str, bytes],
    config: dict[str, Any],
) -> dict[str, Any]:
    code_hash = _sha(Path(__file__).read_bytes())
    basis = {
        "packet_version": packet.version,
        "cases_sha256": _sha(source),
        "image_sha256": {case_id: _sha(image) for case_id, image in images.items()},
        "config": config,
        "config_sha256": _sha(_canonical(config)),
        "code_sha256": code_hash,
        "cases_path": str(packet_path),
    }
    basis["basis_sha256"] = _sha(_canonical(basis))
    return basis


def _prepare_output(output: Path, basis: dict[str, Any], source: bytes) -> None:
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("basis_sha256") != basis["basis_sha256"]:
            raise ValueError("Output directory belongs to a different input/config/code basis")
        return
    if any(output.iterdir()):
        raise ValueError("Output directory must be new or contain a compatible manifest")
    _write_json(manifest_path, {"schema_version": "vision-probe-v1", **basis})
    _atomic_write(output / "cases.input.json", source)


def _request(url: str, body: bytes | None = None) -> tuple[bytes, float]:
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method="POST" if body else "GET")
    started = time.monotonic()
    with urlopen(request, timeout=MAX_CASE_SECONDS) as response:
        raw = response.read()
    return raw, time.monotonic() - started


def _get_json(path: Path, endpoint: str, body: dict[str, Any] | None = None) -> tuple[Any, float]:
    raw_body = None if body is None else _canonical(body)
    raw, elapsed = _request(f"{OLLAMA_BASE_URL}{endpoint}", raw_body)
    _atomic_write(path, raw)
    return json.loads(raw), elapsed


def _preflight(directory: Path, model: str, expected_digest: str) -> dict[str, Any]:
    root = directory / "preflight"
    tags_data, tags_time = _get_json(root / "tags.json", "/api/tags")
    ps_data, ps_time = _get_json(root / "ps.json", "/api/ps")
    version_data, version_time = _get_json(root / "version.json", "/api/version")
    show_data, show_time = _get_json(root / "show.json", "/api/show", {"model": model})
    selected, ps, version, show = _validate_preflight(
        tags_data, ps_data, version_data, show_data, model, expected_digest
    )
    summary = _preflight_summary(
        model,
        selected,
        ps,
        version,
        show,
        (tags_data, ps_data, show_data),
        (tags_time, ps_time, version_time, show_time),
    )
    _write_json(directory / "preflight.json", summary)
    return summary


def _validate_preflight(
    tags_data: Any,
    ps_data: Any,
    version_data: Any,
    show_data: Any,
    model: str,
    expected_digest: str,
) -> tuple[_Tag, _Ps, _Version, _Show]:
    tags = _Tags.model_validate(tags_data)
    ps = _Ps.model_validate(ps_data)
    version = _Version.model_validate(version_data)
    show = _Show.model_validate(show_data)
    selected = _select_tag(tags, model, expected_digest)
    _validate_vision(show)
    return selected, ps, version, show


def _select_tag(tags: _Tags, model: str, expected_digest: str) -> _Tag:
    selected = next((tag for tag in tags.models if model in {tag.name, tag.model}), None)
    if selected is None:
        raise ValueError(f"Selected model {model!r} is not installed")
    if selected.digest != expected_digest:
        raise ValueError("Installed model digest does not match --expected-digest")
    if selected.details.get("runner") != "mlx":
        raise ValueError("Selected model is not reported with the MLX runner")
    return selected


def _validate_vision(show: _Show) -> None:
    if "vision" not in show.capabilities:
        raise ValueError("Selected model does not report vision capability")


def _preflight_summary(
    model: str,
    selected: _Tag,
    ps: _Ps,
    version: _Version,
    show: _Show,
    raw: tuple[Any, Any, Any],
    times: tuple[float, float, float, float],
) -> dict[str, Any]:
    tags_data, ps_data, show_data = raw
    tags_time, ps_time, version_time, show_time = times
    summary = {
        "model": model,
        "digest": selected.digest,
        "runner": selected.details.get("runner"),
        "capabilities": show.capabilities,
        "family": show.family,
        "version": version.version,
        "tags_sha256": _sha(_canonical(tags_data)),
        "ps_sha256": _sha(_canonical(ps_data)),
        "show_sha256": _sha(_canonical(show_data)),
        "preflight_elapsed_seconds": {
            "tags": tags_time,
            "ps": ps_time,
            "version": version_time,
            "show": show_time,
        },
        "loaded_models": ps.models,
    }
    return summary


def _request_payload(
    packet: ProbePacket, case: ProbeCase, model: str, image: bytes | None
) -> dict[str, Any]:
    user_content = f"Task:\n{case.task}\n\nOCR text:\n{case.ocr}"
    user_message: dict[str, Any] = {"role": "user", "content": user_content}
    if image is not None:
        user_message["images"] = [base64.b64encode(image).decode("ascii")]
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": packet.prompt},
            user_message,
        ],
        "format": VisionJudgment.model_json_schema(),
        "options": {
            "temperature": 0,
            "num_predict": MAX_OUTPUT_TOKENS,
            "num_ctx": MAX_CONTEXT_TOKENS,
        },
        "think": False,
        "keep_alive": "5m",
        "stream": False,
    }


def _result_from_raw(case: ProbeCase, raw: bytes, elapsed: float | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "case_id": case.id,
        "status": "invalid_schema",
        "expected": {"status": case.expected_status, "text": case.expected_text},
        "proposed": None,
        "evaluation": {},
        "elapsed_seconds": elapsed,
        "input_tokens": None,
        "output_tokens": None,
        "done_reason": None,
    }
    try:
        response = _ChatResponse.model_validate_json(raw)
    except ValueError as error:
        return _invalid_result(result, error)
    result.update(
        {
            "input_tokens": response.prompt_eval_count,
            "output_tokens": response.eval_count,
            "done_reason": response.done_reason,
        }
    )
    if not response.done or response.done_reason != "stop":
        result["status"] = (
            "truncated" if response.done_reason == "length" else "incomplete_response"
        )
        return result
    return _validate_judgment(result, case, response.message.content)


def _invalid_result(result: dict[str, Any], error: ValueError) -> dict[str, Any]:
    result["validation_error"] = str(error)
    return result


def _validate_judgment(result: dict[str, Any], case: ProbeCase, content: str) -> dict[str, Any]:
    try:
        judgment = VisionJudgment.model_validate_json(content)
    except ValueError as error:
        return _invalid_result(result, error)
    result.update(
        {
            "status": "valid",
            "proposed": judgment.model_dump(mode="json"),
            "evaluation": {
                "status_matches": judgment.status == case.expected_status,
                "text_matches": (
                    None
                    if case.expected_text is None
                    else judgment.transcription == case.expected_text
                ),
            },
        }
    )
    return result


def _event(
    output: Path, case: ProbeCase, completed: int, total: int, result: dict[str, Any]
) -> None:
    proposed = result.get("proposed")
    event = {
        "event": "case_completed",
        "case_id": case.id,
        "completed": completed,
        "total": total,
        "elapsed_seconds": result.get("elapsed_seconds"),
        "status": result["status"],
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "before": case.ocr,
        "proposed": None if proposed is None else proposed.get("transcription"),
    }
    _emit(output, event)


def _case_dir(output: Path, case_id: str) -> Path:
    return output / "cases" / case_id


def _recover_or_block(output: Path, packet: ProbePacket) -> set[str]:
    return {case.id for case in packet.cases if _recover_case(output, case)}


def _recover_case(output: Path, case: ProbeCase) -> bool:
    directory = _case_dir(output, case.id)
    result_path = directory / "result.json"
    response_path = directory / "response.raw"
    intent_path = directory / "intent.json"
    if intent_path.exists() and not response_path.exists():
        raise ResumeBlocked(
            f"Case {case.id} has launch intent but no response; execution state is unknown"
        )
    if result_path.exists():
        return True
    if response_path.exists():
        result = _result_from_raw(case, response_path.read_bytes(), None)
        _write_json(result_path, result)
        return True
    return False


def _transport_failure(
    output: Path, case: ProbeCase, error: Exception, elapsed: float
) -> dict[str, Any]:
    result = {
        "case_id": case.id,
        "status": "execution_unknown",
        "error": f"{type(error).__name__}: {error}",
        "elapsed_seconds": elapsed,
        "before": case.ocr,
        "proposed": None,
    }
    _write_json(_case_dir(output, case.id) / "result.json", result)
    _emit(output, {"event": "execution_unknown", "case_id": case.id, "elapsed_seconds": elapsed})
    return result


def _run_case(
    output: Path,
    packet: ProbePacket,
    case: ProbeCase,
    model: str,
    image: bytes | None,
    completed: int,
    total: int,
) -> dict[str, Any]:
    directory = _case_dir(output, case.id)
    directory.mkdir(parents=True, exist_ok=True)
    payload = _request_payload(packet, case, model, image)
    body = _canonical(payload)
    _atomic_write(directory / "request.json", body)
    _write_json(
        directory / "intent.json",
        {"at": datetime.now(UTC).isoformat(), "request_sha256": _sha(body)},
    )
    _emit(
        output,
        {
            "event": "case_started",
            "case_id": case.id,
            "completed": completed,
            "total": total,
            "before": case.ocr,
            "status": "started",
        },
    )
    started = time.monotonic()
    try:
        raw, elapsed = _request(f"{OLLAMA_BASE_URL}/api/chat", body)
    except Exception as error:
        result = _transport_failure(output, case, error, time.monotonic() - started)
        _event(output, case, completed + 1, total, result)
        return result
    _atomic_write(directory / "response.raw", raw)
    result = _result_from_raw(case, raw, elapsed)
    _write_json(directory / "result.json", result)
    _event(output, case, completed + 1, total, result)
    return result


def run_probe(
    cases_path: Path,
    output: Path,
    model: str = MODEL_DEFAULT,
    expected_digest: str = "",
    live: bool = False,
) -> dict[str, Any]:
    packet, source, images = _load_packet(cases_path)
    config = _config(model, expected_digest)
    basis = _basis(cases_path.resolve(), source, packet, images, config)
    if not live:
        return {
            "status": "offline_only",
            "case_count": len(packet.cases),
            "basis_sha256": basis["basis_sha256"],
        }
    _prepare_output(output, basis, source)
    completed_cases = _recover_or_block(output, packet)
    pending = [case for case in packet.cases if case.id not in completed_cases]
    if not pending:
        return _summary(output, packet, completed_cases)
    return _launch(output, packet, pending, images, model, expected_digest, basis, completed_cases)


def _launch(
    output: Path,
    packet: ProbePacket,
    pending: list[ProbeCase],
    images: dict[str, bytes],
    model: str,
    expected_digest: str,
    basis: dict[str, Any],
    completed_cases: set[str],
) -> dict[str, Any]:
    started = time.monotonic()
    _write_json(
        output / "launch-intent.json",
        {
            "at": datetime.now(UTC).isoformat(),
            "basis_sha256": basis["basis_sha256"],
            "case_ids": [case.id for case in pending],
        },
    )
    with _ollama_request_lock():
        preflight = _preflight(output, model, expected_digest)
        _run_pending(output, packet, pending, images, model, started, completed_cases)
    summary = _summary(output, packet, completed_cases, preflight)
    _write_json(output / "summary.json", summary)
    return summary


def _run_pending(
    output: Path,
    packet: ProbePacket,
    pending: list[ProbeCase],
    images: dict[str, bytes],
    model: str,
    started: float,
    completed: set[str],
) -> None:
    for case in pending:
        if time.monotonic() - started >= MAX_BATCH_SECONDS:
            return
        result = _run_case(
            output, packet, case, model, images.get(case.id), len(completed), len(packet.cases)
        )
        completed.add(case.id)
        if result["status"] == "execution_unknown":
            return


def _summary(
    output: Path, packet: ProbePacket, completed: set[str], preflight: dict[str, Any] | None = None
) -> dict[str, Any]:
    results = _saved_results(output, packet)
    status = _summary_status(completed, packet, results)
    preflight_brief = _brief_preflight(preflight)
    return {
        "status": status,
        "completed": len(completed),
        "total": len(packet.cases),
        "results": results,
        "preflight": preflight_brief,
    }


def _saved_results(output: Path, packet: ProbePacket) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text())
        for case in packet.cases
        if (path := _case_dir(output, case.id) / "result.json").exists()
    ]


def _summary_status(completed: set[str], packet: ProbePacket, results: list[dict[str, Any]]) -> str:
    if any(result["status"] == "execution_unknown" for result in results):
        return "failed"
    return "complete" if len(completed) == len(packet.cases) else "incomplete"


def _brief_preflight(preflight: dict[str, Any] | None) -> dict[str, Any] | None:
    keys = ("model", "digest", "runner", "capabilities", "family", "version")
    return None if preflight is None else {key: preflight[key] for key in keys}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=MODEL_DEFAULT)
    parser.add_argument("--expected-digest", required=True)
    parser.add_argument("--live", action="store_true", help="make bounded local Ollama requests")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_probe(args.cases, args.output, args.model, args.expected_digest, args.live)
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] in {"complete", "offline_only"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
