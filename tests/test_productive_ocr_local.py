"""Process/HTTP tests use a small owned fake executable, never a model server."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import threading
from pathlib import Path

import pytest

from congressional_globe.productive_ocr_local import (
    LocalTransportReceipt,
    OwnedLocalClient,
    OwnedLocalError,
    OwnedLocalPlan,
    read_spool,
)

TEST_PYTHON = shutil.which("python3", path=f"/opt/homebrew/bin{os.pathsep}{os.defpath}")
assert TEST_PYTHON is not None
SERVER = (
    "#!"
    + str(TEST_PYTHON)
    + """
import json
import os
import socket

host, port = os.environ["OLLAMA_HOST"].split(":")
server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((host, int(port)))
server.listen(8)
while True:
    conn, _ = server.accept()
    with conn:
        request = b""
        while b"\\r\\n\\r\\n" not in request:
            part = conn.recv(4096)
            if not part:
                break
            request += part
        head, _, body = request.partition(b"\\r\\n\\r\\n")
        headers = head.decode().split("\\r\\n")
        length = 0
        if headers[0].startswith("POST"):
            length_header = next(
                line for line in headers if line.lower().startswith("content-length:")
            )
            length = int(length_header.split(":", 1)[1])
        while len(body) < length:
            body += conn.recv(4096)
        with open(os.path.join(os.environ["HOME"], "requests.log"), "a") as log:
            log.write(headers[0].split()[0] + "\\n")
        if headers[0].startswith("GET"):
            status, payload = 200, b'{"version":"fake"}'
        elif json.loads(body).get("prompt") == "hang":
            import time
            time.sleep(20)
            status, payload = 200, b"{}"
        elif json.loads(body).get("prompt") == "http-error":
            status, payload = 503, b'{"error":"expected fake error"}'
        else:
            status = 200
            result = {
                "model": "fake:latest", "done": True, "done_reason": "stop",
                "message": {"role": "assistant", "content": "fixture"},
                "prompt_eval_count": 3, "eval_count": 2,
            }
            payload = json.dumps(result).encode()
        reason = "OK" if status == 200 else "Unavailable"
        header = (
            "HTTP/1.1 %d %s\\r\\nContent-Length: %d\\r\\n"
            "Connection: close\\r\\n\\r\\n" % (status, reason, len(payload))
        ).encode()
        conn.sendall(header + payload)
