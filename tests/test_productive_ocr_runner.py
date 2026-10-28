"""Fake-only productive OCR execution and durable fresh-process recovery."""

import json
import runpy
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes
from congressional_globe.productive_ocr_runner import (
    RunnerContext,
    SessionBounds,
    canonical,
    code_identity,
    execute,
    freeze_job,
)

HOST = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_host.py")))
CONTENTS = [
    "all_words",
    "names_places",
    "numbers",
    "punctuation",
    "printed_repetition",
    "bracketed_cues",
    "target_context_boundaries",
    "unflagged_text",
    "static_edits",
]


def _reply(unit):
    return {
        "contract": "ocr-productive-repair-reply-v2",
        "unit_id": unit,
        "role": "productive_repair_and_self_check",
        "status": "no_finding",
        "inspections": [
            {
                "paragraph_alias": "P1",
                "image_alias": "I1",
                "completeness": "complete",
                "image_suitability": "clear",
                "reason": None,
            }
        ],
        "findings": [],
        "patches": [],
        "reason": None,
        "target_readings": [
            {
                "paragraph_alias": "P1",
                "image_alias": "I1",
                "reading_status": "unchanged",
                "proposed_text": "By Mr. Example.",
                "uncertainties": [],
                "reason": None,
            }
        ],
        "self_check": [
            {
                "paragraph_alias": "P1",
                "coverage": "complete",
                "checked_content": CONTENTS,
                "remaining_concerns": [],
            }
        ],
    }


def _response(unit):
    text = json.dumps(_reply(unit))
    return {
        "status": "completed",
        "finish_reason": None,
        "output_text": text,
        "raw_response": text,
        "usage": {"input_tokens": 2, "output_tokens": 3},
    }


class Call:
    def __init__(self, unit, mode):
        self.unit, self.mode, self.cancelled = unit, mode, False

    def result(self, timeout):
        assert 0 < timeout <= 120
        if self.mode in {"timeout", "unstopped"}:
            raise TimeoutError("invented test timeout")
        response = _response(self.unit)
        if self.mode == "unknown_usage":
            response["usage"] = None
        if self.mode == "invalid":
            response["output_text"] = "{}"
        return response

    def cancel(self):
        self.cancelled = True

    def observe(self):
        return "running" if self.mode == "unstopped" else "stopped"


class Client:
    offline_test_double = True

    def __init__(self, mode="valid", sent=None):
        self.mode, self.calls, self.owned, self.sent = mode, [], [], sent

    def start(self, body):
        packet = json.loads(json.loads(body)["messages"][1]["content"])
        unit = packet["unit_id"]
        self.calls.append(unit)
        if self.sent:
            with self.sent.open("a") as stream:
                stream.write(unit + "\n")
                stream.flush()
        owned = Call(unit, self.mode)
        self.owned.append(owned)
        return owned


def _session(started=None, timeout=120.0):
    packet, registry = HOST["_packet"]({})
    prompt, schema = "Invented offline test prompt", canonical({"type": "object"})
    payload = packet["payload"]
    detector, configuration = b"synthetic detector", b"synthetic configuration"
    for value in (detector, configuration):
        registry.files[sha256_bytes(value)] = value
    payload["diagnostics"] = {
        "status": "frozen",
        "detector_sha256": sha256_bytes(detector),
        "configuration_sha256": sha256_bytes(configuration),
        "signals": [],
        "negative_targets": ["P1"],
    }

    payload["prompt_sha256"] = sha256_bytes(prompt.encode())
    payload["response_schema_sha256"] = sha256_bytes(schema.encode())
    registry.files[payload["prompt_sha256"]] = prompt.encode()
    registry.files[payload["response_schema_sha256"]] = schema.encode()
    bounds = SessionBounds(
        started_at_epoch=started or time.time(),
        max_wall_seconds=1800.0,
        max_request_seconds=840.0,
        timeout_seconds=timeout,
        max_calls=2,
        max_input_tokens=12,
        max_output_tokens=3000,
        per_call_output_tokens=1500,
    )
    for key, value in [
        ("bounds_sha256", canonical(bounds.model_dump(mode="json"))),
        ("code_sha256", canonical(code_identity())),
    ]:
        payload[key] = sha256_bytes(value.encode())
        registry.files[payload[key]] = value.encode()
    jobs = []
    for unit in ["U1", "U2"]:
        payload["unit_id"] = unit
        packet["packet_sha256"] = sha256_bytes(canonical_json(payload))
        job = freeze_job(packet, registry, prompt, schema, "invented-fake-model", 2, "a" * 64)
        fit = {
            "model_name": "invented-fake-model",
            "body_sha256": job.body_sha256,
            "model_digest": payload["model_digest"],
            "input_tokens": 2,
            "output_tokens": 1500,
            "evidence_scope": "synthetic_test",
        }
        encoded = canonical(fit).encode()
        identity = sha256_bytes(encoded)
        registry.files[identity] = encoded
        jobs.append(job.model_copy(update={"token_fit_sha256": identity}))
    return tuple(jobs), registry, bounds


