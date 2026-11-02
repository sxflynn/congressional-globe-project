"""One explicitly approved original S5 attempt; never native-fit clearance.

The fixed spent-slot file survives changed configuration/output arguments. Recovery
can import durable receipts but cannot start a process or send another request.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Literal

from pydantic import Field

from congressional_globe import productive_ocr_measurement_scoped as scoped
from congressional_globe.bracket_cues import Contract
from congressional_globe.productive_ocr_authority import MODEL_DIGEST, MODEL_NAME
from congressional_globe.productive_ocr_export import export_reply
from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
from congressional_globe.productive_ocr_live import RuntimeObservation
from congressional_globe.productive_ocr_local import OwnedLocalClient, OwnedLocalPlan, read_spool
from congressional_globe.productive_ocr_long_audit import LongerAuditPlan
from congressional_globe.productive_ocr_measurement_inputs import load_s5_inputs
from congressional_globe.productive_ocr_runner import _session_lock, code_identity, fingerprint
from congressional_globe.role_run_store import RoleRunStore
from congressional_globe.scan_models import Sha256

APPROVAL_SHA = "8afa77450efbfdc1f0f4cc236fcfd16f3c4d6763b0c91e6c0e6d666f4ef13bfc"
BODY_SHA = "e19305443cf7b8676acdf25848b88455db203d55b8e1c394116bdd071aed000a"
EXECUTABLE_SHA = "e5c7c0ffa50d23d0f0e59cbf325f689b0010ee5563be89b73b05f08844e19e6b"
PACKAGE = Path("artifacts/s5-measurement-20261029-01")
REPOSITORY = Path(__file__).resolve().parents[2]
TEXT_PACKAGE = Path("artifacts/s5-text-measurement-20261030-01")
TEXT_APPROVAL_SHA = "7dfdbef3c989b6ec85470f02ee5c988a2e53a393fbbec7ae233e2c77b3895f17"
TEXT_BODY_SHA = "067610eef55dd0c346b3a5f41494b6b0e2c57cfbebf1f923dd047d7c476ab08f"
CONFORMANCE_PACKAGE = Path("artifacts/s5-conformance-verification-20261030-01")
CONFORMANCE_APPROVAL_SHA = "2e9f82f13d17572421e8d40f071b958788a9e4f80684c5ded07a331cd7355572"
CONFORMANCE_BODY_SHA = "dd3f0268df6a4c03a0fdac962313336d1869b239953113c788b28c8aca12acd8"


class MeasurementSpec(Contract):
    contract: Literal[
        "productive-ocr-s5-measurement-v1",
        "productive-ocr-s5-text-measurement-v2",
        "productive-ocr-s5-conformance-measurement-v3",
        "productive-ocr-s5-scoped-repeat-1-v4",
        "productive-ocr-s5-scoped-repeat-2-v4",
        "productive-ocr-s5-scoped-repeat-3-v4",
        "productive-ocr-s1-scoped-repeat-1-v4",
        "productive-ocr-s1-scoped-repeat-2-v4",
        "productive-ocr-s1-scoped-repeat-3-v4",
        "productive-ocr-s2-scoped-repeat-1-v4",
        "productive-ocr-s2-scoped-repeat-2-v4",
        "productive-ocr-s2-scoped-repeat-3-v4",
        "productive-ocr-d1-audit-repeat-1-v2",
        "productive-ocr-d1-audit-repeat-2-v2",
        "productive-ocr-d1-audit-repeat-3-v2",
        "productive-ocr-d2-audit-repeat-1-v2",
        "productive-ocr-d2-audit-repeat-2-v2",
        "productive-ocr-d2-audit-repeat-3-v2",
        "productive-ocr-d1c-compact-repeat-1-v3",
        "productive-ocr-d1c-compact-repeat-2-v3",
        "productive-ocr-d1c-compact-repeat-3-v3",
        "productive-ocr-d1l-long-repeat-1-v3",
        "productive-ocr-d1l-long-repeat-2-v3",
        "productive-ocr-d1l-long-repeat-3-v3",
        "productive-ocr-d1a-lean-repeat-1-v1",
        "productive-ocr-d1a-lean-repeat-2-v1",
        "productive-ocr-d1a-lean-repeat-3-v1",
        "productive-ocr-d1w-whole-repeat-1-v1",
        "productive-ocr-d1w-whole-repeat-2-v1",
        "productive-ocr-d1w-whole-repeat-3-v1",
        "productive-ocr-d2w-whole-repeat-1-v1",
        "productive-ocr-d2w-whole-repeat-2-v1",
        "productive-ocr-d2w-whole-repeat-3-v1",
        "productive-ocr-d2i-image-repeat-1-v1",
        "productive-ocr-d2i-image-repeat-2-v1",
        "productive-ocr-d2i-image-repeat-3-v1",
    ]
    approval_sha256: Sha256
    body_sha256: Sha256
    code_sha256: Sha256
    started_at_epoch: float = Field(gt=0, allow_inf_nan=False)
    plan: OwnedLocalPlan | LongerAuditPlan


def write_new(path: Path, value: object) -> None:
    """Durably save a new checkpoint; never overwrite an earlier result."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical_json(value))
        stream.flush()
        os.fsync(stream.fileno())


