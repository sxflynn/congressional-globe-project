import json
from datetime import UTC, datetime, timedelta

import pytest

from congressional_globe import reading_launch as launch


def test_count_evidence_rejects_output_reserve_overflow(monkeypatch):
    monkeypatch.setattr(launch, "materialize_record", lambda record: None)
    record = dict(model="m", model_digest="digest", options=dict(num_ctx=16384, num_predict=4096))
    count = dict(model="m", model_digest="digest", total_input_tokens=12289)
    with pytest.raises(ValueError, match="reserve"):
        launch._check_count(record, count)
    count["total_input_tokens"] = 12288
    assert launch._check_count(record, count)["token_fit"] == "verified"


def test_count_evidence_rejects_different_model(monkeypatch):
    monkeypatch.setattr(launch, "materialize_record", lambda record: None)
    with pytest.raises(ValueError, match="identity"):
        launch._check_count(
            dict(model="m", model_digest="digest"), dict(model="n", model_digest="digest")
        )


def test_stale_or_busy_process_proof_cannot_launch(tmp_path):
    path = tmp_path / "proof.json"
    proof = dict(
        observed_utc=(datetime.now(UTC) - timedelta(seconds=61)).isoformat(),
        no_competing_worker=True,
        cleanup_claimed=0,
    )
    path.write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="old"):
        launch._process_proof(path)
    proof.update(observed_utc=datetime.now(UTC).isoformat(), cleanup_claimed=1)
    path.write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="worker"):
        launch._process_proof(path)


def test_offline_prepare_never_touches_transport(monkeypatch, tmp_path):
    monkeypatch.setattr(launch, "prepare", lambda *args: ([], {}, {}, {"test": "synthetic"}))
    monkeypatch.setattr(
        launch, "verify_runtime", lambda *args: pytest.fail("offline run contacted runtime")
    )
    assert launch.launch(tmp_path, tmp_path / "not-present.json")["provider_calls"] == 0


def test_launch_passes_tighter_bounds_and_cooperative_stop_to_dispatch(monkeypatch, tmp_path):
    from congressional_globe.reading_dispatch import RuntimeCheck

    monkeypatch.setattr(launch, "prepare", lambda *args: ([], {}, {}, {}))
    runtime = RuntimeCheck(
        checked_at=datetime.now(UTC),
        runtime_version="test",
        process_state_verified=False,
        process_observation_sha256="0" * 64,
        model_digests={},
    )
    monkeypatch.setattr(launch, "verify_runtime", lambda *args: runtime)
    seen = {}

    def capture(*args, **kwargs):
        seen.update(kwargs)
        return []

    monkeypatch.setattr(launch, "dispatch", capture)
    proof = tmp_path / "proof.json"
    proof.write_text(
        json.dumps(
            dict(
                observed_utc=datetime.now(UTC).isoformat(),
                no_competing_worker=True,
                cleanup_claimed=0,
            )
        )
    )
    stop = tmp_path / "STOP"
    launch.launch(
        tmp_path,
        proof,
        execute=True,
        max_calls=6,
        total_seconds=1200,
        per_model_seconds=360,
        stop_file=stop,
    )
    assert (
        seen["max_calls"],
        seen["total_seconds"],
        seen["per_model_seconds"],
        seen["stop_file"],
    ) == (6, 1200, 360, stop)
