from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from congressional_globe.review_models import ReviewPacket
from congressional_globe.review_store import ReviewStore


def _packet(version: int = 1) -> ReviewPacket:
    return ReviewPacket.model_validate(
        {
            "id": "HR-demo",
            "version": version,
            "title": "A review",
            "instructions": "Read the evidence and answer.",
            "blind": True,
            "questions": [
                {
                    "id": "decision",
                    "prompt": "Which label fits?",
                    "options": ["yes", "no"],
                    "required": True,
                    "evidence": [
                        {
                            "label": "Source",
                            "text": "L\u2019émigré—café.",
                            "url": "https://example.org",
                        }
                    ],
                },
                {"id": "comment", "prompt": "Anything else?", "required": False},
            ],
        }
    )


def test_packet_registration_is_hashed_immutable_and_versioned(tmp_path):
    store = ReviewStore(tmp_path / "reviews.sqlite")
    first = store.register(_packet())
    same = store.register(_packet())
    assert first["packet_sha256"] == same["packet_sha256"]
    packet = store.get_packet("HR-demo")
    assert packet is not None
    assert packet["packet_sha256"] == first["packet_sha256"]
    assert [packet["version"] for packet in store.packets()] == [1]

    changed = _packet().model_copy(update={"title": "Changed"})
    with pytest.raises(ValueError, match="different content"):
        store.register(changed)
    store.register(_packet(version=2))
    latest = store.get_packet("HR-demo")
    assert latest is not None
    assert latest["version"] == 2
    with pytest.raises(ValueError, match="stale"):
        store.save_draft("HR-demo", 1, "Reviewer", {"decision": "yes"})


def test_draft_persists_partial_answers_and_validates_question_options(tmp_path):
    store = ReviewStore(tmp_path / "reviews.sqlite")
    store.register(_packet())
    saved = store.save_draft("HR-demo", 1, " Reviewer ", {"comment": "Still considering"})
    assert saved["reviewer"] == "Reviewer"
    draft = store.get_draft("HR-demo", 1, "Reviewer")
    assert draft is not None
    assert draft["answers"] == {"comment": "Still considering"}
    with pytest.raises(ValueError, match="unknown question"):
        store.save_draft("HR-demo", 1, "Reviewer", {"unknown": "x"})
    with pytest.raises(ValueError, match="listed option"):
        store.save_draft("HR-demo", 1, "Reviewer", {"decision": "maybe"})


def test_submit_is_idempotent_and_changed_answer_appends_revision(tmp_path):
    path = tmp_path / "reviews.sqlite"
    store = ReviewStore(path)
    store.register(_packet())
    first = store.submit("HR-demo", 1, "Reviewer", {"decision": "yes"}, "note")
    repeated = store.submit("HR-demo", 1, "Reviewer", {"decision": "yes"}, "note")
    revised = store.submit("HR-demo", 1, "Reviewer", {"decision": "no"}, "note")
    assert repeated["submission_id"] == first["submission_id"]
    assert revised["revision"] == 2
    assert [row["revision"] for row in store.submissions()] == [1, 2]

    reopened = ReviewStore(path)
    assert reopened.export(first["submission_id"])["submission"]["answers"] == {"decision": "yes"}
    with pytest.raises(ValueError, match="required answers"):
        reopened.submit("HR-demo", 1, "Another", {}, None)
    with pytest.raises(ValueError, match="listed option"):
        reopened.submit("HR-demo", 1, "Another", {"decision": "perhaps"})


def test_reverting_to_earlier_answers_appends_new_current_revision(tmp_path):
    store = ReviewStore(tmp_path / "reviews.sqlite")
    store.register(_packet())
    first_a = store.submit("HR-demo", 1, "Reviewer", {"decision": "yes"})
    store.submit("HR-demo", 1, "Reviewer", {"decision": "no"})
    reverted_a = store.submit("HR-demo", 1, "Reviewer", {"decision": "yes"})
    repeated_a = store.submit("HR-demo", 1, "Reviewer", {"decision": "yes"})
    assert reverted_a["revision"] == 3
    assert reverted_a["submission_id"] != first_a["submission_id"]
    assert repeated_a["submission_id"] == reverted_a["submission_id"]
    assert [item["superseded"] for item in store.submissions()] == [True, True, False]