def _verify_spec(repository: Path, spec: MeasurementSpec) -> None:
    _verify_repository(repository, _package(spec))
    _verify_approval(repository, spec)
    if spec.code_sha256 != fingerprint(code_identity()):
        raise ValueError("measurement implementation differs from frozen code")
    _verify_backend(spec)
    _verify_session_time(spec)


def _verify_approval(repository: Path, spec: MeasurementSpec) -> None:
    approval_sha, body_sha = _authority(spec)
    approval = _approval_path(repository, spec)
    if sha256_bytes(approval.read_bytes()) != approval_sha:
        raise ValueError("exact human S5 approval is absent or changed")
    if (spec.approval_sha256, spec.body_sha256) != (approval_sha, body_sha):
        raise ValueError("measurement scope differs from the approved S5 attempt")


def _approval_path(repository, spec):
    if spec.contract in scoped.ALL_PROFILES:
        return scoped.approval_path(repository, spec)
    return repository / _package(spec) / "approval.json"


def _verify_repository(repository: Path, package: Path = PACKAGE) -> None:
    if repository.resolve() != REPOSITORY:
        raise ValueError("measurement spent slot belongs to the original repository only")
    if (repository / package).is_symlink() or (repository / package / "run").is_symlink():
        raise ValueError("measurement evidence directories cannot be symlinks")


def _verify_backend(spec: MeasurementSpec) -> None:
    plan = spec.plan
    actual = (plan.model_name, plan.model_digest, plan.executable_sha256)
    if actual != (MODEL_NAME, MODEL_DIGEST, EXECUTABLE_SHA):
        raise ValueError("S5 measurement requires the exact approved installed backend")
    if plan.executable != "/Applications/Ollama.app/Contents/Resources/ollama":
        raise ValueError("measurement executable path differs from the approved backend")
    if plan.request_timeout_seconds != _timeout_seconds(spec) or plan.startup_timeout_seconds > 45:
        raise ValueError("measurement lifecycle differs from its fixed diagnostic time bound")


def _verify_session_time(spec: MeasurementSpec) -> None:
    if spec.plan.session_deadline_epoch != spec.started_at_epoch + 600:
        raise ValueError("measurement must bind the approved600second whole session")
    age = time.time() - spec.started_at_epoch
    if not 0 <= age <= _prep_seconds(spec):
        raise TimeoutError("preparation exceeded its bounded phase or clock is unverified")


def _verify_runtime(directory: Path, spec: MeasurementSpec) -> RuntimeObservation:
    proof = RuntimeObservation.model_validate_json((directory / "runtime.json").read_bytes())
    if (proof.readiness_sha256, proof.window_id) != (
        fingerprint(spec.model_dump(mode="json")),
        scoped.window(spec),
    ):
        raise ValueError("operator observation does not bind this exact S5 specification")
    if not 0 <= time.time() - proof.checked_at_epoch <= 30:
        raise ValueError("operator runtime observation is stale or future dated")
    _verify_runtime_files(directory, proof)
    return proof


