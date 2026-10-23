import json
from pathlib import Path

import pytest

from congressional_globe.role_run_io import RunOptions
from congressional_globe.role_runner import execute

PREPARED = Path(__file__).parents[1] / "artifacts/role-alias-preparation-20261023-02"
CASE = "t2-1-010"


def _options(output):
    return RunOptions(
        prepared=PREPARED,
        output=output,
        provider="openai",
        model="gpt-5.4-mini",
        base_url="https://example.invalid/v1",
        cases=[CASE],
        timeout=1,
        max_seconds=30,
    )


def _response(*, bad_reference=False):
    role = {
        "candidate_id": None,
        "evidence_ids": [],
        "target_ids": ["missing" if bad_reference else "P1"],
        "role": "other",
        "status": "unknown",
        "basis": "The supplied excerpt does not identify a supported speaker.",
    }
    output = json.dumps({"speaker_roles": [role]})
    return {
        "raw_response": '{"provider":"fake"}',
        "output_text": output,
        "status": "completed",
        "finish_reason": None,
        "usage": {"input_tokens": 100, "output_tokens": 0, "cached_input_tokens": 20},
        "provider_request_id": "fake-request",
    }


def test_offline_plan_does_not_create_output_or_call_provider(tmp_path):
    output = tmp_path / "not-created"
    calls = []

    def caller(packet, prompt, schema):
        calls.append(packet)
        return _response()

    plan = execute(_options(output), caller=caller)
    assert plan["mode"] == "offline plan"
    assert calls == []
    assert not output.exists()


def test_valid_run_is_reused_without_another_provider_call(tmp_path):
    output = tmp_path / "run"
    calls = []

    def caller(packet, prompt, schema):
        calls.append(packet["window_id"])
        return _response()

    first = execute(_options(output), live=True, caller=caller)
    second = execute(_options(output), live=True, caller=caller)
    assert calls == [CASE]
    assert first["statuses"]["valid"] == second["statuses"]["valid"] == 1
    assert second["attempts"] == 1
    assert second["results"][0]["result"]["raw_response"] == '{"provider":"fake"}'


def test_timeout_is_unresolved_and_resume_requires_review(tmp_path):
    output = tmp_path / "run"
    calls = []

    def caller(*args):
        calls.append(1)
        raise TimeoutError("request outcome unknown")

    result = execute(_options(output), live=True, caller=caller)
    assert result["statuses"]["unresolved"] == 1
    assert len(calls) == 1
    with pytest.raises(ValueError, match="Unresolved call"):
        execute(_options(output), live=True, caller=caller)
    assert len(calls) == 1


def test_keyboard_interrupt_keeps_attempt_inflight_and_blocks_resume(tmp_path):
    output = tmp_path / "run"
    calls = []

    def caller(*args):
        calls.append(1)
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        execute(_options(output), live=True, caller=caller)
    with pytest.raises(ValueError, match="Unresolved call"):
        execute(_options(output), live=True, caller=caller)
    assert len(calls) == 1


def test_invalid_reference_keeps_raw_provider_response(tmp_path):
    response = _response(bad_reference=True)
    result = execute(_options(tmp_path / "run"), live=True, caller=lambda *args: response)
    saved = result["results"][0]["result"]
    assert result["statuses"]["invalid"] == 1
    assert saved["raw_response"] == response["raw_response"]
    assert "target_ids" in saved["validation_error"]
