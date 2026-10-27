from __future__ import annotations

import hashlib
import json

from lxml import html
from streamlit.testing.v1 import AppTest

from congressional_globe import review_app, review_evidence
from congressional_globe.review_store import ReviewStore


def _store(tmp_path, monkeypatch) -> ReviewStore:
    database = tmp_path / "reviews.sqlite"
    monkeypatch.setenv("GLOBE_REVIEW_DATABASE", str(database))
    store = ReviewStore(database)
    store.register(
        {
            "id": "DEMO-TEST",
            "version": 1,
            "title": "Synthetic practice",
            "instructions": "Invented text for UI testing.",
            "blind": True,
            "questions": [
                {"id": "choice", "prompt": "Pick one", "options": ["A", "B"]},
                {"id": "comment", "prompt": "Write a note", "options": [], "required": False},
            ],
        }
    )
    return store


def _app() -> AppTest:
    return AppTest.from_string("from congressional_globe.review_app import main\nmain()").run()


def _reviewer(app: AppTest, name: str = "Reviewer One") -> None:
    app.text_input(key="reviewer").set_value(name).run()


def _question_widget(app: AppTest, question_id: str, widgets: str):
    return next(
        widget
        for widget in getattr(app, widgets)
        if widget.key and widget.key.endswith(f"-{question_id}")
    )


def test_draft_survives_new_app_session(tmp_path, monkeypatch) -> None:
    store = _store(tmp_path, monkeypatch)
    app = _app()
    _reviewer(app)
    _question_widget(app, "choice", "selectbox").select("B")
    _question_widget(app, "comment", "text_area").set_value("Keep this note")
    app.button[0].click().run()
    draft = store.get_draft("DEMO-TEST", 1, "Reviewer One")
    assert draft is not None
    assert draft["answers"] == {
        "choice": "B",
        "comment": "Keep this note",
    }

    reopened = _app()
    _reviewer(reopened)
    assert _question_widget(reopened, "choice", "selectbox").value == "B"
    assert _question_widget(reopened, "comment", "text_area").value == "Keep this note"


def test_required_validation_and_free_text_submission(tmp_path, monkeypatch) -> None:
    store = _store(tmp_path, monkeypatch)
    app = _app()
    _reviewer(app)
    app.button[1].click().run()
    assert any("required answers are missing" in item.value for item in app.error)

    _question_widget(app, "choice", "selectbox").select("A")
    _question_widget(app, "comment", "text_area").set_value("Free text answer")
    app.button[1].click().run()
    rows = store.submissions()
    assert len(rows) == 1
    assert rows[0]["answers"] == {"choice": "A", "comment": "Free text answer"}


def test_revision_appends_and_history_keeps_previous_answer(tmp_path, monkeypatch) -> None:
    store = _store(tmp_path, monkeypatch)
    store.submit("DEMO-TEST", 1, "Reviewer One", {"choice": "A", "comment": "First"})
    app = _app()
    app.radio[0].set_value("Submitted").run()
    app.button(key=f"revise-{store.submissions()[0]['submission_id']}").click().run()
    _question_widget(app, "choice", "selectbox").select("B")
    _question_widget(app, "comment", "text_area").set_value("Second")
    app.button[2].click().run()

    rows = store.submissions()
    assert [row["revision"] for row in rows] == [1, 2]
    assert [row["answers"]["choice"] for row in rows] == ["A", "B"]
    app.radio[0].set_value("History").run()
    assert any("revision 1" in item.label for item in app.expander)
    assert any(button.label == "Revise this response" for button in app.button)


def test_duplicate_of_applied_submission_keeps_applied_receipt(tmp_path, monkeypatch) -> None:
    store = _store(tmp_path, monkeypatch)
    row = store.submit("DEMO-TEST", 1, "Reviewer One", {"choice": "A", "comment": ""})
    store.mark_applied(row["submission_id"], "test receipt")
    duplicate = store.submit("DEMO-TEST", 1, "Reviewer One", {"choice": "A", "comment": ""})
    assert duplicate["submission_id"] == row["submission_id"]
    assert "Applied" in review_app._submission_message(duplicate)