def _verify_runtime_files(directory: Path, proof: RuntimeObservation) -> None:
    for digest in (
        proof.process_evidence_sha256,
        proof.queue_evidence_sha256,
        proof.log_evidence_sha256,
        proof.model_metadata_sha256,
    ):
        path = directory / "evidence" / digest
        if path.stat().st_size > 1024 * 1024 or sha256_bytes(path.read_bytes()) != digest:
            raise ValueError("bounded operator runtime evidence is missing or changed")


def execute(repository: Path, spec: MeasurementSpec, checkpoint=lambda _: None) -> dict:
    """Validate source and authority, claim a fixed slot, then send at most once."""
    _verify_spec(repository, spec)
    host, projection, _registry = _load_inputs(repository, spec)
    if projection.body_sha256 != spec.body_sha256:
        raise ValueError("selected input differs from exact approved request")
    directory = repository / _package(spec) / "run"
    _verify_runtime(directory, spec)
    _verify_session_time(spec)
    packet = {"window_id": scoped.window(spec), "host": host, "body_utf8": projection.body_utf8}
    with _session_lock():
        return _claim_execute(directory, spec, packet, checkpoint)


def _claim_execute(directory, spec, packet, checkpoint):
    config = {"spec": spec.model_dump(mode="json"), "max_output_tokens": 1500}
    if spec.contract in scoped.ALL_PROFILES:
        config["group_sha256"] = scoped.verify_group(REPOSITORY, spec, packet)
    write_new(directory.parent / "spent-slot.json", config)
    write_new(directory / "frozen.json", {"config": config, "packet": packet})
    store = RoleRunStore(directory / "jobs.sqlite", config, [packet])
    try:
        attempt = store.start(packet["window_id"], packet)
        checkpoint("after_claim")
        result = _attempt(directory, spec, packet, store, attempt, checkpoint)
        write_new(directory / "result.json", result)
        return result
    finally:
        store.close()


def _attempt(directory, spec, packet, store, attempt, checkpoint):
    def before_send() -> None:
        _verify_runtime(directory, spec)

    client = OwnedLocalClient(
        spec.plan,
        directory / "spool",
        before_send=before_send,
    )
    started = time.monotonic()
    try:
        call = client.start(packet["body_utf8"].encode())
    except Exception as error:
        return _finish_failure(store, attempt, error, time.monotonic() - started)
    return _receive(
        directory,
        packet,
        store,
        attempt,
        call,
        started,
        checkpoint,
        spec.plan.request_timeout_seconds,
    )


def _receive(directory, packet, store, attempt, call, started, checkpoint, timeout=120):
    try:
        response = call.result(timeout=timeout)
    except Exception as error:
        state = call.cancel_and_observe()
        return _finish_failure(store, attempt, error, time.monotonic() - started, state)
    elapsed = time.monotonic() - started
    store.record_response(attempt, response, elapsed)
    checkpoint("after_raw")
    result = _finish_response(store, attempt, packet, response, elapsed, call.observe())
    return result


def _finish_failure(store, attempt, error, elapsed, state=None):
    result = {
        "error_type": type(error).__name__,
        "error_cause_types": _error_cause_types(error),
        "error": str(error)[:1000],
        "owned_stop_observation": state or getattr(error, "owned_stop_observation", "unknown"),
        "elapsed_seconds": elapsed,
        "usage": None,
        "input_fit": "unknown; no authentic native preflight",
        "outcome": "spent attempt; no retry; inspect durable transport spool",
    }
    store.finish(attempt, result, "unresolved")
    return result


def _error_cause_types(error):
    names = []
    for _index in range(4):
        names.append(type(error).__name__)
        error = error.__cause__
        if error is None:
            break
    return names


