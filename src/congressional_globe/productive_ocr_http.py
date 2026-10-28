"""Bounded loopback HTTP framing and conservative Ollama response normalization."""

from __future__ import annotations

import base64
import http.client
import io
import socket
import threading
import time
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

MAX_RESPONSE_BYTES = 32 * 1024 * 1024


class OllamaMessage(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True, frozen=True)
    role: str
    content: str


class OllamaChatResponse(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True, frozen=True)
    model: str
    message: OllamaMessage
    done: bool
    done_reason: str | None = None
    prompt_eval_count: int | None = Field(default=None, ge=0)
    eval_count: int | None = Field(default=None, ge=0)


class _MemorySocket:
    def __init__(self, payload: bytes) -> None:
        self.stream = _NonClosingBytesIO(payload)

    def makefile(self, _mode: str) -> io.BytesIO:
        return self.stream

    def trailing_bytes(self) -> bytes:
        return self.stream.read()


class _NonClosingBytesIO(io.BytesIO):
    def close(self) -> None:
        return


class HttpResponseBytes(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    status: int = Field(ge=100, le=599)
    body: bytes


class HttpExchangeFailure(RuntimeError):
    def __init__(self, message: str, partial: bytes, body_sent: bool) -> None:
        super().__init__(message)
        self.partial = partial
        self.body_sent = body_sent


def exchange(
    host: str,
    port: int,
    method: str,
    path: str,
    body: bytes,
    timeout: float,
    sent: threading.Event | None = None,
    cancelled: threading.Event | None = None,
    max_bytes: int = MAX_RESPONSE_BYTES,
    send_lock: threading.Lock | None = None,
) -> bytes:
    """Send exact body bytes and collect exact HTTP response bytes until close."""
    request = _request_bytes(host, port, method, path, body)
    deadline = time.monotonic() + timeout
    chunks = bytearray()
    body_sent = False
    try:
        _check_receive_cancel(cancelled)
        with socket.create_connection((host, port), timeout=min(timeout, 2.0)) as connection:
            connection.settimeout(0.25)
            _send_request(connection, request, sent, cancelled, send_lock or threading.Lock())
            body_sent = True
            _receive(connection, chunks, deadline, max_bytes, cancelled)
    except Exception as exc:
        raise HttpExchangeFailure(str(exc), bytes(chunks), body_sent) from exc
    return bytes(chunks)


def _send_request(
    connection: socket.socket,
    request: bytes,
    sent: threading.Event | None,
    cancelled: threading.Event | None,
    send_lock: threading.Lock,
) -> None:
    with send_lock:
        _check_receive_cancel(cancelled)
        connection.sendall(request)
        if sent is not None:
            sent.set()


def _request_bytes(host: str, port: int, method: str, path: str, body: bytes) -> bytes:
    headers = (
        f"{method} {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")
    return headers + body


def _receive(
    connection: socket.socket,
    chunks: bytearray,
    deadline: float,
    max_bytes: int,
    cancelled: threading.Event | None,
) -> None:
    while True:
        _check_receive_cancel(cancelled)
        part = _read_receive_chunk(connection, deadline)
        if part is None:
            continue
        if not part:
            break
        _append_receive_chunk(chunks, part, max_bytes)


def _check_receive_cancel(cancelled: threading.Event | None) -> None:
    if cancelled is not None and cancelled.is_set():
        raise TimeoutError("owned HTTP request cancelled")


def _read_receive_chunk(connection: socket.socket, deadline: float) -> bytes | None:
    try:
        return connection.recv(64 * 1024)
    except TimeoutError:
        if time.monotonic() >= deadline:
            raise TimeoutError("owned HTTP response exceeded request deadline") from None
        return None


def _append_receive_chunk(chunks: bytearray, part: bytes, max_bytes: int) -> None:
    chunks.extend(part)
    if len(chunks) > max_bytes:
        raise ValueError("owned HTTP response exceeds spool ceiling")


def parse_response(raw_http: bytes, max_bytes: int = MAX_RESPONSE_BYTES) -> HttpResponseBytes:
    """Parse response framing only after caller has durably spooled raw_http."""
    if len(raw_http) > max_bytes or b"\r\n\r\n" not in raw_http:
        raise ValueError("malformed or oversized raw HTTP response")
    memory_socket = _MemorySocket(raw_http)
    response = http.client.HTTPResponse(cast(socket.socket, memory_socket))
    response.begin()
    expected_length = response.length
    body = response.read(max_bytes + 1)
    _validate_framing(body, expected_length, memory_socket, max_bytes)
    return HttpResponseBytes(status=response.status, body=body)


def _validate_framing(body, expected_length, memory_socket, max_bytes):
    if len(body) > max_bytes:
        raise ValueError("HTTP entity exceeds response ceiling")
    if expected_length is not None and expected_length != len(body):
        raise ValueError("HTTP entity length differs from response framing")
    if memory_socket.trailing_bytes():
        raise ValueError("HTTP response has trailing bytes after its framed entity")


def normalize_response(http_response: HttpResponseBytes, model_name: str) -> dict[str, Any]:
    """Map one Ollama completion conservatively into the T53 provider result shape."""
    try:
        raw_text = http_response.body.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return _invalid_utf8_response(http_response.body)
    if http_response.status != 200:
        return _error_response(raw_text, f"HTTP {http_response.status}")
    try:
        parsed = OllamaChatResponse.model_validate_json(http_response.body)
    except Exception as exc:
        return _error_response(raw_text, f"invalid Ollama completion: {type(exc).__name__}")
    return _normalize_parsed(parsed, model_name, raw_text)


def _normalize_parsed(parsed, model_name, raw_text):
    if parsed.model != model_name:
        return _error_response(raw_text, "Ollama response model identity mismatch")
    return {
        "status": "completed" if parsed.done else "incomplete",
        "finish_reason": parsed.done_reason or ("stop" if parsed.done else None),
        "output_text": parsed.message.content,
        "raw_response": raw_text,
        "usage": _usage(parsed),
    }


def _invalid_utf8_response(body: bytes) -> dict[str, Any]:
    return {
        "status": "error",
        "finish_reason": "invalid UTF-8 response body",
        "output_text": "",
        "raw_response": None,
        "raw_response_base64": base64.b64encode(body).decode("ascii"),
        "usage": None,
    }


def _usage(parsed: OllamaChatResponse) -> dict[str, int] | None:
    if parsed.prompt_eval_count is None or parsed.eval_count is None:
        return None
    return {"input_tokens": parsed.prompt_eval_count, "output_tokens": parsed.eval_count}


def _error_response(raw_text: str, reason: str) -> dict[str, Any]:
    return {
        "status": "error",
        "finish_reason": reason,
        "output_text": "",
        "raw_response": raw_text,
        "usage": None,
    }
