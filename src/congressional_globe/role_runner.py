"""Bounded opt-in role diagnostics with durable attempts and visible progress."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import platform
import re
import subprocess
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from congressional_globe.role_aliases import validate_alias_result
from congressional_globe.role_provider import RoleProvider
from congressional_globe.role_run_io import (
    RunOptions,
    read_prepared,
    reservation,
    run_config,
    write_json,
)
from congressional_globe.role_run_store import RoleRunStore

Caller = Callable[[dict, str, dict], dict]


@contextmanager
def _exclusive(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    with (output / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _event(output: Path, event: str, **fields) -> None:
    record = {"timestamp_utc": datetime.now(UTC).isoformat(), "event": event, **fields}
    line = json.dumps(record, ensure_ascii=False)
    with (output / "events.jsonl").open("a") as stream:
        stream.write(line + "\n")
        stream.flush()
    print(line, flush=True)


def _progress(store: RoleRunStore, started: float) -> dict:
    summary = store.summary()
    statuses = summary["statuses"]
    total = sum(statuses.values())
    completed = total - statuses["pending"] - statuses["inflight"]
    durations = [row["result"].get("elapsed_seconds", 0) for row in store.results()]
    mean = sum(durations) / len(durations) if durations else None
    return {
        **summary,
        "total": total,
        "completed": completed,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "estimated_remaining_seconds": None
        if mean is None
        else round(mean * statuses["pending"], 1),
        "eta_basis": "mean completed request duration; unknown until first result",
    }


def _wait_call(
    caller: Caller,
    packet: dict,
    prompt: str,
    schema: dict,
    output: Path,
    store: RoleRunStore,
    started: float,
) -> dict:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(caller, packet, prompt, schema)
        while not future.done():
            try:
                return future.result(timeout=10)
            except FutureTimeout:
                _event(
                    output,
                    "request_waiting",
                    window_id=packet["window_id"],
                    **_progress(store, started),
                )
        return future.result()


def _parse_result(response: dict, packet: dict) -> tuple[str, dict]:
    if response["status"] != "completed" or response["finish_reason"] == "length":
        return "invalid", {"validation_error": "Provider response incomplete or refused"}
    try:
        parsed = validate_alias_result(json.loads(response["output_text"]), packet)
        return "valid", {"role_proposals": parsed, "validation_scope": "schema/reference only"}
    except ValueError as error:
        return "invalid", {"validation_error": str(error)}


def _attempt(
    caller: Caller,
    packet: dict,
    prompt: str,
    schema: dict,
    output: Path,
    store: RoleRunStore,
    started: float,
) -> tuple[str, dict]:
    tick = time.monotonic()
    try:
        response = _wait_call(caller, packet, prompt, schema, output, store, started)
        status, validation = _parse_result(response, packet)
        result = {**response, **validation}
    except Exception as error:
        status = "unresolved"
        message = re.sub(r"sk-[A-Za-z0-9_-]+", "[redacted]", str(error))[:500]
        result = {
            "error_type": type(error).__name__,
            "error": message,
            "usage": None,
            "outcome": "No usable response; processing/usage unknown. Do not auto-retry.",
        }
    return status, {**result, "elapsed_seconds": round(time.monotonic() - tick, 3)}


def _call_one(
    caller: Caller,
    packet: dict,
    prompt: str,
    schema: dict,
    output: Path,
    store: RoleRunStore,
    started: float,
) -> str:
    attempt_id = store.start(packet["window_id"])
    _event(
        output,
        "request_started",
        window_id=packet["window_id"],
        attempt_id=attempt_id,
        input_text=packet["raw_text"],
        **_progress(store, started),
    )
    status, result = _attempt(caller, packet, prompt, schema, output, store, started)
    store.finish(attempt_id, result, status)
    _event(
        output,
        "request_finished",
        window_id=packet["window_id"],
        attempt_id=attempt_id,
        result_status=status,
        result=result,
        **_progress(store, started),
    )
    return status


def _work(
    options: RunOptions,
    caller: Caller,
    packets: list[dict],
    prompt: str,
    schema: dict,
    config: dict,
) -> dict:
    started = time.monotonic()
    store = RoleRunStore(options.output / "jobs.sqlite", config, packets)
    try:
        return _work_store(options, caller, prompt, schema, store, started)
    finally:
        store.close()


def _work_store(
    options: RunOptions,
    caller: Caller,
    prompt: str,
    schema: dict,
    store: RoleRunStore,
    started: float,
) -> dict:
    _require_no_unknown(store)
    _event(options.output, "worker_started", pid=os.getpid(), **_progress(store, started))
    packet = store.next_pending()
    while packet is not None:
        if time.monotonic() - started + options.timeout > options.max_seconds:
            break
        status = _call_one(caller, packet, prompt, schema, options.output, store, started)
        if status != "valid":
            break
        packet = store.next_pending()
    summary = _summary(store, options.provider)
    write_json(options.output / "summary.json", summary)
    _event(options.output, "worker_stopped", summary=summary, **_progress(store, started))
    return summary


def _require_no_unknown(store: RoleRunStore) -> None:
    counts = store.summary()["statuses"]
    if counts["inflight"] or counts["unresolved"]:
        raise ValueError(
            "Unresolved call exists; inspect terminal worker/server evidence before further work"
        )


def _summary(store: RoleRunStore, provider: str) -> dict:
    results = store.results()
    return {
        **store.summary(),
        "results": results,
        "api_cost_usd_estimate": _cost(results, provider),
        "quality": "Schema/reference validity only; semantic/human review pending",
        "recovery": "No automatic retries; unknown outcomes block resume",
    }


def _cost(results: list[dict], provider: str) -> float | None:
    if provider == "ollama":
        return 0.0
    values = [_cost_one(row["result"].get("usage")) for row in results]
    if any(value is None for value in values):
        return None
    return round(sum(filter(None, values)), 8)


def _cost_one(usage: dict | None) -> float | None:
    if not usage or usage.get("input_tokens") is None or usage.get("output_tokens") is None:
        return None
    cached = usage.get("cached_input_tokens") or 0
    return (
        (usage["input_tokens"] - cached) * 0.75 + cached * 0.075 + usage["output_tokens"] * 4.5
    ) / 1e6


def execute(options: RunOptions, live: bool = False, caller: Caller | None = None) -> dict:
    packets, prompt, schema, hashes = read_prepared(options)
    envelope = sum(reservation(p, prompt, schema, options) for p in packets)
    if envelope > options.budget_usd:
        raise ValueError("Conservative token-cost planning envelope exceeds POC budget")
    config = run_config(options, hashes, packets)
    if not live:
        return {"mode": "offline plan", "config": config, "planning_cost_envelope_usd": envelope}
    with _exclusive(options.output):
        return _execute_live(options, caller, packets, prompt, schema, config, envelope)


def _execute_live(
    options: RunOptions,
    caller: Caller | None,
    packets: list[dict],
    prompt: str,
    schema: dict,
    config: dict,
    envelope: float,
) -> dict:
    _event(
        options.output,
        "launch_intent",
        pid=os.getpid(),
        config=config,
        planning_cost_envelope_usd=envelope,
        argv=_public_argv(),
        worker_identity=_worker_identity(),
    )
    if caller is None:
        load_dotenv()
        caller = RoleProvider(
            options.provider,
            options.model,
            options.base_url,
            options.timeout,
            options.max_output_tokens,
        ).call
    return _work(options, caller, packets, prompt, schema, config)


def _public_argv() -> list[str]:
    import sys

    return sys.argv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider", choices=["openai", "ollama"], required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url")
    parser.add_argument("--case", action="append", dest="cases", default=[])
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--max-seconds", type=float, default=900)
    parser.add_argument("--max-output-tokens", type=int, default=3000)
    parser.add_argument("--budget-usd", type=float, default=0.25)
    parser.add_argument("--live", action="store_true")
    arguments = vars(parser.parse_args())
    live = arguments.pop("live")
    arguments["base_url"] = arguments["base_url"] or _default_url(arguments["provider"])
    options = RunOptions.model_validate(arguments)
    print(json.dumps(execute(options, live), indent=2, ensure_ascii=False))


def _default_url(provider: str) -> str:
    return "https://api.openai.com/v1" if provider == "openai" else "http://127.0.0.1:11434/v1"


def _worker_identity() -> dict:
    try:
        result = subprocess.run(
            ["ps", "-p", str(os.getpid()), "-o", "lstart=,command="],
            capture_output=True,
            text=True,
            check=True,
        )
        return {
            "host": platform.node(),
            "pid": os.getpid(),
            "os_start_and_command": result.stdout.strip(),
        }
    except (OSError, subprocess.CalledProcessError) as error:
        return {
            "host": platform.node(),
            "pid": os.getpid(),
            "inspection_error": type(error).__name__,
        }


if __name__ == "__main__":
    main()
