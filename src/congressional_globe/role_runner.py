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
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

from congressional_globe.metadata_results import (
    MetadataContract,
    mapped_metadata,
    packet_text,
    validated_metadata,
)
from congressional_globe.role_provider import RoleProvider
from congressional_globe.role_run_io import (
    RunOptions,
    frozen_request,
    read_prepared,
    reservation,
    run_config,
    write_json,
)
from congressional_globe.role_run_store import RoleRunStore

Caller = Callable[[dict, str, dict], dict]


class _ProviderReply(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    raw_response: str
    output_text: str
    status: str
    finish_reason: str | None
    usage: dict | None


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
    durations = [row["result"].get("elapsed_seconds") for row in store.results()]
    mean = _mean_duration(durations)
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


def _mean_duration(durations: list) -> float | None:
    if not durations or None in durations:
        return None
    return sum(durations) / len(durations)


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


def _parse_result(
    response: dict, packet: dict, frozen: dict, contract: MetadataContract
) -> tuple[str, dict]:
    try:
        reply = _ProviderReply.model_validate(response)
        if reply.status != "completed" or reply.finish_reason == "length":
            return "invalid", {"validation_error": "Provider response incomplete or refused"}
        parsed = json.loads(response["output_text"])
        validated = validated_metadata(parsed, packet, contract)
        return "valid", {
            **validated,
            "source_mapped_proposals": mapped_metadata(parsed, packet, frozen, contract),
            "validation_scope": "host contract/source bindings; historical accuracy unreviewed",
        }
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
    frozen: dict,
    contract: MetadataContract,
) -> tuple[str, dict]:
    tick = time.monotonic()
    elapsed = None
    try:
        response = _wait_call(caller, packet, prompt, schema, output, store, started)
        elapsed = round(time.monotonic() - tick, 3)
        store.record_response(store.inflight_id(packet["window_id"]), response, elapsed)
        status, validation = _parse_result(response, packet, frozen, contract)
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
    measured = round(time.monotonic() - tick, 3) if elapsed is None else elapsed
    return status, {**result, "elapsed_seconds": measured}


def _call_one(
    caller: Caller,
    packet: dict,
    prompt: str,
    schema: dict,
    output: Path,
    store: RoleRunStore,
    started: float,
    frozen: dict,
    contract: MetadataContract,
    request: dict,
) -> str:
    attempt_id = store.start(packet["window_id"], request)
    _event(
        output,
        "request_started",
        window_id=packet["window_id"],
        attempt_id=attempt_id,
        input_text=packet_text(packet, contract),
        **_progress(store, started),
    )
    status, result = _attempt(
        caller, packet, prompt, schema, output, store, started, frozen, contract
    )
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
    sources: dict,
) -> dict:
    started = time.monotonic()
    store = RoleRunStore(options.output / "jobs.sqlite", config, packets)
    try:
        return _work_store(options, caller, prompt, schema, store, started, sources)
    finally:
        store.close()


def _work_store(
    options: RunOptions,
    caller: Caller,
    prompt: str,
    schema: dict,
    store: RoleRunStore,
    started: float,
    sources: dict,
) -> dict:
    _recover_saved(store, sources, options.contract)
    _require_no_unknown(store)
    prior_seconds = store.budget_summary()["seconds"]
    _event(options.output, "worker_started", pid=os.getpid(), **_progress(store, started))
    packet = _eligible_pending(store)
    while packet is not None:
        if not _has_budget(options, store, started, prior_seconds):
            _event(
                options.output,
                "dispatch_stopped",
                reason="insufficient_or_unknown_cumulative_budget",
                cumulative_usage=store.budget_summary(),
            )
            break
        status = _call_one(
            caller,
            packet,
            prompt,
            schema,
            options.output,
            store,
            started,
            sources[packet["window_id"]],
            options.contract,
            frozen_request(options, packet, prompt, schema),
        )
        if status != "valid":
            break
        packet = _eligible_pending(store)
    summary = _summary(store, options.provider)
    write_json(options.output / "summary.json", summary)
    write_json(options.output / "proposals.json", _proposal_export(summary, options.contract))
    _event(options.output, "worker_stopped", summary=summary, **_progress(store, started))
    return summary


