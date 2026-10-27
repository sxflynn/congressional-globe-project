"""Fresh-process interruption checks for the existing metadata job path."""

import hashlib
import json
import runpy
import signal
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from congressional_globe.role_run_store import RoleRunStore

HELPERS = runpy.run_path(str(Path(__file__).with_name("test_metadata_runner.py")))
WORKER = r"""
import json,os,signal,sys
from pathlib import Path
from congressional_globe.role_run_io import RunOptions
from congressional_globe.role_run_store import RoleRunStore
from congressional_globe import role_runner
options=RunOptions.model_validate_json(Path(sys.argv[1]).read_text())
mode=sys.argv[2]
replies=json.loads((options.output.parent/'replies.json').read_text())
def kill():os.kill(os.getpid(),signal.SIGKILL)
def caller(packet,prompt,schema):
    with (options.output.parent/'sent.txt').open('a') as stream:
        stream.write(packet['window_id']+'\n');stream.flush();os.fsync(stream.fileno())
    if mode=='ambiguous':kill()
    return replies[packet['window_id']]
def install(name,when):
    original=getattr(RoleRunStore,name)
    def hooked(self,*args,**kwargs):
        if when=='before':kill()
        value=original(self,*args,**kwargs)
        kill()
        return value
    setattr(RoleRunStore,name,hooked)
if mode=='before_claim':install('start','before')
if mode=='claimed':install('start','after')
if mode=='saved_reply':install('record_response','after')
if mode=='finished':install('finish','after')
try:
    result=role_runner.execute(options,live=True,caller=caller)
    (options.output.parent/'result.json').write_text(json.dumps(result))
except Exception as error:
    (options.output.parent/'pickup-error.txt').write_text(type(error).__name__+': '+str(error))
    sys.exit(2)
"""


def _job(tmp_path):
    cases = HELPERS["_date_cases"]()
    options = HELPERS["_prepared"](tmp_path, "scoped-date-v1", [c["packet"] for c in cases])
    (tmp_path / "options.json").write_text(options.model_dump_json())
    replies = {c["case_id"]: HELPERS["_response"](c["result"]) for c in cases}
    (tmp_path / "replies.json").write_text(json.dumps(replies))
    return options


def _process(tmp_path, mode):
    result = subprocess.run(
        [sys.executable, "-c", WORKER, str(tmp_path / "options.json"), mode],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
    )
    observation = {"mode": mode, "returncode": result.returncode, "stderr": result.stderr}
    with (tmp_path / "process-observations.jsonl").open("a") as stream:
        stream.write(json.dumps(observation) + "\n")
    return result


def _sent(tmp_path):
    path = tmp_path / "sent.txt"
    return path.read_text().splitlines() if path.exists() else []


def _rows(options, query):
    with sqlite3.connect(options.output / "jobs.sqlite") as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(query)]


@pytest.mark.parametrize("checkpoint", ["before_claim", "saved_reply", "finished"])
def test_fresh_process_recovers_without_duplicate_sends(tmp_path, checkpoint):
    options = _job(tmp_path)
    killed = _process(tmp_path, checkpoint)
    assert killed.returncode == -signal.SIGKILL
    resumed = _process(tmp_path, "resume")
    assert resumed.returncode == 0, resumed.stderr
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["statuses"]["valid"] == result["attempts"] == 2
    assert len(_sent(tmp_path)) == len(set(_sent(tmp_path))) == 2
    assert result["cumulative_usage"]["input_tokens"] == 200
    assert result["cumulative_usage"]["output_tokens"] == 20
    assert result["cumulative_usage"]["unknown_usage"] == 0
    checkpoints = _rows(options, "SELECT * FROM attempt_checkpoints")
    assert all(row["response_json"] is not None for row in checkpoints)
    for row in checkpoints:
        assert hashlib.sha256(row["response_json"].encode()).hexdigest() == row["response_sha256"]


@pytest.mark.parametrize("checkpoint,expected_sends", [("claimed", 0), ("ambiguous", 1)])
def test_fresh_process_ambiguous_attempt_blocks_all_new_sends(tmp_path, checkpoint, expected_sends):
    options = _job(tmp_path)
    assert _process(tmp_path, checkpoint).returncode == -signal.SIGKILL
    assert _process(tmp_path, "resume").returncode == 2
    assert "Unresolved call" in (tmp_path / "pickup-error.txt").read_text()
    assert len(_sent(tmp_path)) == expected_sends
    assert len(_rows(options, "SELECT * FROM attempts")) == 1


def test_saved_unknown_usage_recovers_answer_but_blocks_next_call(tmp_path):
    options = _job(tmp_path)
    path = tmp_path / "replies.json"
    replies = json.loads(path.read_text())
    replies[next(iter(replies))]["usage"] = None
    path.write_text(json.dumps(replies))
    assert _process(tmp_path, "saved_reply").returncode == -signal.SIGKILL
    assert _process(tmp_path, "resume").returncode == 0
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["statuses"]["valid"] == result["statuses"]["pending"] == 1
    assert result["cumulative_usage"]["unknown_usage"] == 1
    assert len(_sent(tmp_path)) == 1
    assert _rows(options, "SELECT response_json FROM attempt_checkpoints")[0]["response_json"]