def _finish_response(store, attempt, packet, response, elapsed, state):
    exported = _export(packet, response, elapsed)
    result = {
        **response,
        "elapsed_seconds": elapsed,
        "owned_stop_observation": state,
        "source_export": exported,
        "input_fit": "unknown; backend counts are reported values, not authentic native fit",
        "input_reporting_threshold": 6000,
        "launch_clearance": None,
    }
    status = _result_status(response, exported, state)
    result["measurement_status"] = status
    store.finish(attempt, result, status)
    return result


def _export(packet, response, elapsed):
    if packet.get("window_id") in {"D1A", "D1W", "D2W", "D2I"}:
        from congressional_globe.productive_ocr_appendix_audit import export_appendix_reply
        from congressional_globe.productive_ocr_image_statute import export_image_reply
        from congressional_globe.productive_ocr_lean_audit import export_lean_reply
        from congressional_globe.productive_ocr_whole_audit import export_whole_reply

        exporter = {
            "D1A": export_lean_reply,
            "D1W": export_whole_reply,
            "D2W": export_appendix_reply,
            "D2I": export_image_reply,
        }[packet["window_id"]]
        return exporter(REPOSITORY, packet, response, elapsed)
    if packet.get("window_id") in {"D1C", "D1L"}:
        from congressional_globe.productive_ocr_compact_measurement import export_compact_reply

        return export_compact_reply(REPOSITORY, packet, response, elapsed)
    host = packet["host"]
    if host["payload"].get("contract") == "ocr-productive-repair-host-input-v3":
        return _export_text(packet, response)
    return export_reply(
        host,
        packet["body_utf8"],
        response.get("output_text", ""),
        host["payload"]["model_digest"],
        host["payload"]["response_schema_sha256"],
        response.get("usage"),
        elapsed,
    ).model_dump(mode="json")


def _result_status(response, exported, state):
    if state != "stopped":
        return "unresolved"
    if not _complete_response(response):
        return "invalid"
    return _export_status(exported)


def _complete_response(response):
    usage = response.get("usage") or {}
    return (
        response.get("status") == "completed"
        and response.get("finish_reason") != "length"
        and usage.get("output_tokens", 0) <= 1500
    )


def recover(repository: Path, selected_spec: MeasurementSpec | None = None) -> dict:
    """Reconcile one complete saved transport receipt without any dispatch path."""
    package = PACKAGE if selected_spec is None else _package(selected_spec)
    _verify_repository(repository, package)
    directory = repository / package / "run"
    frozen = json.loads((directory / "frozen.json").read_bytes())
    spec = MeasurementSpec.model_validate_json(canonical_json(frozen["config"]["spec"]))
    _match_recovery_spec(selected_spec, spec)
    packet = frozen["packet"]
    if json.loads((directory.parent / "spent-slot.json").read_bytes()) != frozen["config"]:
        raise ValueError("recovery configuration differs from the fixed spent slot")
    _verify_recovery_authority(repository, spec, packet)
    with _session_lock():
        store = RoleRunStore(directory / "jobs.sqlite", frozen["config"], [packet])
        try:
            return _recover_store(directory, spec, packet, store)
        finally:
            store.close()


def _verify_recovery_authority(repository, spec, packet):
    _verify_approval(repository, spec)
    _verify_backend(spec)
    if spec.code_sha256 != fingerprint(code_identity()):
        raise ValueError("recovery implementation differs from the frozen attempt")
    host, projection, _registry = _load_inputs(repository, spec)
    expected = {"window_id": scoped.window(spec), "host": host, "body_utf8": projection.body_utf8}
    if packet != expected or projection.body_sha256 != spec.body_sha256:
        raise ValueError("recovery checkpoint differs from the approved source/request")


def _recover_store(directory, spec, packet, store):
    if store.results():
        return {"results": store.results(), "dispatch": "disabled during recovery"}
    saved = read_spool(
        directory / "spool", spec.body_sha256, spec.plan.model_name, spec.plan.model_digest
    )
    if saved is None:
        raise ValueError("no complete receipt; slot stays spent and outcome unknown")
    attempt = store.inflight_id(scoped.window(spec))
    elapsed = _reconcile_saved_response(store, attempt, saved)
    return _finish_response(store, attempt, packet, saved.response, elapsed, saved.stop_observation)


