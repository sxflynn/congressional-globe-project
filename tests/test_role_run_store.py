import pytest

from congressional_globe.role_run_store import RoleRunStore


def _store(path, packets=None, config=None):
    return RoleRunStore(
        path,
        config or {"model": "fixture", "temperature": 0},
        packets or [{"window_id": "w1", "text": "one"}, {"window_id": "w2", "text": "two"}],
    )


def test_compatible_resume_skips_finished_task(tmp_path):
    path = tmp_path / "run.sqlite"
    store = _store(path)
    attempt = store.start("w1")
    store.finish(attempt, {"raw_reply": "{}", "usage": {"total": 1}}, "valid")
    store.close()

    resumed = _store(path)
    assert resumed.next_pending() == {"window_id": "w2", "text": "two"}
    assert resumed.summary() == {
        "statuses": {
            "pending": 1,
            "inflight": 0,
            "valid": 1,
            "invalid": 0,
            "error": 0,
            "unresolved": 0,
        },
        "attempts": 1,
    }
    assert resumed.results() == [
        {
            "window_id": "w1",
            "status": "valid",
            "result": {"raw_reply": "{}", "usage": {"total": 1}},
        }
    ]
    resumed.close()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"config": {"model": "different", "temperature": 0}},
        {"packets": [{"window_id": "w1", "text": "changed"}, {"window_id": "w2", "text": "two"}]},
        {"packets": [{"window_id": "w2", "text": "two"}, {"window_id": "w1", "text": "one"}]},
    ],
)
def test_incompatible_resume_is_rejected(tmp_path, kwargs):
    path = tmp_path / "run.sqlite"
    _store(path).close()
    with pytest.raises(ValueError, match="identity"):
        _store(path, **kwargs)


def test_unresolved_interrupted_attempt_is_never_pending(tmp_path):
    store = _store(tmp_path / "run.sqlite")
    attempt = store.start("w1")
    assert store.mark_interrupted() == 1
    assert store.next_pending() == {"window_id": "w2", "text": "two"}
    with pytest.raises(ValueError, match="not pending"):
        store.start("w1")
    assert store.results() == [
        {
            "window_id": "w1",
            "status": "unresolved",
            "result": {"error": "interrupted; outcome unknown"},
        }
    ]
    with pytest.raises(ValueError, match="no longer inflight"):
        store.finish(attempt, {"raw_reply": "late"}, "valid")
    store.close()


def test_only_current_inflight_attempt_can_finish(tmp_path):
    store = _store(tmp_path / "run.sqlite")
    with pytest.raises(ValueError, match="not pending"):
        store.start("absent")
    attempt = store.start("w1")
    with pytest.raises(ValueError, match="terminal"):
        store.finish(attempt, {}, "pending")
    store.finish(attempt, {"error": "bad JSON"}, "error")
    with pytest.raises(ValueError, match="no longer inflight"):
        store.finish(attempt, {}, "valid")
    store.close()