def test_completed_compatible_session_reuses_all_results_without_sends(tmp_path):
    jobs, registry, bounds = _session()
    client = Client()
    first = execute(tmp_path, jobs, bounds, RunnerContext(registry, client))
    assert first["statuses"]["valid"] == 2
    assert client.calls == ["U1", "U2"]
    second = execute(tmp_path, jobs, bounds, RunnerContext(registry, client))
    assert second == first
    assert client.calls == ["U1", "U2"]
    assert first["historical_status"] == "unreviewed_proposals_not_verified_print"


@pytest.mark.parametrize("mode", ["timeout", "unstopped"])
def test_owned_request_timeout_cancels_and_blocks_followup(tmp_path, mode):
    jobs, registry, bounds = _session()
    client = Client(mode)
    result = execute(tmp_path, jobs, bounds, RunnerContext(registry, client))
    assert result["statuses"]["unresolved"] == 1
    assert client.calls == ["U1"]
    assert client.owned[0].cancelled
    assert result["usage"]["unknown_usage"] == 1
    with pytest.raises(ValueError, match="ambiguous"):
        execute(tmp_path, jobs, bounds, RunnerContext(registry, client))
    assert client.calls == ["U1"]


def test_unknown_usage_stops_next_request_without_guessing_zero(tmp_path):
    jobs, registry, bounds = _session()
    client = Client("unknown_usage")
    result = execute(tmp_path, jobs, bounds, RunnerContext(registry, client))
    assert result["usage"]["unknown_usage"] == 1
    assert result["statuses"]["pending"] == 1
    execute(tmp_path, jobs, bounds, RunnerContext(registry, client))
    assert client.calls == ["U1"]


def test_invalid_reply_preserves_raw_and_stops(tmp_path):
    jobs, registry, bounds = _session()
    client = Client("invalid")
    result = execute(tmp_path, jobs, bounds, RunnerContext(registry, client))
    assert result["statuses"]["invalid"] == 1
    assert result["results"][0]["result"]["output_text"] == "{}"
    with pytest.raises(ValueError, match="invalid"):
        execute(tmp_path, jobs, bounds, RunnerContext(registry, client))


def test_elapsed_session_deadline_survives_process_restart(tmp_path):
    jobs, registry, bounds = _session(time.time() - 1790)
    client = Client()
    result = execute(tmp_path, jobs, bounds, RunnerContext(registry, client))
    assert result["attempts"] == 0
    assert not client.calls


def test_foreign_wire_fields_and_changed_journal_identity_refused(tmp_path):
    jobs, registry, bounds = _session()
    job = jobs[0]
    body = json.loads(job.body_utf8)
    body["hidden_oracle"] = "invented expected answer"
    encoded = canonical(body)
    wrong = job.model_copy(
        update={"body_utf8": encoded, "body_sha256": sha256_bytes(encoded.encode())}
    )
    with pytest.raises(ValueError, match="foreign fields"):
        execute(tmp_path, (wrong,), bounds, RunnerContext(registry, Client()))
    execute(tmp_path, jobs, bounds, RunnerContext(registry, Client()))
    with pytest.raises(ValueError, match="identity"):
        execute(tmp_path, jobs[:1], bounds, RunnerContext(registry, Client()))


