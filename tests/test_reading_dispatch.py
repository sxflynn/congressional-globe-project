from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from congressional_globe import reading_dispatch as dispatcher
from congressional_globe import reading_requests as requests
from congressional_globe.reading_contracts import ReadingCandidate, ReadingParagraph, text_hash
from congressional_globe.reading_controls import make_control
from congressional_globe.reading_dispatch import (
    RequestReadiness,
    RuntimeCheck,
    _task_id,
    dispatch,
)
from congressional_globe.reading_run_store import ReadingRunStore


def _setup(tmp_path):
    paragraph = ReadingParagraph(
        item_identifier="congressionalg7391unit",
        part_number=1,
        scan_leaf=1,
        printed_page={},
        reading_order=0,
        paragraph_id="dispatch-target",
        hocr_page_id="page1",
        line_ids=[],
        bbox=None,
        raw="A short historical passage.",
        raw_sha256=text_hash("A short historical passage."),
        static="A short historical passage.",
        static_sha256=text_hash("A short historical passage."),
        static_patches=[],
    )
    unit = ReadingCandidate(
        id="dispatch-unit",
        part_number=1,
        stratum="ordinary",
        split="primary",
        target=[paragraph],
        selection_reason="synthetic transport proof",
    )
    image_path = tmp_path / "crop.jpg"
    image_path.write_bytes(b"verified synthetic image")
    image = requests.ImageInput(
        id="crop",
        path=image_path,
        sha256=requests.digest(image_path.read_bytes()),
        sources=[
            dict(
                source_id=paragraph.source_id,
                raw_sha256=paragraph.raw_sha256,
                start=0,
                end=len(paragraph.raw),
            )
        ],
    )
    record = requests.describe_request(
        unit,
        [image],
        next(iter(requests.SUPPORTED_MODELS)),
        "prompt",
        {"type": "object"},
        requests.RequestOptions(),
    )
    record.update(token_fit="verified", launch_ready=True)
    ready = RequestReadiness(
        request_sha256=record["request_sha256"],
        model_digest=record["model_digest"],
        token_fit_sha256="a" * 64,
        source_expectation_sha256="b" * 64,
        review_effort_sha256="c" * 64,
        expected_input_tokens=12,
        token_fit_verified=True,
        source_expectations_frozen=True,
        review_effort_resolved=True,
    )
    runtime = RuntimeCheck(
        checked_at=datetime.now(UTC),
        runtime_version="test-ollama",
        process_state_verified=True,
        process_observation_sha256="d" * 64,
        model_digests={record["model"]: record["model_digest"]},
    )
    store = ReadingRunStore(
        tmp_path / "run.sqlite",
        {"run_id": "dispatch-test", "model": record["model"]},
        [
            {
                "task_id": _task_id(record),
                "request_sha256": record["request_sha256"],
                "model_digest": record["model_digest"],
            }
        ],
    )
    return unit, record, ready, runtime, store


@contextmanager
def _response(value: str):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return value.encode()

    yield Response()


def _reply(record):
    source = json.loads(record["messages_without_image_payloads"][1]["content"])["target"][0]
    body = {"unit_id": record["unit_id"], "status": "unchanged", "patches": [], "uncertain": []}
    if record.get("control_kind"):
        body.update(
            status="needs_review",
            uncertain=[
                {
                    "source_id": source["source_id"],
                    "start": 0,
                    "end": len(source["raw"]),
                    "reason": "The supplied source image does not support a reading.",
                }
            ],
        )
    payload = {
        "model": record["model"],
        "done": True,
        "done_reason": "stop",
        "message": {
            "role": "assistant",
            "content": json.dumps(body),
        },
        "prompt_eval_count": 12,
        "eval_count": 8,
        "total_duration": 1000,
    }
    return json.dumps(payload)


def _call(store, unit, record, ready, runtime, opener, stop_file=None):
    return dispatch(
        store=store,
        records=[record],
        units={unit.id: unit},
        readiness={_task_id(record): ready},
        runtime=runtime,
        base_url="http://localhost:11434",
        opt_in=True,
        opener=opener,
        lock_factory=lambda: _response("unused"),
        stop_file=stop_file,
    )


