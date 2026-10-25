"""Launch the frozen bounded reading comparison only after file-bound readiness."""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from congressional_globe.reading_contracts import ReadingCandidate
from congressional_globe.reading_dispatch import (
    RequestReadiness,
    _task_id,
    dispatch,
    verify_runtime,
)
from congressional_globe.reading_images import verify_index
from congressional_globe.reading_requests import digest, materialize_record
from congressional_globe.reading_run_store import ReadingRunStore

MANIFEST = Path("artifacts/reading-launch-20261025-01/requests.json")
COUNTS = Path("artifacts/reading-count-20261025-01/counts.json")
PROTOCOL = Path("artifacts/reading-launch-20261025-01/assessment-protocol.json")
REVIEW = Path("docs/archive/human-review/HR-009-v1/applied.json")
CANDIDATES = Path("artifacts/reading-prepare-20261024-03/candidates.jsonl")
IMAGES = Path("artifacts/reading-images-20261024-01/index.json")
BINARY = Path("/Applications/Ollama.app/Contents/Resources/ollama")


def _json(path):
    return json.loads(path.read_text())


def _sha(path):
    return digest(path.read_bytes())


def prepare(
    manifest_path=MANIFEST, counts_path=COUNTS, protocol_path=PROTOCOL
) -> tuple[list[dict], dict, dict, dict]:
    manifest, counts, protocol, review = map(
        _json, [manifest_path, counts_path, protocol_path, REVIEW]
    )
    if counts["request_manifest"]["sha256"] != _sha(manifest_path):
        raise ValueError("count evidence does not match launch request manifest")
    if counts["runtime_binary_sha256"] != _sha(BINARY):
        raise ValueError("runtime binary differs from counted source/build evidence")
    _check_source_and_review(protocol, review)
    units = {u.id: u for u in _units()}
    verify_index(IMAGES, list(units.values()))
    rows = _counted_records(manifest, counts)
    evidence = _readiness(rows, counts, counts_path, protocol_path)
    config = dict(
        files={
            str(p): _sha(p)
            for p in [manifest_path, counts_path, protocol_path, REVIEW, CANDIDATES, IMAGES]
        },
        code={
            str(p): _sha(p) for p in sorted(Path("src/congressional_globe").glob("reading_*.py"))
        },
        max_calls=60,
        total_seconds=7200,
        per_model_seconds=2400,
        call_seconds=120,
        source_derived_fit=True,
        runtime_count_must_match=True,
    )
    return rows, units, evidence, config


def _units():
    return [
        ReadingCandidate.model_validate_json(line) for line in CANDIDATES.read_text().splitlines()
    ]


def _check_source_and_review(protocol, review):
    if not protocol["source_expectations_frozen"]:
        raise ValueError("pre-output source expectations are not frozen")
    _verify_evidence_files(protocol["evidence"])
    source = protocol["source_expectations"]
    if _sha(Path(source["path"])) != source["sha256"]:
        raise ValueError("pre-output source observations changed")
    if review["answer"] != "Use the 10-minute review plan":
        raise ValueError("review policy is not the approved bounded plan")


def _verify_evidence_files(evidence):
    for path, expected in evidence.items():
        if _sha(Path(path)) != expected:
            raise ValueError("assessment policy evidence changed")


def _counted_records(manifest, counts):
    by_hash = {row["request_sha256"]: row for row in counts["counts"]}
    if len(by_hash) != len(manifest["requests"]):
        raise ValueError("count evidence does not cover every exact request once")
    return [
        _check_count(record, by_hash[record["request_sha256"]]) for record in manifest["requests"]
    ]


def _check_count(record, count):
    if (count["model"], count["model_digest"]) != (record["model"], record["model_digest"]):
        raise ValueError("count model identity mismatch")
    if (
        count["total_input_tokens"] + record["options"]["num_predict"]
        > record["options"]["num_ctx"]
    ):
        raise ValueError("counted request does not fit with full output reserve")
    materialize_record(record)
    return {**record, "token_fit": "verified", "launch_ready": True}


def _readiness(rows, counts, counts_path=COUNTS, protocol_path=PROTOCOL):
    by_hash = {row["request_sha256"]: row for row in counts["counts"]}
    return {
        _task_id(record): RequestReadiness(
            request_sha256=record["request_sha256"],
            model_digest=record["model_digest"],
            token_fit_sha256=_sha(counts_path),
            source_expectation_sha256=_sha(protocol_path),
            review_effort_sha256=_sha(REVIEW),
            expected_input_tokens=by_hash[record["request_sha256"]]["total_input_tokens"],
            token_fit_verified=True,
            source_expectations_frozen=True,
            review_effort_resolved=True,
        )
        for record in rows
    }


def _process_proof(path: Path):
    proof = _json(path)
    age = (datetime.now(UTC) - datetime.fromisoformat(proof["observed_utc"])).total_seconds()
    if not 0 <= age <= 60:
        raise ValueError("process/queue observation must be less than60seconds old")
    if not proof["no_competing_worker"] or proof["cleanup_claimed"] != 0:
        raise ValueError("another worker or queue claim requires reconciliation")
    return proof


def launch(
    output: Path,
    process_proof: Path,
    *,
    execute=False,
    manifest_path=MANIFEST,
    counts_path=COUNTS,
    protocol_path=PROTOCOL,
    stop_file=None,
    max_calls=60,
    total_seconds=7200,
    per_model_seconds=2400,
) -> dict:
    rows, units, evidence, config = prepare(manifest_path, counts_path, protocol_path)
    config.update(
        max_calls=max_calls, total_seconds=total_seconds, per_model_seconds=per_model_seconds
    )
    output.mkdir(exist_ok=True, parents=True)
    if not execute:
        return dict(status="offline_ready", requests=len(rows), config=config, provider_calls=0)
    _process_proof(process_proof)
    runtime = verify_runtime(
        "http://127.0.0.1:11434", {r["model"]: r["model_digest"] for r in rows}
    )
    runtime = runtime.model_copy(
        update=dict(process_state_verified=True, process_observation_sha256=_sha(process_proof))
    )
    tasks = [
        dict(
            task_id=_task_id(r), request_sha256=r["request_sha256"], model_digest=r["model_digest"]
        )
        for r in rows
    ]
    store = ReadingRunStore(output / "attempts.sqlite", config, tasks)
    try:
        results = dispatch(
            store,
            rows,
            units,
            evidence,
            runtime,
            "http://127.0.0.1:11434",
            opt_in=True,
            max_calls=max_calls,
            total_seconds=total_seconds,
            per_model_seconds=per_model_seconds,
            stop_file=stop_file,
        )
        report = dict(summary=store.summary(), results=results, config=config)
        (output / f"results-{uuid.uuid4()}.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )
        return dict(summary=store.summary(), returned_results=len(results))
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--process-proof", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--counts", type=Path, default=COUNTS)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--stop-file", type=Path)
    parser.add_argument("--max-calls", type=int, default=60)
    parser.add_argument("--total-seconds", type=int, default=7200)
    parser.add_argument("--per-model-seconds", type=int, default=2400)
    args = parser.parse_args()
    print(
        json.dumps(
            launch(
                args.output,
                args.process_proof,
                execute=args.execute,
                manifest_path=args.manifest,
                counts_path=args.counts,
                protocol_path=args.protocol,
                stop_file=args.stop_file,
                max_calls=args.max_calls,
                total_seconds=args.total_seconds,
                per_model_seconds=args.per_model_seconds,
            )
        )
    )


if __name__ == "__main__":
    main()