def _eligible_pending(store: RoleRunStore) -> dict | None:
    statuses = store.summary()["statuses"]
    if statuses["invalid"] or statuses["error"]:
        return None
    return store.next_pending()


def _recover_saved(store: RoleRunStore, sources: dict, contract: MetadataContract) -> None:
    for saved in store.saved_responses():
        frozen = sources[saved["window_id"]]
        packet = store.packet(saved["window_id"])
        status, validation = _parse_result(saved["response"], packet, frozen, contract)
        result = {**saved["response"], **validation, "elapsed_seconds": saved["elapsed_seconds"]}
        store.finish(saved["attempt_id"], result, status)


def _has_budget(
    options: RunOptions, store: RoleRunStore, started: float, prior_seconds: float
) -> bool:
    usage = store.budget_summary()
    if usage["unknown_elapsed"] or usage["unknown_usage"]:
        return False
    if usage["calls"] >= options.limit or usage["output_limit_exceeded"]:
        return False
    elapsed = max(usage["seconds"], prior_seconds + time.monotonic() - started)
    return elapsed + options.timeout <= options.max_seconds and _paid_capacity(options, store)


def _paid_capacity(options: RunOptions, store: RoleRunStore) -> bool:
    spent = _cost(store.results(), options.provider)
    if spent is None:
        return False
    packet = store.next_pending()
    if packet is None:
        return spent <= options.budget_usd
    reserved = store.config["request_reservations_usd"][packet["window_id"]]
    return spent + reserved <= options.budget_usd


def _proposal_export(summary: dict, contract: MetadataContract) -> dict:
    return {
        "contract": contract,
        "historical_status": "proposal_only_not_human_reviewed",
        "results": [_proposal_row(row) for row in summary["results"]],
        "raw_results": "summary.json and jobs.sqlite retain raw provider responses and usage",
    }


def _proposal_row(row: dict) -> dict:
    result = row["result"]
    return {
        "window_id": row["window_id"],
        "status": row["status"],
        "source_mapped_proposals": result.get("source_mapped_proposals"),
        "validation_error": result.get("validation_error"),
        "error": result.get("error"),
    }


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
        "cumulative_usage": store.budget_summary(),
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
    if not _known_usage(usage):
        return None
    assert usage is not None
    cached = usage.get("cached_input_tokens") or 0
    return (
        (usage["input_tokens"] - cached) * 0.75 + cached * 0.075 + usage["output_tokens"] * 4.5
    ) / 1e6


def _known_usage(usage: dict | None) -> bool:
    if not isinstance(usage, dict):
        return False
    values: list[Any] = [
        usage.get("input_tokens"),
        usage.get("output_tokens"),
        usage.get("cached_input_tokens") or 0,
    ]
    return _valid_counts(values) and values[2] <= values[0]


def _valid_counts(values: list) -> bool:
    return all(type(value) is int and value >= 0 for value in values)


def execute(options: RunOptions, live: bool = False, caller: Caller | None = None) -> dict:
    packets, prompt, schema, hashes, sources = read_prepared(options)
    envelope = sum(reservation(p, prompt, schema, options) for p in packets)
    if envelope > options.budget_usd:
        raise ValueError("Conservative token-cost planning envelope exceeds POC budget")
    config = run_config(options, hashes, packets)
    config["request_hashes"] = {
        p["window_id"]: _request_digest(frozen_request(options, p, prompt, schema)) for p in packets
    }
    config["request_reservations_usd"] = {
        p["window_id"]: reservation(p, prompt, schema, options) for p in packets
    }
    if not live:
        return {"mode": "offline plan", "config": config, "planning_cost_envelope_usd": envelope}
    with _exclusive(options.output):
        return _execute_live(options, caller, packets, prompt, schema, config, envelope, sources)


def _request_digest(request: dict) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(
            request,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def _execute_live(
    options: RunOptions,
    caller: Caller | None,
    packets: list[dict],
    prompt: str,
    schema: dict,
    config: dict,
    envelope: float,
    sources: dict,
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
    return _work(options, caller, packets, prompt, schema, config, sources)


def _public_argv() -> list[str]:
    import sys

    return sys.argv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider", choices=["openai", "ollama"], required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--contract", choices=["role-v1", "role-v2", "scoped-date-v1"], default="role-v1"
    )
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