def test_same_question_ids_on_two_packets_have_separate_widget_state() -> None:
    first = review_app._widget_prefix("DEMO-TEST", 1, "Reviewer One", "")
    second = review_app._widget_prefix("DEMO-OTHER", 1, "Reviewer One", "")
    assert first != second


def test_history_submission_can_open_revision_form(tmp_path, monkeypatch) -> None:
    store = _store(tmp_path, monkeypatch)
    row = store.submit("DEMO-TEST", 1, "Reviewer One", {"choice": "A", "comment": "First"})
    store.mark_applied(row["submission_id"], "test receipt")
    app = _app()
    app.radio[0].set_value("History").run()
    app.button(key=f"revise-{row['submission_id']}").click().run()
    assert app.text_input(key=f"revision-reviewer-{row['submission_id']}").value == "Reviewer One"
    assert any(button.label == "Submit revision" for button in app.button)


def test_revision_draft_restores_after_new_app_session(tmp_path, monkeypatch) -> None:
    store = _store(tmp_path, monkeypatch)
    row = store.submit("DEMO-TEST", 1, "Reviewer One", {"choice": "A", "comment": "First"})
    app = _app()
    app.radio[0].set_value("Submitted").run()
    app.button(key=f"revise-{row['submission_id']}").click().run()
    _question_widget(app, "choice", "selectbox").select("B")
    _question_widget(app, "comment", "text_area").set_value("Saved revision note")
    app.button[1].click().run()
    draft = store.get_draft("DEMO-TEST", 1, "Reviewer One")
    assert draft is not None
    assert draft["answers"]["choice"] == "B"

    reopened = _app()
    reopened.radio[0].set_value("Submitted").run()
    reopened.button(key=f"revise-{row['submission_id']}").click().run()
    assert _question_widget(reopened, "choice", "selectbox").value == "B"
    assert _question_widget(reopened, "comment", "text_area").value == "Saved revision note"


def test_review_opens_directly_without_access_code(tmp_path, monkeypatch) -> None:
    _store(tmp_path, monkeypatch)
    monkeypatch.delenv("GLOBE_REVIEW_ACCESS_CODE", raising=False)
    app = _app()
    assert app.text_input(key="reviewer").label == "Your name or reviewer ID"
    assert not any(widget.label == "Access code" for widget in app.text_input)
    assert app.selectbox
    assert not app.exception


def test_packet_definitions_render_in_prompts_evidence_and_choice_help(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    presentation = json.loads(review_evidence.SOURCE_PRESENTATION.read_text())
    presentation["source_spans"][hashlib.sha256(b"One widget.").hexdigest()] = []
    classified = tmp_path / "presentation.json"
    classified.write_text(json.dumps(presentation))
    monkeypatch.setattr(review_evidence, "SOURCE_PRESENTATION", classified)
    store.register(
        {
            "id": "DEMO-TEST",
            "version": 2,
            "title": "Definition example",
            "instructions": "Explain a widget.",
            "glossary": [{"term": "widget", "definition": "A small invented test object."}],
            "questions": [
                {
                    "id": "choice",
                    "prompt": "Which widget?",
                    "options": ["widget", "other"],
                    "evidence": [{"label": "Test evidence", "text": "One widget."}],
                }
            ],
        }
    )
    app = _app()
    rendered = "\n".join(item.value for item in app.markdown)
    assert rendered.count("A small invented test object.") == 4
    assert "Answer terms:" in rendered
    assert app.selectbox[-1].options == ["", "widget", "other"]
    assert not app.exception


def test_packet_title_and_version_offer_definitions(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    store.register(
        {
            "id": "DEMO-TEST",
            "version": 2,
            "title": "Provenance check",
            "instructions": "Keep the original wording.",
            "questions": [{"id": "choice", "prompt": "Pick one", "options": ["A", "B"]}],
        }
    )
    app = _app()
    rendered = "\n".join(item.value for item in app.markdown)
    tree = html.fragment_fromstring(rendered, create_parent="div")
    heading = tree.xpath('.//*[@role="heading"]')[0]
    assert heading.get("aria-level") == "3"
    assert heading.xpath('.//button[@aria-label="Define: Provenance"]')
    assert tree.xpath('.//button[@aria-label="Define: version"]')
    assert not app.exception