def _other_request(tmp_path, unit, record):
    paragraph = unit.target[0].model_copy(update={"paragraph_id": "unrelated-source"})
    other_unit = unit.model_copy(update={"id": "unrelated-unit", "target": [paragraph]})
    image_path = tmp_path / "unrelated.jpg"
    image_path.write_bytes(b"another verified source image")
    image = requests.ImageInput(
        id="unrelated-crop",
        path=image_path,
        sha256=requests.digest(image_path.read_bytes()),
        sources=[
            dict(
                source_id=paragraph.source_id,
                raw_sha256=paragraph.raw_sha256,
                start=0,
                end=len(paragraph.raw),
            )
        ],
    )
    return requests.describe_request(
        other_unit,
        [image],
        record["model"],
        "prompt",
        {"type": "object"},
        requests.RequestOptions(),
    )


def test_dispatch_persists_exact_request_and_raw_full_reply_before_reopen(tmp_path):
    unit, record, ready, runtime, store = _setup(tmp_path)
    seen = []

    def opener(request, timeout):
        seen.append((request.full_url, request.data, timeout))
        return _response(_reply(record))

    result = _call(store, unit, record, ready, runtime, opener)
    assert result[0]["status"] == "valid"
    assert result[0]["derived"][unit.target[0].source_id]["text"] == unit.target[0].raw
    assert seen[0][0].endswith("/api/chat")
    assert json.loads(seen[0][1])["model"] == record["model"]
    assert seen[0][2] <= 120
    attempt_id = result[0]["attempt_id"]
    store.close()

    reopened = ReadingRunStore(
        tmp_path / "run.sqlite",
        {"run_id": "dispatch-test", "model": record["model"]},
        [
            {
                "task_id": _task_id(record),
                "request_sha256": record["request_sha256"],
                "model_digest": record["model_digest"],
            }
        ],
    )
    attempt = reopened.attempt(attempt_id)
    assert attempt["status"] == "valid"
    assert attempt["raw_reply"] == _reply(record)
    assert json.loads(attempt["raw_reply"])["prompt_eval_count"] == 12
    assert attempt["usage"]["eval_count"] == 8
    timing = reopened.timing_summary()
    assert timing["calls"] == 1
    assert timing["models"][record["model"]]["calls"] == 1
    assert timing["models"][record["model"]]["seconds"] > 0
    assert (
        _call(
            reopened,
            unit,
            record,
            ready,
            runtime,
            lambda *_args, **_kwargs: pytest.fail("terminal task was called"),
        )
        == []
    )
    reopened.close()


def test_dispatch_requires_opt_in_and_every_readiness_dimension(tmp_path):
    unit, record, ready, runtime, store = _setup(tmp_path)
    with pytest.raises(ValueError, match="opt_in"):
        dispatch(
            store, [record], {unit.id: unit}, {unit.id: ready}, runtime, "http://localhost:11434"
        )
    unready = ready.model_copy(update={"review_effort_resolved": False})
    with pytest.raises(ValueError, match="verified"):
        _call(store, unit, record, unready, runtime, lambda *_a, **_k: None)
    with pytest.raises(ValueError, match="token fit"):
        _call(
            store, unit, {**record, "token_fit": "unknown"}, ready, runtime, lambda *_a, **_k: None
        )
    store.close()