def _reconcile_saved_response(store, attempt, recovered):
    prior = store.saved_responses()
    if prior:
        saved = prior[0]
        if (saved["attempt_id"], saved["response"]) != (attempt, recovered.response):
            raise ValueError("transport spool differs from immutable saved response")
        return saved["elapsed_seconds"]
    store.record_response(attempt, recovered.response, recovered.elapsed_seconds)
    return recovered.elapsed_seconds


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args()
    if args.recover:
        selected = _optional_spec(args.spec)
        result = recover(args.repository.resolve(), selected)
    else:
        if args.spec is None:
            parser.error("--spec is required for the single measurement attempt")
        spec = MeasurementSpec.model_validate_json(args.spec.read_bytes())
        result = execute(args.repository.resolve(), spec)
    print(json.dumps(result, ensure_ascii=False))


def _is_text(spec):
    return spec.contract == "productive-ocr-s5-text-measurement-v2"


def _package(spec):
    if spec.contract in scoped.ALL_PROFILES:
        return scoped.package(spec)
    if _is_conformance(spec):
        return CONFORMANCE_PACKAGE
    return TEXT_PACKAGE if _is_text(spec) else PACKAGE


def _authority(spec):
    if spec.contract in scoped.ALL_PROFILES:
        return scoped.authority(spec)
    if _is_conformance(spec):
        return CONFORMANCE_APPROVAL_SHA, CONFORMANCE_BODY_SHA
    return (TEXT_APPROVAL_SHA, TEXT_BODY_SHA) if _is_text(spec) else (APPROVAL_SHA, BODY_SHA)


def _timeout_seconds(spec):
    return (
        300
        if spec.contract
        in scoped.LONG_PROFILES
        + scoped.LEAN_PROFILES
        + scoped.WHOLE_PROFILES
        + scoped.APPENDIX_PROFILES
        + scoped.IMAGE_PROFILES
        else 120
    )


def _prep_seconds(spec):
    if (
        spec.contract
        in scoped.LONG_PROFILES
        + scoped.LEAN_PROFILES
        + scoped.WHOLE_PROFILES
        + scoped.APPENDIX_PROFILES
        + scoped.IMAGE_PROFILES
    ):
        return 90
    return 300 if spec.contract == "productive-ocr-s5-measurement-v1" else 270


def _load_inputs(repository, spec):
    if spec.contract in scoped.ALL_PROFILES:
        from congressional_globe.productive_ocr_measurement_inputs import load_scoped_inputs

        return load_scoped_inputs(repository, spec)
    if _is_conformance(spec):
        from congressional_globe.productive_ocr_measurement_inputs import load_s5_conformance_inputs

        return load_s5_conformance_inputs(repository)
    if not _is_text(spec):
        return load_s5_inputs(repository)
    from congressional_globe.productive_ocr_measurement_inputs import load_s5_text_inputs

    return load_s5_text_inputs(repository)


def _is_conformance(spec):
    return spec.contract == "productive-ocr-s5-conformance-measurement-v3"


def _export_text(packet, response):
    from congressional_globe.productive_ocr_text_reply import export_text_reply

    try:
        return export_text_reply(
            packet["host"], packet["body_utf8"], response.get("output_text", "")
        ).model_dump(mode="json")
    except (ValueError, KeyError, TypeError) as error:
        return {
            "outcome": "invalid",
            "rejection_reason": str(error)[:1000],
            "raw_reply_text": response.get("output_text", ""),
        }


def _export_status(exported):
    outcome = exported["outcome"]
    if outcome == "invalid":
        return "invalid"
    if isinstance(outcome, dict) and outcome["proposal_status"] == "unresolved":
        return "unresolved"
    return "valid"


def _optional_spec(path):
    return None if path is None else MeasurementSpec.model_validate_json(path.read_bytes())


def _match_recovery_spec(selected, frozen):
    if selected is not None and selected != frozen:
        raise ValueError("selected recovery specification differs from frozen attempt")


if __name__ == "__main__":
    main()