WORKER = r"""
import json,os,runpy,signal,sys
from pathlib import Path
helper=runpy.run_path(sys.argv[1])
base=Path(sys.argv[2]);mode=sys.argv[3]
from congressional_globe.productive_ocr_runner import execute,RunnerContext
started=float((base/'started.txt').read_text())
jobs,registry,bounds=helper['_session'](started)
def checkpoint(name):
    if name==mode:os.kill(os.getpid(),signal.SIGKILL)
client=helper['Client'](sent=base/'sent.txt')
try:
    result=execute(base/'run',jobs,bounds,RunnerContext(registry,client,checkpoint=checkpoint))
    (base/'result.json').write_text(json.dumps(result))
except Exception as error:
    (base/'error.txt').write_text(str(error));sys.exit(2)
"""


def _process(tmp_path, checkpoint):
    return subprocess.run(
        [sys.executable, "-c", WORKER, __file__, str(tmp_path), checkpoint],
        capture_output=True,
        text=True,
        timeout=20,
    )


@pytest.mark.parametrize("checkpoint", ["before_claim", "after_raw", "after_terminal"])
def test_fresh_process_recovers_saved_results_without_duplicate_sends(tmp_path, checkpoint):
    (tmp_path / "started.txt").write_text(str(time.time()))
    killed = _process(tmp_path, checkpoint)
    assert killed.returncode == -signal.SIGKILL, killed.stderr
    resumed = _process(tmp_path, "resume")
    assert resumed.returncode == 0, resumed.stderr
    assert (tmp_path / "sent.txt").read_text().splitlines() == ["U1", "U2"]
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["statuses"]["valid"] == 2


@pytest.mark.parametrize("checkpoint", ["after_claim", "after_send"])
def test_fresh_process_ambiguous_call_blocks_next_send(tmp_path, checkpoint):
    (tmp_path / "started.txt").write_text(str(time.time()))
    assert _process(tmp_path, checkpoint).returncode == -signal.SIGKILL
    assert _process(tmp_path, "resume").returncode == 2
    assert "ambiguous" in (tmp_path / "error.txt").read_text()
    sent = tmp_path / "sent.txt"
    assert not sent.exists() or sent.read_text().splitlines() == ["U1"]


def test_deadline_expiring_after_claim_never_starts_client(tmp_path):
    jobs, registry, bounds = _session()
    now = [bounds.started_at_epoch]
    client = Client()

    def checkpoint(name):
        if name == "after_claim":
            now[0] += 1801

    result = execute(
        tmp_path,
        jobs,
        bounds,
        RunnerContext(registry, client, clock=lambda: now[0], checkpoint=checkpoint),
    )
    assert not client.calls
    assert result["statuses"]["unresolved"] == 1


def test_duplicate_frozen_ids_rejected_before_journal_creation(tmp_path):
    jobs, registry, bounds = _session()
    with pytest.raises(ValueError, match="duplicate"):
        execute(tmp_path, (jobs[0], jobs[0]), bounds, RunnerContext(registry, Client()))
    assert not (tmp_path / "jobs.sqlite").exists()


class ProcessCall:
    def __init__(self):
        self.process = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
        self.cancelled = False

    def result(self, timeout):
        self.process.wait(timeout=timeout)
        raise AssertionError("long-running owned fake should have timed out")

    def cancel(self):
        self.cancelled = True
        self.process.terminate()
        self.process.wait(timeout=5)

    def observe(self):
        return "stopped" if self.process.poll() is not None else "running"


class ProcessClient:
    offline_test_double = True

    def __init__(self):
        self.owned = []

    def start(self, body):
        owned = ProcessCall()
        self.owned.append(owned)
        return owned


