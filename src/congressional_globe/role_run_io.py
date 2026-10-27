"""Hash-bound prepared inputs and bounded role-run configuration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from congressional_globe.metadata_results import (
    MetadataContract,
    metadata_schema,
    verify_metadata_packet,
)


class RunOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prepared: Path
    output: Path
    provider: Literal["openai", "ollama"]
    model: str = Field(min_length=1)
    base_url: str
    contract: MetadataContract = "role-v1"
    cases: list[str] = Field(default_factory=list)
    limit: int = Field(default=6, ge=1, le=6)
    timeout: float = Field(default=120, gt=0, le=120)
    max_seconds: float = Field(default=900, gt=0, le=900)
    max_output_tokens: int = Field(default=3000, ge=128, le=3000)
    budget_usd: float = Field(default=0.25, gt=0, le=0.25)


class _Manifest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    files_sha256: dict[str, str]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_prepared(options: RunOptions) -> tuple[list[dict], str, dict, dict, dict]:
    base = options.prepared
    manifest = _Manifest.model_validate_json((base / "manifest.json").read_text())
    _required_files(manifest)
    for filename, expected in manifest.files_sha256.items():
        _verify_file(base, filename, expected)
    _verify_review(base)
    packets = _read_jsonl(base / "provider-inputs.jsonl")
    frozen = _read_jsonl(base / "frozen-inputs.jsonl")
    _verify_packets(packets, frozen, options.contract)
    packets = select_cases(packets, options.cases, options.limit)
    schema = json.loads((base / "output.schema.json").read_text())
    if schema != metadata_schema(options.contract):
        raise ValueError("Prepared output schema does not match selected contract")
    hashes = {
        **manifest.files_sha256,
        "source-review.json": digest(base / "source-review.json"),
        "checks.json": digest(base / "checks.json"),
    }
    return (
        packets,
        (base / "prompt.txt").read_text(),
        schema,
        hashes,
        {row["window_id"]: row for row in frozen},
    )


def _required_files(manifest: _Manifest) -> None:
    required = {"provider-inputs.jsonl", "frozen-inputs.jsonl", "prompt.txt", "output.schema.json"}
    if not required <= manifest.files_sha256.keys():
        raise ValueError("Prepared manifest is missing required file hashes")


def _verify_file(base: Path, filename: str, expected: str) -> None:
    if Path(filename).name != filename or digest(base / filename) != expected:
        raise ValueError(f"Prepared file identity mismatch: {filename}")


def _verify_review(base: Path) -> None:
    checks = json.loads((base / "checks.json").read_text())
    if digest(base / "source-review.json") != checks["source_review_sha256"]:
        raise ValueError("Frozen source-review hash mismatch")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _verify_packets(packets: list[dict], frozen: list[dict], contract: MetadataContract) -> None:
    if not 1 <= len(packets) <= 6:
        raise ValueError("Expected one to six frozen diagnostic inputs")
    for packet, row in zip(packets, frozen, strict=True):
        verify_metadata_packet(packet, row, contract)


def select_cases(packets: list[dict], cases: list[str], limit: int) -> list[dict]:
    by_id = {packet["window_id"]: packet for packet in packets}
    if len(by_id) != len(packets):
        raise ValueError("Duplicate prepared window IDs")
    selected = cases or list(by_id)
    _check_selection(selected, set(by_id))
    return [by_id[identifier] for identifier in selected[:limit]]


def reservation(packet: dict, prompt: str, schema: dict, options: RunOptions) -> float:
    if options.provider == "ollama":
        return 0.0
    if options.model != "gpt-5.4-mini":
        raise ValueError("Paid POC cost guard supports only the authorized gpt-5.4-mini")
    payload = json.dumps(packet, ensure_ascii=False) + prompt + json.dumps(schema)
    return ((len(payload.encode()) + 4096) * 0.75 + options.max_output_tokens * 4.5) / 1e6


def run_config(options: RunOptions, hashes: dict, packets: list[dict]) -> dict:
    fields = options.model_dump(mode="json", exclude={"prepared", "output"})
    names = (
        "role_aliases.py",
        "role_provider.py",
        "role_run_store.py",
        "role_run_io.py",
        "role_runner.py",
        "metadata_results.py",
        "role_v2.py",
        "scoped_dates.py",
        "quote_dates.py",
    )
    return {
        **fields,
        "input_hashes": hashes,
        "case_ids": [p["window_id"] for p in packets],
        "code_hashes": {name: digest(Path(__file__).parent / name) for name in names},
    }


def frozen_request(options: RunOptions, packet: dict, prompt: str, schema: dict) -> dict:
    return {
        "provider": options.provider,
        "model": options.model,
        "base_url": options.base_url,
        "contract": options.contract,
        "packet": packet,
        "prompt": prompt,
        "schema": schema,
        "max_output_tokens": options.max_output_tokens,
        "timeout": options.timeout,
        "reasoning_effort": "none",
    }


def _check_selection(selected: list[str], available: set[str]) -> None:
    if len(selected) != len(set(selected)) or not set(selected) <= available:
        raise ValueError("Unknown or duplicate selected case")