@pytest.mark.parametrize("column", ["request_json", "response_json"])
def test_saved_checkpoint_mutation_refuses_before_send(tmp_path, column):
    options = _job(tmp_path)
    assert _process(tmp_path, "saved_reply").returncode == -signal.SIGKILL
    with sqlite3.connect(options.output / "jobs.sqlite") as db:
        db.execute(f"UPDATE attempt_checkpoints SET {column}=?", ("{}",))
    assert _process(tmp_path, "resume").returncode == 2
    assert "hash mismatch" in (tmp_path / "pickup-error.txt").read_text()
    assert len(_sent(tmp_path)) == 1


def test_elapsed_budget_survives_process_restart(tmp_path):
    options = _job(tmp_path)
    assert _process(tmp_path, "saved_reply").returncode == -signal.SIGKILL
    with sqlite3.connect(options.output / "jobs.sqlite") as db:
        db.execute("UPDATE attempt_checkpoints SET elapsed_seconds=?", (options.max_seconds,))
    assert _process(tmp_path, "resume").returncode == 0
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["statuses"]["pending"] == 1
    assert result["cumulative_usage"]["seconds"] == options.max_seconds
    assert len(_sent(tmp_path)) == 1


def test_unknown_elapsed_is_not_guessed_during_saved_reply_recovery(tmp_path):
    options = _job(tmp_path)
    assert _process(tmp_path, "saved_reply").returncode == -signal.SIGKILL
    with sqlite3.connect(options.output / "jobs.sqlite") as db:
        db.execute("UPDATE attempt_checkpoints SET elapsed_seconds=NULL")
    assert _process(tmp_path, "resume").returncode == 0
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["cumulative_usage"]["unknown_elapsed"] == 1
    assert result["results"][0]["result"]["elapsed_seconds"] is None
    assert len(_sent(tmp_path)) == 1


def test_legacy_database_rejected_without_schema_or_byte_changes(tmp_path):
    path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE run_identity(singleton INTEGER)")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="legacy role journal schema"):
        RoleRunStore(path, {}, [{"window_id": "w1"}])
    assert path.read_bytes() == before


def test_request_response_and_usage_cannot_be_changed_through_store(tmp_path):
    path = tmp_path / "jobs.sqlite"
    request = {"packet": {"window_id": "w1"}}
    digest = hashlib.sha256(
        json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    store = RoleRunStore(path, {"request_hashes": {"w1": digest}}, [{"window_id": "w1"}])
    with pytest.raises(ValueError, match="request identity"):
        store.start("w1", {"packet": "different"})
    attempt = store.start("w1", request)
    response = HELPERS["_response"]({"speaker_roles": []})
    store.record_response(attempt, response, 0.5)
    with pytest.raises(ValueError, match="immutable"):
        store.record_response(attempt, {**response, "usage": None}, 0.5)
    with pytest.raises(ValueError, match="saved response must be validated"):
        store.mark_interrupted()
    with pytest.raises(ValueError, match="cannot replace"):
        store.finish(attempt, {"raw_response": "changed"}, "valid")
    store.close()


def test_invalid_cached_usage_cannot_produce_negative_spending(tmp_path):
    _job(tmp_path)
    path = tmp_path / "replies.json"
    replies = json.loads(path.read_text())
    replies[next(iter(replies))]["usage"]["cached_input_tokens"] = 101
    path.write_text(json.dumps(replies))
    assert _process(tmp_path, "resume").returncode == 0
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["cumulative_usage"]["unknown_usage"] == 1
    assert result["api_cost_usd_estimate"] is None
    assert len(_sent(tmp_path)) == 1


def test_terminal_usage_mutation_cannot_understate_paid_budget(tmp_path):
    options = _job(tmp_path)
    assert _process(tmp_path, "finished").returncode == -signal.SIGKILL
    with sqlite3.connect(options.output / "jobs.sqlite") as db:
        row = db.execute("SELECT result_json FROM attempts").fetchone()
        changed = json.loads(row[0])
        changed["usage"]["input_tokens"] = 0
        db.execute("UPDATE attempts SET result_json=?", (json.dumps(changed),))
    assert _process(tmp_path, "resume").returncode == 2
    assert "terminal result hash mismatch" in (tmp_path / "pickup-error.txt").read_text()
    assert len(_sent(tmp_path)) == 1


def test_recovered_invalid_reply_keeps_batch_stopped(tmp_path):
    _job(tmp_path)
    path = tmp_path / "replies.json"
    replies = json.loads(path.read_text())
    replies[next(iter(replies))] = HELPERS["_response"]({"dates": []})
    path.write_text(json.dumps(replies))
    assert _process(tmp_path, "saved_reply").returncode == -signal.SIGKILL
    assert _process(tmp_path, "resume").returncode == 0
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["statuses"]["invalid"] == result["statuses"]["pending"] == 1
    assert len(_sent(tmp_path)) == 1