"""
)


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _fixture(tmp_path: Path, *, request_timeout: float = 8) -> tuple[OwnedLocalPlan, Path]:
    exe = tmp_path / "fake-ollama"
    exe.write_text(SERVER)
    exe.chmod(0o700)
    model_store = tmp_path / "models"
    (model_store / "fake").mkdir(parents=True, mode=0o700)
    (model_store / "blobs").mkdir(mode=0o700)
    blob = b"synthetic model bytes; not weights and never loaded"
    digest = hashlib.sha256(blob).hexdigest()
    blob_path = model_store / "blobs" / f"sha256-{digest}"
    blob_path.write_bytes(blob)
    blob_path.chmod(0o600)
    manifest = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.ollama.image.model",
        "config": {
            "mediaType": "application/vnd.ollama.image.config",
            "digest": f"sha256:{digest}",
            "size": len(blob),
        },
        "layers": [
            {
                "mediaType": "application/vnd.ollama.image.model",
                "digest": f"sha256:{digest}",
                "size": len(blob),
            }
        ],
    }
    manifest_path = model_store / "fake" / "latest"
    manifest_bytes = json.dumps(manifest, separators=(",", ":")).encode()
    manifest_path.write_bytes(manifest_bytes)
    manifest_path.chmod(0o600)
    model_store.chmod(0o700)
    plan = OwnedLocalPlan(
        executable=str(exe),
        executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
        argv=(str(exe), "serve"),
        port=_port(),
        model_store=str(model_store),
        model_manifest=str(manifest_path),
        model_name="fake:latest",
        model_digest=hashlib.sha256(manifest_bytes).hexdigest(),
        startup_timeout_seconds=5,
        connect_timeout_seconds=2,
        request_timeout_seconds=request_timeout,
        stop_grace_seconds=0.5,
    )
    spool = tmp_path / "spool"
    return plan, spool


def _body(marker: str = "ok") -> bytes:
    return json.dumps({"model": "fake:latest", "prompt": marker}, separators=(",", ":")).encode()


def test_owned_fake_server_spools_raw_http_then_stops(tmp_path: Path) -> None:
    plan, spool = _fixture(tmp_path)
    body = _body()
    call = OwnedLocalClient(plan, spool).start(body)
    response = call.result(6)
    assert response["output_text"] == "fixture"
    assert response["usage"] == {"input_tokens": 3, "output_tokens": 2}
    assert response["owned_local"]["stop_observation"] == "stopped"
    assert call.observe() == "stopped"
    recovered = read_spool(
        spool, hashlib.sha256(body).hexdigest(), "fake:latest", plan.model_digest
    )
    assert recovered is not None
    assert recovered.response["raw_response"] == response["raw_response"]
    assert (Path(recovered.spool_directory) / "request.bin").read_bytes() == body
    assert (
        (Path(recovered.spool_directory) / "response.http").read_bytes().startswith(b"HTTP/1.1 200")
    )
    receipt = json.loads((Path(recovered.spool_directory) / "receipt.json").read_bytes())
    assert receipt["known_processes"][0]["command"]
    altered = {**receipt, "elapsed_seconds": receipt["elapsed_seconds"] + 1}
    with pytest.raises(ValueError, match="elapsed time disagrees"):
        LocalTransportReceipt.model_validate(altered)


def test_non_success_http_is_preserved_as_raw_error(tmp_path: Path) -> None:
    plan, spool = _fixture(tmp_path)
    response = OwnedLocalClient(plan, spool).start(_body("http-error")).result(6)
    assert response["status"] == "error"
    assert "expected fake error" in response["raw_response"]
    assert response["usage"] is None


def test_before_send_rechecks_and_cleans_server_without_post(tmp_path: Path) -> None:
    plan, spool = _fixture(tmp_path)

    def reject_stale_runtime_proof() -> None:
        raise RuntimeError("runtime observation expired")

    client = OwnedLocalClient(plan, spool, before_send=reject_stale_runtime_proof)
    with pytest.raises(OwnedLocalError, match="could not start"):
        client.start(_body())
    request_log = next(spool.glob("*/home/requests.log")).read_text().splitlines()
    assert request_log == ["GET"]


def test_cancelled_delayed_worker_cannot_send_later_post(tmp_path: Path, monkeypatch) -> None:
    from congressional_globe import productive_ocr_local as local_module

    plan, spool = _fixture(tmp_path)
    plan = plan.model_copy(update={"connect_timeout_seconds": 0.2})
    original_exchange = local_module.exchange
    post_entered = threading.Event()
    release_worker = threading.Event()
    post_finished = threading.Event()
    monkeypatch.setattr(
        local_module,
        "exchange",
        _delayed_post_exchange(original_exchange, post_entered, release_worker, post_finished),
    )
    _assert_cancel_blocks_late_post(plan, spool, post_entered, release_worker, post_finished)


def _delayed_post_exchange(original, entered, release, finished):
    def delayed(
        host,
        port,
        method,
        path,
        body,
        timeout,
        sent=None,
        cancelled=None,
        max_bytes=32 * 1024 * 1024,
        send_lock=None,
    ):
        if method != "POST":
            return original(
                host, port, method, path, body, timeout, sent, cancelled, max_bytes, send_lock
            )
        entered.set()
        release.wait(5)
        try:
            return original(
                host, port, method, path, body, timeout, sent, cancelled, max_bytes, send_lock
            )
        finally:
            finished.set()

    return delayed


def _assert_cancel_blocks_late_post(plan, spool, entered, release, finished):
    errors = []

    def start_request() -> None:
        try:
            OwnedLocalClient(plan, spool).start(_body())
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=start_request)
    worker.start()
    assert entered.wait(5)
    worker.join(5)
    assert not worker.is_alive()
    assert errors and isinstance(errors[0], OwnedLocalError)
    release.set()
    assert finished.wait(5)
    request_log = next(spool.glob("*/home/requests.log")).read_text().splitlines()
    assert request_log == ["GET"]


def test_occupied_unowned_port_is_rejected_without_touching_listener(tmp_path: Path) -> None:
    plan, spool = _fixture(tmp_path)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", plan.port))
        listener.listen()
        with pytest.raises(ValueError, match="already occupied"):
            OwnedLocalClient(plan, spool).start(_body())
        assert listener.fileno() >= 0


def test_plan_rejects_shell_or_non_loopback_execution(tmp_path: Path) -> None:
    plan, _ = _fixture(tmp_path)
    with pytest.raises(ValueError):
        OwnedLocalPlan.model_validate(
            {**plan.model_dump(), "argv": (plan.executable, "serve; touch x")}
        )
    with pytest.raises(ValueError):
        OwnedLocalPlan.model_validate({**plan.model_dump(), "host": "0.0.0.0"})


def test_client_revalidates_copied_plan_updates(tmp_path: Path) -> None:
    plan, spool = _fixture(tmp_path)
    forged = plan.model_copy(update={"request_timeout_seconds": float("nan")})
    with pytest.raises(ValueError):
        OwnedLocalClient(forged, spool)


def test_missing_usage_stays_unknown(tmp_path: Path) -> None:
    plan, _ = _fixture(tmp_path)
    # The fake's successful completion fixture has usage, so this contract is checked through
    # the shared normalizer with a valid response that omits both counts.
    from congressional_globe.productive_ocr_http import HttpResponseBytes, normalize_response

    payload = json.dumps(
        {"model": "fake:latest", "done": True, "message": {"role": "assistant", "content": "x"}}
    ).encode()
    assert (
        normalize_response(HttpResponseBytes(status=200, body=payload), plan.model_name)["usage"]
        is None
    )


def test_http_parser_preserves_body_and_rejects_truncated_entity() -> None:
    from congressional_globe.productive_ocr_http import parse_response

    wire = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}"
    assert parse_response(wire).body == b"{}"
    truncated = b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\nConnection: close\r\n\r\n{}"
    with pytest.raises(ValueError, match="length differs"):
        parse_response(truncated)
    surplus = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}EVIL"
    with pytest.raises(ValueError, match="trailing bytes"):
        parse_response(surplus)


def test_invalid_utf8_response_preserves_original_body_bytes() -> None:
    import base64

    from congressional_globe.productive_ocr_http import HttpResponseBytes, normalize_response

    body = b'{"message":"\xff"}'
    result = normalize_response(HttpResponseBytes(status=200, body=body), "fake:latest")
    assert result["status"] == "error"
    assert result["finish_reason"] == "invalid UTF-8 response body"
    assert result["raw_response"] is None
    assert base64.b64decode(result["raw_response_base64"]) == body