def test_timeout_cancels_actual_owned_fake_process_and_observes_exit(tmp_path):
    jobs, registry, bounds = _session(timeout=0.05)
    client = ProcessClient()
    result = execute(tmp_path, jobs, bounds, RunnerContext(registry, client))
    assert result["statuses"]["unresolved"] == 1
    assert len(client.owned) == 1
    assert client.owned[0].cancelled
    assert client.owned[0].observe() == "stopped"


def test_saved_raw_without_stop_evidence_blocks_recovery_without_resend(tmp_path):
    (tmp_path / "started.txt").write_text(str(time.time()))
    assert _process(tmp_path, "after_raw_before_observation").returncode == -signal.SIGKILL
    assert _process(tmp_path, "resume").returncode == 2
    assert "stop observation missing" in (tmp_path / "error.txt").read_text()
    assert (tmp_path / "sent.txt").read_text().splitlines() == ["U1"]


def test_token_fit_evidence_must_bind_actual_body_and_model(tmp_path):
    jobs, registry, bounds = _session()
    fit = json.loads(registry.files[jobs[0].token_fit_sha256])
    fit["body_sha256"] = "b" * 64
    encoded = canonical(fit).encode()
    identity = sha256_bytes(encoded)
    registry.files[identity] = encoded
    wrong = jobs[0].model_copy(update={"token_fit_sha256": identity})
    with pytest.raises(ValueError, match="token-fit"):
        execute(tmp_path, (wrong,), bounds, RunnerContext(registry, Client()))


def test_raw_reply_saved_before_stop_observation_and_parsing(tmp_path):
    jobs, registry, bounds = _session()
    visited = []

    def checkpoint(name):
        visited.append(name)
        if name == "after_raw_before_observation":
            import sqlite3

            with sqlite3.connect(tmp_path / "jobs.sqlite") as db:
                response = db.execute("SELECT response_json FROM attempt_checkpoints").fetchone()[0]
            assert json.loads(response)["raw_response"] == _response("U1")["raw_response"]

    execute(tmp_path, jobs[:1], bounds, RunnerContext(registry, Client(), checkpoint=checkpoint))
    assert visited.index("after_raw_before_observation") < visited.index("after_raw")


def test_model_name_must_match_frozen_token_fit_identity(tmp_path):
    jobs, registry, bounds = _session()
    fit = json.loads(registry.files[jobs[0].token_fit_sha256])
    fit["model_name"] = "different-fake-model"
    encoded = canonical(fit).encode()
    identity = sha256_bytes(encoded)
    registry.files[identity] = encoded
    wrong = jobs[0].model_copy(update={"token_fit_sha256": identity})
    with pytest.raises(ValueError, match="model name"):
        execute(tmp_path, (wrong,), bounds, RunnerContext(registry, Client()))


def test_backend_observation_crossing_deadline_preserves_raw_and_blocks(tmp_path):
    jobs, registry, bounds = _session()
    now = [bounds.started_at_epoch]

    class DelayedCall(Call):
        def observe(self):
            now[0] += 1801
            return "stopped"

    class DelayedClient(Client):
        def start(self, body):
            self.calls.append("U1")
            return DelayedCall("U1", "valid")

    client = DelayedClient()
    result = execute(tmp_path, jobs, bounds, RunnerContext(registry, client, clock=lambda: now[0]))
    row = result["results"][0]
    assert row["status"] == "unresolved"
    assert not row["result"]["owned_stop_observation"]["within_deadline"]
    assert row["result"]["raw_response"] == _response("U1")["raw_response"]
    assert client.calls == ["U1"]


def test_runner_rejects_client_without_explicit_offline_test_declaration(tmp_path):
    jobs, registry, bounds = _session()
    client = Client()
    client.offline_test_double = False
    with pytest.raises(ValueError, match="offline test doubles only"):
        execute(tmp_path, jobs, bounds, RunnerContext(registry, client))
    assert not client.calls