def test_submit_clears_draft_and_later_draft_remains_independent(tmp_path):
    store = ReviewStore(tmp_path / "reviews.sqlite")
    store.register(_packet())
    store.save_draft("HR-demo", 1, "Reviewer", {"decision": "yes"})
    submitted = store.submit("HR-demo", 1, "Reviewer", {"decision": "yes"})
    assert store.get_draft("HR-demo", 1, "Reviewer") is None
    store.save_draft("HR-demo", 1, "Reviewer", {"decision": "no"})
    draft = store.get_draft("HR-demo", 1, "Reviewer")
    assert draft is not None
    assert draft["answers"] == {"decision": "no"}
    repeated = store.submit("HR-demo", 1, "Reviewer", {"decision": "yes"})
    assert repeated["submission_id"] == submitted["submission_id"]
    assert store.get_draft("HR-demo", 1, "Reviewer") is None


def test_applied_receipt_is_immutable_idempotent_and_pending_filters(tmp_path):
    store = ReviewStore(tmp_path / "reviews.sqlite")
    store.register(_packet())
    submission = store.submit("HR-demo", 1, "Reviewer", {"decision": "yes"})
    applied = store.mark_applied(submission["submission_id"], "commit:abc123")
    assert applied["applied"] is True
    assert store.mark_applied(submission["submission_id"], "commit:abc123") == applied
    assert (
        store.export(submission["submission_id"])["applied_receipt"]["reference"] == "commit:abc123"
    )
    assert store.submissions(pending_only=True) == []
    with pytest.raises(ValueError, match="different applied receipt"):
        store.mark_applied(submission["submission_id"], "commit:def456")
    with pytest.raises(KeyError, match="unknown submission"):
        store.export("missing")


def test_export_contains_exact_packet_snapshot_submission_and_receipt(tmp_path):
    store = ReviewStore(tmp_path / "reviews.sqlite")
    registered = store.register(_packet())
    submission = store.submit(
        "HR-demo", 1, "Reviewer", {"decision": "yes", "comment": "café — naïve"}, "résumé"
    )
    applied = store.mark_applied(submission["submission_id"], "archive:HR-demo-v1")
    exported = store.export(submission["submission_id"])
    packet_json = exported["packet_snapshot"]["packet_json"]
    assert hashlib.sha256(packet_json.encode("utf-8")).hexdigest() == registered["packet_sha256"]
    assert "L\u2019émigré—café." in packet_json
    assert json.loads(packet_json) == exported["packet"]
    assert exported["submission"]["answers"]["comment"] == "café — naïve"
    assert exported["submission"]["notes"] == "résumé"
    payload_json = json.dumps(
        {"answers": exported["submission"]["answers"], "notes": "résumé"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert (
        hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        == exported["submission"]["payload_sha256"]
    )
    assert exported["applied_receipt"]["reference"] == applied["applied_reference"]


def test_concurrent_identical_submissions_create_one_revision(tmp_path):
    store = ReviewStore(tmp_path / "reviews.sqlite")
    store.register(_packet())

    def submit_once(_: int) -> dict:
        return store.submit("HR-demo", 1, "Reviewer", {"decision": "yes"})

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit_once, range(16)))
    assert len({result["submission_id"] for result in results}) == 1
    assert len(store.submissions()) == 1


def test_revised_submission_supersedes_old_in_pending_inbox(tmp_path):
    store = ReviewStore(tmp_path / "reviews.sqlite")
    store.register(_packet())
    first = store.submit("HR-demo", 1, "Reviewer", {"decision": "yes"})
    second = store.submit("HR-demo", 1, "Reviewer", {"decision": "no"})
    all_revisions = store.submissions()
    assert [item["superseded"] for item in all_revisions] == [True, False]
    assert [item["submission_id"] for item in store.submissions(pending_only=True)] == [
        second["submission_id"]
    ]
    assert first["submission_id"] != second["submission_id"]
    with pytest.raises(ValueError, match="superseded submission"):
        store.mark_applied(first["submission_id"], "archive:old")
