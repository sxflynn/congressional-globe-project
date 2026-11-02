"""Owned, per-request local Ollama process supervision for productive OCR."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
from congressional_globe.productive_ocr_http import (
    HttpExchangeFailure,
    exchange,
    normalize_response,
    parse_response,
)

MAX_BODY_BYTES = 24 * 1024 * 1024
MAX_MODEL_PARTS = 64
PINNED_MODEL_MANIFEST_SHA256 = "5642e97495e1a088883805981563dcdc4a040c2f53388b7a41d1f24d3622cf7e"
PINNED_MODEL_PARTS = 1209


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always"
    )


class ManifestPart(StrictModel):
    mediaType: str = Field(min_length=1)
    digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    size: int = Field(ge=0)
    name: str | None = None


class ModelManifest(StrictModel):
    model_config = ConfigDict(extra="allow", strict=True, frozen=True)
    schemaVersion: int = Field(ge=1)
    mediaType: str = Field(min_length=1)
    config: ManifestPart
    layers: list[ManifestPart] = Field(min_length=1)


class OwnedLocalPlan(StrictModel):
    executable: str = Field(min_length=1)
    executable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    argv: tuple[str, str]
    host: Literal["127.0.0.1"] = "127.0.0.1"
    port: int = Field(ge=49152, le=65535)
    model_store: str = Field(min_length=1)
    model_manifest: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    startup_timeout_seconds: float = Field(default=20.0, gt=0, le=45)
    connect_timeout_seconds: float = Field(default=4.0, gt=0, le=8)
    request_timeout_seconds: float = Field(default=120.0, gt=0, le=120)
    stop_grace_seconds: float = Field(default=1.0, gt=0, le=3)
    session_deadline_epoch: float | None = Field(default=None, gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def fixed_private_server(self) -> OwnedLocalPlan:
        _validate_plan_paths(self)
        _validate_model_tag_path(self)
        return self


def _validate_plan_paths(plan: OwnedLocalPlan) -> None:
    if not Path(plan.executable).is_absolute() or plan.argv != (plan.executable, "serve"):
        raise ValueError("server argv must be the exact executable followed by serve")
    store, manifest = Path(plan.model_store), Path(plan.model_manifest)
    if not store.is_absolute() or not manifest.is_absolute():
        raise ValueError("model store and manifest paths must be absolute")
    if not manifest.is_relative_to(store):
        raise ValueError("model manifest must be inside the selected model store")


def _validate_model_tag_path(plan: OwnedLocalPlan) -> None:
    tag = plan.model_name.split(":", maxsplit=1)
    manifest = Path(plan.model_manifest)
    if len(tag) != 2 or manifest.name != tag[1] or manifest.parent.name != tag[0]:
        raise ValueError("model tag must name the selected manifest path")


class OwnedProcessIdentity(StrictModel):
    pid: int = Field(gt=0)
    ppid: int = Field(ge=0)
    pgid: int = Field(gt=0)
    started: str = Field(min_length=1)
    command: str = Field(min_length=1, max_length=4096)


class LocalTransportReceipt(StrictModel):
    contract: Literal["productive-ocr-owned-local-receipt-v1"] = (
        "productive-ocr-owned-local-receipt-v1"
    )
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_name: str = Field(min_length=1)
    model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_http_sha256: str | None = Field(pattern=r"^[0-9a-f]{64}$")
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)
    started_at_epoch: float = Field(gt=0, allow_inf_nan=False)
    ended_at_epoch: float = Field(gt=0, allow_inf_nan=False)
    started_monotonic: float = Field(gt=0, allow_inf_nan=False)
    ended_monotonic: float = Field(gt=0, allow_inf_nan=False)
    owned_pid: int = Field(gt=0)
    owned_pgid: int = Field(gt=0)
    owned_process_start: str = Field(min_length=1)
    owned_executable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    known_processes: list[OwnedProcessIdentity] = Field(max_length=128)
    stop_observation: Literal["stopped", "running", "unknown"]
    complete_http_response: bool

    @model_validator(mode="after")
    def consistent_timing(self) -> LocalTransportReceipt:
        if (
            self.ended_at_epoch < self.started_at_epoch
            or self.ended_monotonic < self.started_monotonic
        ):
            raise ValueError("transport receipt end precedes start")
        if abs(self.elapsed_seconds - (self.ended_monotonic - self.started_monotonic)) > 0.001:
            raise ValueError("transport receipt elapsed time disagrees with monotonic bounds")
        return self


class RecoveredSpool(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    response: dict[str, Any]
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)
    stop_observation: Literal["stopped", "running", "unknown"]
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    spool_directory: str = Field(min_length=1)


class LocalTransportIntent(StrictModel):
    contract: Literal["productive-ocr-owned-local-intent-v1"]
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_name: str = Field(min_length=1)
    model_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class _ProcessRow:
    pid: int
    ppid: int
    pgid: int
    started: str
    command: str


class OwnedLocalError(RuntimeError):
    def __init__(self, message: str, observation: str = "unknown") -> None:
        super().__init__(message)
        self.owned_stop_observation = observation


StopObservation = Literal["stopped", "running", "unknown"]


class OwnedLocalClient:
    """Starts a fresh private server for every request; never attaches to shared Ollama."""

    offline_test_double = False

    def __init__(
        self,
        plan: OwnedLocalPlan,
        spool_dir: Path,
        before_send: Callable[[], None] | None = None,
    ) -> None:
        from congressional_globe.productive_ocr_long_audit import validate_diagnostic_plan

        self.plan = validate_diagnostic_plan(plan)
        self.spool_dir = spool_dir
        self.before_send = before_send

    def start(self, body: bytes) -> OwnedLocalCall:
        started_epoch, started_monotonic = time.time(), time.monotonic()
        deadline = _job_deadline(self.plan, started_epoch, started_monotonic)
        _validate_launch_inputs(self.plan, self.spool_dir, body, deadline)
        _require_request_budget(deadline, self.plan.stop_grace_seconds)
        call_dir = _new_spool_dir(self.spool_dir)
        request_hash = sha256_bytes(body)
        _write_synced(call_dir / "request.bin", body)
        _write_synced(
            call_dir / "intent.json",
            canonical_json(
                {
                    "contract": "productive-ocr-owned-local-intent-v1",
                    "request_sha256": request_hash,
                    "model_name": self.plan.model_name,
                    "model_digest": self.plan.model_digest,
                }
            ),
        )
        process, root_identity = _spawn_server(self.plan, call_dir)
        call = OwnedLocalCall(
            self.plan,
            process,
            call_dir,
            body,
            request_hash,
            root_identity,
            started_epoch,
            started_monotonic,
            deadline,
            self.before_send,
        )
        try:
            _start_http_call(self.plan, process, call)
            return call
        except Exception as exc:
            observation = call.cancel_and_observe()
            _write_failure_receipt(call, observation)
            if isinstance(exc, OwnedLocalError):
                raise OwnedLocalError(str(exc), observation) from exc
            raise OwnedLocalError("owned local request could not start", observation) from exc


def _start_http_call(plan: OwnedLocalPlan, process: subprocess.Popen, call: OwnedLocalCall) -> None:
    _wait_for_health(plan, process, call)
    _require_request_budget(call.deadline_monotonic, plan.stop_grace_seconds)
    if call.before_send is not None:
        call.before_send()
    call._begin()
    if not call._sent_or_failed.wait(plan.connect_timeout_seconds + 1):
        raise OwnedLocalError("owned HTTP send observation timed out")
    if call._start_error is not None and not call._body_sent:
        raise OwnedLocalError("owned HTTP request was not sent", call.cancel_and_observe())


def read_spool(
    spool_dir: Path, request_sha256: str, model_name: str, model_digest: str
) -> RecoveredSpool | None:
    """Recover exactly one complete hash-bound raw response; ambiguity stays unknown."""
    if not re.fullmatch(r"[0-9a-f]{64}", request_sha256):
        raise ValueError("invalid spool request hash")
    if not spool_dir.is_dir() or spool_dir.is_symlink():
        raise ValueError("private spool directory is unavailable")
    matches = _matching_spools(spool_dir, request_sha256)
    if not matches:
        return None
    if len(matches) != 1:
        raise OwnedLocalError("multiple matching local response spools are ambiguous")
    return _read_complete_spool(matches[0], request_sha256, model_name, model_digest)


def _matching_spools(spool_dir: Path, request_sha256: str) -> list[Path]:
    directories = sorted(spool_dir.iterdir())
    if len(directories) > 128:
        raise OwnedLocalError("local spool search exceeded inspection ceiling")
    return [path for path in directories if _directory_matches(path, request_sha256)]


def _directory_matches(directory: Path, request_sha256: str) -> bool:
    if not directory.is_dir() or directory.is_symlink():
        return False
    request = directory / "request.bin"
    return request.is_file() and _sha_file(request) == request_sha256


def _read_complete_spool(
    directory: Path, request_hash: str, model_name: str, model_digest: str
) -> RecoveredSpool:
    receipt_path, receipt_hash_path = directory / "receipt.json", directory / "receipt.sha256"
    response_path = directory / "response.http"
    if not receipt_path.is_file() or not receipt_hash_path.is_file() or not response_path.is_file():
        raise OwnedLocalError("matching local spool has no complete durable receipt")
    receipt_bytes = receipt_path.read_bytes()
    receipt_hash = sha256_bytes(receipt_bytes)
    if receipt_hash_path.read_text().strip() != receipt_hash:
        raise OwnedLocalError("local spool receipt hash mismatch")
    try:
        receipt = LocalTransportReceipt.model_validate_json(receipt_bytes)
    except Exception as exc:
        raise OwnedLocalError("local spool receipt is invalid") from exc
    request_bytes = (directory / "request.bin").read_bytes()
    raw_http = response_path.read_bytes()
    _check_spool_binding(
        directory, receipt, request_hash, model_name, model_digest, request_bytes, raw_http
    )
    parsed = parse_response(raw_http)
    response = normalize_response(parsed, model_name)
    response["owned_local"] = {
        "spool_directory": str(directory),
        "request_sha256": request_hash,
        "model_name": model_name,
        "model_digest": model_digest,
        "receipt_sha256": receipt_hash,
        "raw_http_sha256": receipt.response_http_sha256,
        "stop_observation": receipt.stop_observation,
        "owned_pid": receipt.owned_pid,
        "owned_pgid": receipt.owned_pgid,
    }
    return RecoveredSpool(
        response=response,
        elapsed_seconds=receipt.elapsed_seconds,
        stop_observation=receipt.stop_observation,
        receipt_sha256=receipt_hash,
        spool_directory=str(directory),
    )


def _check_spool_binding(
    directory: Path,
    receipt: LocalTransportReceipt,
    request_hash: str,
    model_name: str,
    model_digest: str,
    request_bytes: bytes,
    raw_http: bytes,
) -> None:
    _verify_receipt_claims(receipt, request_hash, model_name, model_digest, raw_http)
    intent = _load_intent(directory, request_bytes)
    _verify_intent_claims(intent, request_hash, model_name, model_digest)


def _verify_receipt_claims(
    receipt: LocalTransportReceipt,
    request_hash: str,
    model_name: str,
    model_digest: str,
    raw_http: bytes,
) -> None:
    if not receipt.complete_http_response or receipt.stop_observation == "running":
        raise OwnedLocalError("local spool has incomplete response or stop proof")
    expected = (request_hash, model_name, model_digest, sha256_bytes(raw_http))
    actual = (
        receipt.request_sha256,
        receipt.model_name,
        receipt.model_digest,
        receipt.response_http_sha256,
    )
    if actual != expected:
        raise OwnedLocalError("local spool response/request/model identity mismatch")


def _load_intent(directory: Path, request_bytes: bytes) -> LocalTransportIntent:
    try:
        intent = LocalTransportIntent.model_validate_json((directory / "intent.json").read_bytes())
        request = json.loads(request_bytes)
    except Exception as exc:
        raise OwnedLocalError("local spool intent or request body is invalid") from exc
    if not isinstance(request, dict) or request.get("model") != intent.model_name:
        raise OwnedLocalError("local spool request model does not match intent")
    return intent


def _verify_intent_claims(
    intent: LocalTransportIntent, request_hash: str, model_name: str, model_digest: str
) -> None:
    if (intent.request_sha256, intent.model_name, intent.model_digest) != (
        request_hash,
        model_name,
        model_digest,
    ):
        raise OwnedLocalError("local spool intent/model does not match exact request")


class OwnedLocalCall:
    """One HTTP request owned by one process group and one durable spool directory."""

    def __init__(
        self,
        plan: OwnedLocalPlan,
        process: subprocess.Popen,
        spool: Path,
        body: bytes,
        request_hash: str,
        root_identity: _ProcessRow,
        started_epoch: float,
        started_monotonic: float,
        deadline_monotonic: float,
        before_send: Callable[[], None] | None = None,
    ) -> None:
        self.plan = plan
        self.process = process
        self.spool = spool
        self.body = body
        self.request_hash = request_hash
        self.pid = process.pid
        self.pgid = process.pid
        self.process_started = root_identity.started
        self.started_epoch = started_epoch
        self.started_monotonic = started_monotonic
        self.deadline_monotonic = deadline_monotonic
        self.before_send = before_send
        self._sent_or_failed = threading.Event()
        self._body_sent = False
        self._start_error: Exception | None = None
        self._done = threading.Event()
        self._cancelled = threading.Event()
        self._send_lock = threading.Lock()
        self._lock = threading.RLock()
        self._worker: threading.Thread | None = None
        self._response: dict[str, Any] | None = None
        self._error: Exception | None = None
        self._last_raw = b""
        self._last_complete = False
        self._owned_processes: dict[int, _ProcessRow] = {self.pid: root_identity}
        self._observation_unknown = False

    def _begin(self) -> None:
        watcher = threading.Thread(target=self._watch_process, name="owned-ocr-watch", daemon=True)
        watcher.start()
        self._worker = threading.Thread(
            target=self._run_request, name="owned-ocr-http", daemon=True
        )
        self._worker.start()

    def _watch_process(self) -> None:
        while not self._done.wait(0.1):
            if self.observe() == "unknown":
                self._observation_unknown = True

    def _run_request(self) -> None:
        try:
            self._run_complete_request()
        except Exception as exc:
            self._record_request_failure(exc, self._last_raw, self._last_complete)
        finally:
            self._done.set()

    def _run_complete_request(self) -> None:
        budget = self.deadline_monotonic - 2 * self.plan.stop_grace_seconds - time.monotonic()
        if budget <= 0:
            raise TimeoutError("no request time remains before owned-stop reserve")
        raw = exchange(
            self.plan.host,
            self.plan.port,
            "POST",
            "/api/chat",
            self.body,
            budget,
            self._sent_or_failed,
            self._cancelled,
            send_lock=self._send_lock,
        )
        self._last_raw = raw
        self._last_complete = True
        _write_synced(self.spool / "response.http", raw)
        normalized = normalize_response(parse_response(raw), self.plan.model_name)
        observation = self._stop_backend()
        receipt_hash = _write_receipt(self, raw, observation, True)
        normalized["owned_local"] = _transport_metadata(self, receipt_hash, observation)
        self._response = normalized

    def _record_request_failure(self, exc: Exception, raw: bytes, complete: bool) -> None:
        self._error = exc
        self._start_error = exc
        self._sent_or_failed.set()
        partial = getattr(exc, "partial", b"")
        self._body_sent = bool(getattr(exc, "body_sent", self._body_sent))
        raw = partial or raw
        _spool_partial_response(self.spool, raw)
        observation = self._stop_backend()
        _write_failure_receipt(self, observation, raw, complete=complete)

    def result(self, timeout: float) -> dict[str, Any]:
        remaining = min(timeout, self.deadline_monotonic - time.monotonic())
        if remaining <= 0 or not self._done.wait(remaining):
            raise TimeoutError("owned local HTTP request exceeded caller deadline")
        if self._error is not None:
            raise OwnedLocalError("owned local HTTP request failed", self.observe()) from (
                self._error
            )
        if self._response is None:
            raise OwnedLocalError("owned local request has no normalized response", self.observe())
        return self._response

    def cancel(self) -> None:
        with self._send_lock:
            self._cancelled.set()
        self._stop_backend()
        if self._worker is not None:
            self._worker.join(timeout=self.plan.stop_grace_seconds + 1)

    def observe(self) -> Literal["stopped", "running", "unknown"]:
        return "unknown" if self._observation_unknown else _observe_owned(self)

    def cancel_and_observe(self) -> Literal["stopped", "running", "unknown"]:
        self.cancel()
        return self.observe()

    def _stop_backend(self) -> Literal["stopped", "running", "unknown"]:
        with self._lock:
            return _stop_group(self)


def _spool_partial_response(spool: Path, raw: bytes) -> None:
    if raw and not (spool / "response.http").exists():
        _write_synced(spool / "response.http.partial", raw)


def _validate_launch_inputs(
    plan: OwnedLocalPlan, spool: Path, body: bytes, deadline: float | None = None
) -> None:
    if not body or len(body) > MAX_BODY_BYTES:
        raise ValueError("frozen request body is empty or too large")
    request = json.loads(body)
    if not isinstance(request, dict) or request.get("model") != plan.model_name:
        raise ValueError("frozen request model differs from selected local model")
    _verify_executable(plan, deadline)
    _verify_model_store(plan, deadline)
    _assert_port_free(plan.host, plan.port)
    _ensure_private_directory(spool)


def _job_deadline(plan: OwnedLocalPlan, started_epoch: float, started_monotonic: float) -> float:
    budget = plan.request_timeout_seconds
    if plan.session_deadline_epoch is not None:
        budget = min(budget, plan.session_deadline_epoch - started_epoch)
    deadline = started_monotonic + budget
    if budget <= 2 * plan.stop_grace_seconds:
        raise TimeoutError("insufficient bounded time for local request and owned stop")
    return deadline


def _require_request_budget(deadline: float, stop_grace: float) -> float:
    remaining = deadline - time.monotonic() - 2 * stop_grace
    if remaining <= 0:
        raise TimeoutError("no local request budget remains after reserving backend stop")
    return remaining


def _verify_executable(plan: OwnedLocalPlan, deadline: float | None = None) -> None:
    path = Path(plan.executable)
    if (
        path.is_symlink()
        or not path.is_file()
        or _sha_file(path, deadline) != plan.executable_sha256
    ):
        raise ValueError("selected server executable identity changed")
    if path.stat().st_mode & 0o022:
        raise ValueError("selected server executable is group/world writable")


def _verify_model_store(plan: OwnedLocalPlan, deadline: float | None = None) -> None:
    root, manifest_path = Path(plan.model_store), Path(plan.model_manifest)
    _verify_readonly_model_store(root)
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("selected model manifest is missing or symlinked")
    if _sha_file(manifest_path, deadline) != plan.model_digest:
        raise ValueError("selected model manifest digest mismatch")
    try:
        manifest = _parse_model_manifest(manifest_path.read_bytes())
    except Exception as exc:
        raise ValueError("selected model manifest is invalid") from exc
    for part in (manifest.config, *manifest.layers):
        _verify_blob(root, part, deadline)


def _parse_model_manifest(raw: bytes) -> ModelManifest:
    digest = hashlib.sha256(raw).hexdigest()
    limit = PINNED_MODEL_PARTS if digest == PINNED_MODEL_MANIFEST_SHA256 else MAX_MODEL_PARTS
    manifest = ModelManifest.model_validate_json(raw)
    if len(manifest.layers) > limit:
        raise ValueError("selected model manifest has too many layers")
    return manifest


def _verify_blob(root: Path, part: ManifestPart, deadline: float | None = None) -> None:
    digest = part.digest.removeprefix("sha256:")
    path = root / "blobs" / f"sha256-{digest}"
    if path.is_symlink() or not path.is_file() or path.stat().st_size != part.size:
        raise ValueError("selected model blob is missing or differs from manifest size")
    if _sha_file(path, deadline) != digest:
        raise ValueError("selected model blob hash differs from manifest digest")


def _assert_port_free(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        result = probe.connect_ex((host, port))
    if result == 0:
        raise ValueError("selected loopback port is already occupied")
    if result not in {errno.ECONNREFUSED, errno.ECONNRESET, errno.EHOSTUNREACH}:
        raise ValueError("selected loopback port availability is unknown")


def _verify_readonly_model_store(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise ValueError("selected model store must be an existing directory")
    info = path.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise ValueError("selected model store owner or write permissions are unsafe")


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise ValueError("private directory path is not a directory")
    info = path.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("private directory must be owned by caller with mode 0700")
    path.chmod(0o700)


def _new_spool_dir(base: Path) -> Path:
    _ensure_private_directory(base)
    call = base / uuid.uuid4().hex
    call.mkdir(mode=0o700)
    return call


def _spawn_server(plan: OwnedLocalPlan, spool: Path) -> tuple[subprocess.Popen, _ProcessRow]:
    home = spool / "home"
    home.mkdir(mode=0o700)
    env = {
        "PATH": os.defpath,
        "HOME": str(home),
        "OLLAMA_HOST": f"{plan.host}:{plan.port}",
        "OLLAMA_MODELS": plan.model_store,
    }
    process = subprocess.Popen(
        plan.argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        close_fds=True,
        start_new_session=True,
        shell=False,
    )
    try:
        if os.getpgid(process.pid) != process.pid:
            raise ValueError("spawned server is not in its private process group")
        identity = _read_process_row(process.pid)
        if identity is None or identity.pgid != process.pid:
            raise ValueError("spawned server creation identity is unavailable")
        _write_synced(
            spool / "server.json",
            canonical_json(
                {
                    "owned_pid": process.pid,
                    "owned_pgid": process.pid,
                    "process_started": identity.started,
                    "observed_command": identity.command,
                    "executable_sha256": plan.executable_sha256,
                }
            ),
        )
        return process, identity
    except Exception:
        _terminate_spawn_failure(process)
        raise


def _terminate_spawn_failure(process: subprocess.Popen) -> None:
    try:
        group = os.getpgid(process.pid)
        if group == process.pid:
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        _wait_spawn_failure(process)
    except (OSError, subprocess.SubprocessError):
        pass


def _wait_spawn_failure(process: subprocess.Popen) -> None:
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def _wait_for_health(plan: OwnedLocalPlan, process: subprocess.Popen, call: OwnedLocalCall) -> None:
    deadline = min(
        time.monotonic() + plan.startup_timeout_seconds,
        call.deadline_monotonic - 2 * plan.stop_grace_seconds,
    )
    while time.monotonic() < deadline:
        if _server_ready(plan, process, call):
            return
        time.sleep(0.1)
    raise TimeoutError("owned local server health check did not complete")


def _server_ready(plan: OwnedLocalPlan, process: subprocess.Popen, call: OwnedLocalCall) -> bool:
    if process.poll() is not None:
        raise ValueError("owned local server exited before health check")
    try:
        wire = exchange(plan.host, plan.port, "GET", "/api/version", b"", 0.5)
        response = parse_response(wire, 64 * 1024)
    except (HttpExchangeFailure, OSError, TimeoutError, ValueError):
        return False
    return response.status == 200 and _listener_belongs_to(plan, call)


def _listener_pids(port: int) -> set[int] | None:
    executable = shutil.which("lsof")
    if executable is None:
        return None
    result = _run_lsof(executable, port)
    return _parse_listener_pids(result)


def _run_lsof(executable: str, port: int) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            [executable, "-nP", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _parse_listener_pids(result: subprocess.CompletedProcess[str] | None) -> set[int] | None:
    if result is None:
        return None
    if result.returncode == 1:
        return set()
    if result.returncode != 0:
        return None
    values = _pid_values(result.stdout)
    return values if len(values) <= 128 else None


def _pid_values(output: str) -> set[int]:
    return {int(value) for value in output.split() if value.isdigit()}


def _listener_belongs_to(plan: OwnedLocalPlan, call: OwnedLocalCall) -> bool:
    listeners = _listener_pids(plan.port)
    rows = _owned_tree(call)
    return bool(
        listeners
        and rows is not None
        and listeners <= set(rows)
        and all(rows[pid].pgid == call.pgid for pid in listeners)
    )


def _write_synced(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    _fsync_directory(path.parent)


def _write_receipt(
    call: OwnedLocalCall, raw: bytes, observation: StopObservation, complete: bool
) -> str:
    ended_epoch, ended_monotonic = time.time(), time.monotonic()
    receipt = LocalTransportReceipt(
        request_sha256=call.request_hash,
        model_name=call.plan.model_name,
        model_digest=call.plan.model_digest,
        response_http_sha256=sha256_bytes(raw),
        elapsed_seconds=ended_monotonic - call.started_monotonic,
        started_at_epoch=call.started_epoch,
        ended_at_epoch=ended_epoch,
        started_monotonic=call.started_monotonic,
        ended_monotonic=ended_monotonic,
        owned_pid=call.pid,
        owned_pgid=call.pgid,
        owned_process_start=call.process_started,
        owned_executable_sha256=call.plan.executable_sha256,
        known_processes=_process_records(call),
        stop_observation=observation,
        complete_http_response=complete,
    )
    return _save_receipt(call.spool, receipt)


def _write_failure_receipt(
    call: OwnedLocalCall,
    observation: StopObservation,
    raw: bytes = b"",
    complete: bool = False,
) -> None:
    if (call.spool / "receipt.json").exists():
        return
    ended_epoch, ended_monotonic = time.time(), time.monotonic()
    receipt = LocalTransportReceipt(
        request_sha256=call.request_hash,
        model_name=call.plan.model_name,
        model_digest=call.plan.model_digest,
        response_http_sha256=sha256_bytes(raw) if raw else None,
        elapsed_seconds=ended_monotonic - call.started_monotonic,
        started_at_epoch=call.started_epoch,
        ended_at_epoch=ended_epoch,
        started_monotonic=call.started_monotonic,
        ended_monotonic=ended_monotonic,
        owned_pid=call.pid,
        owned_pgid=call.pgid,
        owned_process_start=call.process_started,
        owned_executable_sha256=call.plan.executable_sha256,
        known_processes=_process_records(call),
        stop_observation=observation,
        complete_http_response=complete,
    )
    _save_receipt(call.spool, receipt)


def _process_records(call: OwnedLocalCall) -> list[OwnedProcessIdentity]:
    return [
        OwnedProcessIdentity(
            pid=row.pid,
            ppid=row.ppid,
            pgid=row.pgid,
            started=row.started,
            command=row.command,
        )
        for row in sorted(call._owned_processes.values(), key=lambda item: item.pid)
    ]


def _save_receipt(spool: Path, receipt: LocalTransportReceipt) -> str:
    data = canonical_json(receipt.model_dump(mode="json"))
    digest = sha256_bytes(data)
    _write_synced(spool / "receipt.json", data)
    _write_synced(spool / "receipt.sha256", digest.encode("ascii"))
    return digest


def _transport_metadata(
    call: OwnedLocalCall, receipt_hash: str, observation: StopObservation
) -> dict:
    return {
        "spool_directory": str(call.spool),
        "request_sha256": call.request_hash,
        "model_name": call.plan.model_name,
        "model_digest": call.plan.model_digest,
        "receipt_sha256": receipt_hash,
        "raw_http_sha256": sha256_bytes(call._last_raw),
        "stop_observation": observation,
        "owned_pid": call.pid,
        "owned_pgid": call.pgid,
    }


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _sha_file(path: Path, deadline: float | None = None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            _check_hash_deadline(deadline)
            digest.update(block)
    _check_hash_deadline(deadline)
    return digest.hexdigest()


def _check_hash_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("local request deadline expired while hashing resources")


def _read_process_row(pid: int) -> _ProcessRow | None:
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "pid=,ppid=,pgid=,lstart=,command="],
        capture_output=True,
        text=True,
        timeout=2,
        check=False,
    )
    if result.returncode == 1:
        return None
    if result.returncode != 0:
        raise OSError("could not inspect owned process identity")
    fields = result.stdout.split()
    if len(fields) < 9:
        raise OSError("owned process identity output is incomplete")
    return _process_row(fields)


def _process_row(fields: list[str]) -> _ProcessRow:
    return _ProcessRow(
        pid=int(fields[0]),
        ppid=int(fields[1]),
        pgid=int(fields[2]),
        started=" ".join(fields[3:8]),
        command=" ".join(fields[8:]),
    )


def _direct_children(pid: int) -> list[int]:
    result = subprocess.run(
        ["pgrep", "-P", str(pid)], capture_output=True, text=True, timeout=2, check=False
    )
    if result.returncode == 1:
        return []
    if result.returncode != 0:
        raise OSError("could not inspect owned descendants")
    children = [int(item) for item in result.stdout.split() if item.isdigit()]
    if len(children) > 128:
        raise OSError("owned process tree exceeds inspection ceiling")
    return children


def _owned_tree(call: OwnedLocalCall) -> dict[int, _ProcessRow] | None:
    rows: dict[int, _ProcessRow] = {}
    pending = list(dict.fromkeys([call.pid, *call._owned_processes.keys()]))
    seen: set[int] = set()
    try:
        while pending:
            pid = pending.pop()
            if not _inspect_process(pid, call, rows, seen, pending):
                return None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    call._owned_processes.update(rows)
    return rows


def _inspect_process(
    pid: int,
    call: OwnedLocalCall,
    rows: dict[int, _ProcessRow],
    seen: set[int],
    pending: list[int],
) -> bool:
    if pid in seen:
        return True
    seen.add(pid)
    if len(seen) > 128:
        return False
    row = _read_process_row(pid)
    if row is None:
        return True
    if _pid_reused(pid, row, call):
        return False
    rows[pid] = row
    pending.extend(_direct_children(pid))
    return True


def _pid_reused(pid: int, row: _ProcessRow, call: OwnedLocalCall) -> bool:
    previous = call._owned_processes.get(pid)
    return previous is not None and previous.started != row.started


def _observe_owned(call: OwnedLocalCall) -> Literal["stopped", "running", "unknown"]:
    rows = _owned_tree(call)
    if rows is None:
        return "unknown"
    if call.process.poll() is None:
        return _observe_live_root(call, rows)
    return _observe_exited_root(call, rows)


def _observe_live_root(
    call: OwnedLocalCall, rows: dict[int, _ProcessRow]
) -> Literal["stopped", "running", "unknown"]:
    root = rows.get(call.pid)
    try:
        live_group = os.getpgid(call.pid)
    except OSError:
        return "unknown"
    if (
        root is None
        or root.started != call.process_started
        or root.pgid != call.pgid
        or live_group != call.pgid
    ):
        return "unknown"
    if any(row.pgid != call.pgid for row in rows.values()):
        return "unknown"
    return "running"


def _observe_exited_root(
    call: OwnedLocalCall, rows: dict[int, _ProcessRow]
) -> Literal["stopped", "running", "unknown"]:
    if not _all_in_owned_group(call, rows):
        return "unknown"
    return _classify_exited_group(call, rows)


def _all_in_owned_group(call: OwnedLocalCall, rows: dict[int, _ProcessRow]) -> bool:
    return all(row.pgid == call.pgid for row in rows.values())


def _classify_exited_group(
    call: OwnedLocalCall, rows: dict[int, _ProcessRow]
) -> Literal["stopped", "running", "unknown"]:
    group_exists = _process_group_exists(call.pgid)
    known_live = any(row.pid != call.pid for row in rows.values())
    if known_live:
        return "running"
    if group_exists:
        return "unknown"
    return "stopped"


def _process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _stop_group(call: OwnedLocalCall) -> Literal["stopped", "running", "unknown"]:
    observation = call.observe()
    if observation == "stopped":
        return observation
    if not _safe_to_signal_group(call):
        return "unknown"
    _signal_group(call, signal.SIGTERM)
    if _wait_for_stop(call, call.plan.stop_grace_seconds) == "stopped":
        return "stopped"
    if not _safe_to_signal_group(call):
        return "unknown"
    _signal_group(call, signal.SIGKILL)
    return _wait_for_stop(call, call.plan.stop_grace_seconds)


def _safe_to_signal_group(call: OwnedLocalCall) -> bool:
    if call.pgid != call.pid:
        return False
    if call.process.poll() is None:
        return _safe_live_root(call)
    rows = _owned_tree(call)
    return rows is not None and _has_owned_live_member(call, rows)


def _safe_live_root(call: OwnedLocalCall) -> bool:
    try:
        row = _read_process_row(call.pid)
        return bool(
            row is not None
            and row.started == call.process_started
            and row.pgid == call.pgid
            and os.getpgid(call.pid) == call.pgid
        )
    except OSError:
        return False


def _has_owned_live_member(call: OwnedLocalCall, rows: dict[int, _ProcessRow]) -> bool:
    for row in rows.values():
        previous = call._owned_processes.get(row.pid, row)
        if row.pgid == call.pgid and previous.started == row.started:
            return True
    return False


def _signal_group(call: OwnedLocalCall, signum: int) -> None:
    if _safe_to_signal_group(call):
        try:
            os.killpg(call.pgid, signum)
        except ProcessLookupError:
            return
        except OSError:
            call._observation_unknown = True


def _wait_for_stop(
    call: OwnedLocalCall, seconds: float
) -> Literal["stopped", "running", "unknown"]:
    deadline = time.monotonic() + seconds
    observation = call.observe()
    while observation == "running" and time.monotonic() < deadline:
        time.sleep(0.05)
        observation = call.observe()
    return observation