def test_timeout_is_inflight_and_never_retried_on_resume(tmp_path):
    unit, record, ready, runtime, store = _setup(tmp_path)
    calls = 0

    def timeout(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise TimeoutError("request outcome unknown")

    result = _call(store, unit, record, ready, runtime, timeout)
    assert result[0]["status"] == "timeout"
    assert store.summary()["inflight"] == 1
    attempt = store.attempt(result[0]["attempt_id"])
    assert attempt["raw_reply"] is None
    assert attempt["usage"] is None
    assert json.loads(attempt["detail"])["transport_error"] == "request outcome unknown"
    with pytest.raises(ValueError, match="unresolved"):
        _call(store, unit, record, ready, runtime, timeout)
    assert calls == 1
    store.close()


def test_prompt_token_mismatch_is_saved_and_halts_batch(tmp_path):
    unit, record, ready, runtime, store = _setup(tmp_path)
    payload = json.loads(_reply(record))
    payload["prompt_eval_count"] = 13
    raw = json.dumps(payload)
    result = _call(store, unit, record, ready, runtime, lambda *_a, **_k: _response(raw))
    assert result[0]["status"] == "invalid"
    assert result[0]["halt_batch"] is True
    assert "parity mismatch" in result[0]["detail"]
    attempt = store.attempt(result[0]["attempt_id"])
    assert attempt["raw_reply"] == raw
    assert attempt["usage"]["prompt_eval_count"] == 13
    assert "parity mismatch" in attempt["detail"]
    store.close()


def test_stop_file_after_response_prevents_next_call_and_persists_report(tmp_path):
    unit, first, first_ready, runtime, store = _setup(tmp_path)
    store.close()
    second = _other_request(tmp_path, unit, first)
    second.update(token_fit="verified", launch_ready=True)
    paragraph = unit.target[0].model_copy(update={"paragraph_id": "unrelated-source"})
    second_unit = unit.model_copy(update={"id": second["unit_id"], "target": [paragraph]})
    second_ready = first_ready.model_copy(update={"request_sha256": second["request_sha256"]})
    records = [first, second]
    units = {unit.id: unit, second_unit.id: second_unit}
    readiness = {
        _task_id(first): first_ready,
        _task_id(second): second_ready,
    }
    tasks = [
        {
            "task_id": _task_id(record),
            "request_sha256": record["request_sha256"],
            "model_digest": record["model_digest"],
        }
        for record in records
    ]
    store = ReadingRunStore(
        tmp_path / "stop-run.sqlite", {"run_id": "stop-test", "model": first["model"]}, tasks
    )
    stop_file = tmp_path / "STOP"
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        stop_file.write_text("stop after this response")
        return _response(_reply(first))

    result = dispatch(
        store,
        records,
        units,
        readiness,
        runtime,
        "http://localhost:11434",
        opt_in=True,
        opener=opener,
        lock_factory=lambda: _response("unused"),
        stop_file=stop_file,
    )
    assert [item["status"] for item in result] == ["valid", "stopped"]
    assert len(calls) == 1
    assert store.summary()["pending"] == 1
    assert store.stop_reports() == [
        {"reason": "stop_file_present", "stop_file": str(stop_file), "pending_tasks": 1}
    ]
    store.close()


def test_second_process_blocks_unknown_timeout_without_duplicate_call(tmp_path):
    unit, record, ready, runtime, store = _setup(tmp_path)
    timed_out = _call(
        store,
        unit,
        record,
        ready,
        runtime,
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("unknown outcome")),
    )[0]
    assert store.attempt(timed_out["attempt_id"])["status"] == "inflight"
    store.close()

    unit_path = tmp_path / "unit.json"
    record_path = tmp_path / "record.json"
    ready_path = tmp_path / "ready.json"
    runtime_path = tmp_path / "runtime.json"
    marker = tmp_path / "transport-called"
    unit_path.write_text(unit.model_dump_json())
    record_path.write_text(json.dumps(record))
    ready_path.write_text(ready.model_dump_json())
    runtime_path.write_text(runtime.model_dump_json())
    script = """
import json, sys
from contextlib import nullcontext
from pathlib import Path
from congressional_globe.reading_contracts import ReadingCandidate
from congressional_globe.reading_dispatch import RuntimeCheck, RequestReadiness, _task_id, dispatch
from congressional_globe.reading_run_store import ReadingRunStore
root = Path(sys.argv[1])
unit = ReadingCandidate.model_validate_json((root / 'unit.json').read_text())
record = json.loads((root / 'record.json').read_text())
ready = RequestReadiness.model_validate_json((root / 'ready.json').read_text())
runtime = RuntimeCheck.model_validate_json((root / 'runtime.json').read_text())
store = ReadingRunStore(root / 'run.sqlite', {'run_id': 'dispatch-test', 'model': record['model']},
    [{'task_id': _task_id(record), 'request_sha256': record['request_sha256'],
      'model_digest': record['model_digest']}])
def opener(*args, **kwargs):
    (root / 'transport-called').write_text('duplicate')
    raise AssertionError('must not make a second transport call')
try:
    dispatch(store, [record], {unit.id: unit}, {_task_id(record): ready}, runtime,
        'http://localhost:11434', opt_in=True, opener=opener, lock_factory=nullcontext)
except ValueError as error:
    if 'unresolved' not in str(error):
        raise
else:
    raise AssertionError('unresolved timeout did not block resume')
store.close()
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")
    child = subprocess.run([sys.executable, "-c", script, str(tmp_path)], env=env, check=False)
    assert child.returncode == 0
    assert not marker.exists()


@pytest.mark.parametrize("kind", ["missing_image", "unrelated_image"])
def test_controls_require_full_target_uncertainty_and_never_receive_coverage(tmp_path, kind):
    unit, primary, ready, runtime, store = _setup(tmp_path)
    store.close()
    unrelated = _other_request(tmp_path, unit, primary) if kind == "unrelated_image" else None
    record = make_control(primary, kind, unrelated)
    ready = ready.model_copy(update={"request_sha256": record["request_sha256"]})
    task = {
        "task_id": _task_id(record),
        "request_sha256": record["request_sha256"],
        "model_digest": record["model_digest"],
    }
    store = ReadingRunStore(
        tmp_path / f"{kind}.sqlite", {"run_id": kind, "model": record["model"]}, [task]
    )
    result = _call(store, unit, record, ready, runtime, lambda *_a, **_k: _response(_reply(record)))
    assert result[0]["status"] == "valid"
    assert result[0]["control_result"] == "passed"
    assert result[0]["derived"][unit.target[0].source_id]["uncertain"][0]["end"] == len(
        unit.target[0].raw
    )
    store.close()


def test_inflight_attempt_blocks_dispatch_before_transport(tmp_path):
    unit, record, ready, runtime, store = _setup(tmp_path)
    store.claim(_task_id(record), json.loads(requests.materialize_record(record)))
    with pytest.raises(ValueError, match="unresolved"):
        _call(
            store,
            unit,
            record,
            ready,
            runtime,
            lambda *_a, **_k: pytest.fail("inflight journal must block transport"),
        )
    store.close()


def test_stale_or_unverified_runtime_blocks_dispatch(tmp_path):
    unit, record, ready, runtime, store = _setup(tmp_path)
    old = runtime.model_copy(update={"checked_at": datetime(2000, 1, 1, tzinfo=UTC)})
    with pytest.raises(ValueError, match="stale"):
        _call(store, unit, record, ready, old, lambda *_a, **_k: None)
    unknown = runtime.model_copy(update={"process_state_verified": False})
    with pytest.raises(ValueError, match="process/queue"):
        _call(store, unit, record, ready, unknown, lambda *_a, **_k: None)
    store.close()


def test_output_truncation_cannot_mask_input_count_mismatch():
    record = dict(model="model", options=dict(num_ctx=16384, num_predict=4096))
    reply = dict(
        model="model", done=True, done_reason="length", prompt_eval_count=21, eval_count=4096
    )
    with pytest.raises(dispatcher._InputParityError, match="parity"):
        dispatcher._validate_response(reply, record, 20)


def test_quote_v2_derives_positions_then_uses_unchanged_host_guards(tmp_path):
    unit, record, ready, runtime, store = _setup(tmp_path)
    record["response_contract"] = "quote-v2"
    response = json.loads(_reply(record))
    response["message"]["content"] = json.dumps(
        dict(
            unit_id=unit.id,
            status="proposed",
            patches=[
                dict(
                    source_id=unit.target[0].source_id,
                    old="short",
                    new="brief",
                    image_ids=["crop"],
                    reason="Synthetic test",
                )
            ],
            uncertain=[],
        )
    )
    results = _call(
        store, unit, record, ready, runtime, lambda *args, **kwargs: _response(json.dumps(response))
    )
    assert results[0]["status"] == "valid"
    assert results[0]["reply"]["patches"][0]["start"] == 2
    store.close()
