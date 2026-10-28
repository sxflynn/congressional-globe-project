"""Evidence-local notes retain exact bindings through the ordinary review lifecycle."""

import pytest
from streamlit.testing.v1 import AppTest

from congressional_globe.review_models import ReviewPacket
from congressional_globe.review_notes import evidence_note_id, evidence_note_questions
from congressional_globe.review_store import ReviewStore


def _setup(tmp_path, monkeypatch):
    path = tmp_path / "notes.sqlite"
    monkeypatch.setenv("GLOBE_REVIEW_DATABASE", str(path))
    store = ReviewStore(path)
    packet = ReviewPacket.model_validate(
        {
            "id": "NOTE-TEST",
            "version": 1,
            "title": "Invented example",
            "instructions": "Practice only.",
            "questions": [
                {
                    "id": "reading",
                    "prompt": "Check the invented text",
                    "options": ["Unclear", "Reviewed"],
                    "evidence": [
                        {"label": "First example", "text": "re- gard"},
                        {"label": "Second example", "text": "Other invented text"},
                    ],
                }
            ],
        }
    )
    store.register(packet)
    return store, packet


def _app():
    return AppTest.from_string("from congressional_globe.review_app import main\nmain()").run()


def test_nearby_save_retains_all_notes_and_unfinished_review_after_reload(tmp_path, monkeypatch):
    store, packet = _setup(tmp_path, monkeypatch)
    app = _app()
    app.text_input(key="reviewer").set_value("Synthetic tester").run()
    app.text_area[0].set_value("The split word was left unchanged")
    app.text_area[1].set_value("Separate note for second example")
    app.button[0].click().run()
    assert not app.exception
    saved = store.get_draft(packet.id, 1, "Synthetic tester")
    keys = list(evidence_note_questions(packet))
    assert saved["answers"][keys[0]] == "The split word was left unchanged"
    assert saved["answers"][keys[1]] == "Separate note for second example"
    assert saved["answers"]["reading"] == ""
    reopened = _app()
    reopened.text_input(key="reviewer").set_value("Synthetic tester").run()
    assert reopened.text_area[0].value == saved["answers"][keys[0]]
    assert reopened.text_area[1].value == saved["answers"][keys[1]]
    assert not store.submissions()


def test_notes_submit_export_and_revision_preserve_old_answers(tmp_path, monkeypatch):
    store, packet = _setup(tmp_path, monkeypatch)
    key = next(iter(evidence_note_questions(packet)))
    with pytest.raises(ValueError, match="required answers"):
        store.submit(packet.id, 1, "Synthetic tester", {key: "Only a note"})
    first = store.submit(
        packet.id, 1, "Synthetic tester", {"reading": "Unclear", key: "First note"}
    )
    second = store.submit(
        packet.id, 1, "Synthetic tester", {"reading": "Reviewed", key: "Revised note"}
    )
    assert store.export(first["submission_id"])["submission"]["answers"][key] == "First note"
    assert store.export(second["submission_id"])["submission"]["answers"][key] == "Revised note"
    assert store.get_packet(packet.id, 1)["packet_sha256"] == first["packet_sha256"]


@pytest.mark.parametrize("change", ["text", "label", "url", "index", "question"])
def test_note_identity_rejects_different_evidence(tmp_path, monkeypatch, change):
    store, packet = _setup(tmp_path, monkeypatch)
    item = packet.questions[0].evidence[0]
    changes = {"text": "Different", "label": "Different", "url": "https://example.org/image"}
    changed = (
        item.model_validate({**item.model_dump(mode="json"), change: changes[change]})
        if change in changes
        else item
    )
    key = evidence_note_id(
        "other" if change == "question" else "reading", 99 if change == "index" else 0, changed
    )
    with pytest.raises(ValueError, match="unknown question"):
        store.save_draft(packet.id, 1, "Synthetic tester", {key: "Should not bind"})


def test_each_note_and_save_button_immediately_follows_its_evidence(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    app = _app()
    nodes = list(app)
    textareas = [i for i, node in enumerate(nodes) if node.type == "text_area"]
    saves = _save_positions(nodes)
    evidence = _evidence_positions(nodes)
    assert evidence[0] < textareas[0] < saves[0] < evidence[1] < textareas[1] < saves[1]


def _save_positions(nodes):
    return [
        i
        for i, node in enumerate(nodes)
        if node.type == "button" and node.label == "Save draft here"
    ]


def _evidence_positions(nodes):
    return [
        i
        for i, node in enumerate(nodes)
        if node.type == "markdown" and "review-source-text" in node.value
    ]


def test_real_question_cannot_override_evidence_note_validation(tmp_path, monkeypatch):
    store, packet = _setup(tmp_path, monkeypatch)
    key = next(iter(evidence_note_questions(packet)))
    payload = packet.model_dump(mode="json")
    payload["version"] = 2
    payload["questions"].append(
        {"id": key, "prompt": "A required choice", "options": ["Only allowed"]}
    )
    store.register(payload)
    with pytest.raises(ValueError, match="collide"):
        store.save_draft(packet.id, 2, "Synthetic tester", {key: "arbitrary"})


def test_agent_inbox_labels_each_comment_and_preserves_it_verbatim(tmp_path, monkeypatch):
    store, packet = _setup(tmp_path, monkeypatch)
    key = next(iter(evidence_note_questions(packet)))
    comment = " It did not fix re- gard.\nPlease check this specific word. "
    store.submit(packet.id, 1, "Synthetic tester", {"reading": "Unclear", key: comment})
    row = store.submissions(pending_only=True)[0]
    feedback = row["evidence_feedback"][0]
    assert feedback["comment"] == comment
    assert feedback["question_id"] == "reading"
    assert feedback["item_number"] == 1
    assert feedback["evidence"]["text"] == "re- gard"
    assert feedback["evidence"]["label"] == "First example"
    assert store.export(row["submission_id"])["submission"]["evidence_feedback"] == [feedback]
    assert not row["applied"]
