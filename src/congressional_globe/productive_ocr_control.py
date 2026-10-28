"""Separate durable stop observations after raw replies; absent proof blocks reuse."""

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import Field

from congressional_globe.bracket_cues import Contract
from congressional_globe.scan_models import Sha256


class StopObservation(Contract):
    attempt_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    window_id: str = Field(min_length=1)
    body_sha256: Sha256
    response_sha256: Sha256
    state: Literal["stopped", "running", "unknown"]
    cancellation_requested: bool
    within_deadline: bool


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def write_observation(directory: Path, record: StopObservation) -> None:
    path = directory / f"owned-stop-{record.attempt_id}.json"
    value = record.model_dump(mode="json")
    with path.open("x") as stream:
        json.dump({"sha256": _digest(value), "record": value}, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())


def read_observation(directory: Path, attempt: str, job, response: dict) -> StopObservation:
    path = directory / f"owned-stop-{attempt}.json"
    if not path.exists():
        raise ValueError(
            "raw reply saved but owned stop observation missing; reconcile before reuse"
        )
    value = json.loads(path.read_text())
    if _digest(value["record"]) != value["sha256"]:
        raise ValueError("owned stop observation fingerprint mismatch")
    record = StopObservation.model_validate_json(json.dumps(value["record"]))
    expected = (attempt, job.window_id, job.body_sha256, _digest(response))
    actual = (record.attempt_id, record.window_id, record.body_sha256, record.response_sha256)
    if actual != expected:
        raise ValueError("owned stop observation does not bind saved raw reply/request")
    return record


def observe_returned(
    attempt, job, response, owned, deadline: float, clock: Callable[[], float]
) -> StopObservation:
    state = _observe(owned)
    cancelled = state != "stopped"
    if cancelled:
        state = cancel_observe(owned)
    return StopObservation(
        attempt_id=attempt,
        window_id=job.window_id,
        body_sha256=job.body_sha256,
        response_sha256=_digest(response),
        state=state,
        cancellation_requested=cancelled,
        within_deadline=clock() <= deadline,
    )


def _observe(owned) -> Literal["stopped", "running", "unknown"]:
    try:
        state = owned.observe()
        if state in {"stopped", "running", "unknown"}:
            return state
    except Exception:
        pass
    return "unknown"


def cancel_observe(owned) -> Literal["stopped", "running", "unknown"]:
    try:
        owned.cancel()
    except Exception:
        return "unknown"
    return _observe(owned)


def safe_stop(record: StopObservation) -> bool:
    return (
        record.state == "stopped" and record.within_deadline and not record.cancellation_requested
    )
