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
    monkeypatch.setattr(launch, "prepare", lambda: ([], {}, {}, {"test": "synthetic"}))
    monkeypatch.setattr(
        launch, "verify_runtime", lambda *args: pytest.fail("offline run contacted runtime")
    )
    assert launch.launch(tmp_path, tmp_path / "not-present.json")["provider_calls"] == 0
