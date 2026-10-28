"""Readable evidence remains a reversible view of exact immutable source text."""

import json
from pathlib import Path

import pytest
from lxml import html
from streamlit.testing.v1 import AppTest

from congressional_globe import review_readable
from congressional_globe.review_models import ReviewPacket
from congressional_globe.review_notes import evidence_note_id
from congressional_globe.review_readable import (
    evidence_digest,
    readable_view,
    show_readable_evidence,
)
from congressional_globe.review_store import ReviewStore


def _packet():
    return ReviewPacket.model_validate_json(Path("docs/review-packets/HR-010-v1.json").read_text())


def _index():
    return _packet().questions[1].evidence[0]


def test_all_nine_presentations_match_original_evidence_and_source_ranges():
    packet = _packet()
    for question in packet.questions:
        for item in question.evidence:
            assert readable_view(item) is not None
    view = readable_view(_index())
    assert view is not None
    assert len(view.groups) == 3
    assert [len(group.lines) for group in view.groups] == [1, 32, 1]
    assert "outside this crop" in view.groups[0].title
    line = view.groups[0].lines[0]
    assert _index().text[line.start : line.end].startswith("Fortifications, bill")


@pytest.mark.parametrize(
    "field,value", [("text", "Changed"), ("label", "Changed"), ("url", "https://example.org/")]
)
def test_changed_evidence_identity_does_not_reuse_a_readable_view(field, value):
    item = _index()
    changed = item.model_validate({**item.model_dump(mode="json"), field: value})
    assert readable_view(changed) is None


@pytest.mark.parametrize("mutation", ["omit", "reorder", "extend"])
def test_source_slices_cannot_be_omitted_reordered_or_extended(tmp_path, monkeypatch, mutation):
    data = json.loads(review_readable.CATALOG.read_text())
    lines = data["evidence"][evidence_digest(_index())]["groups"][1]["lines"]
    if mutation == "omit":
        lines.pop()
    elif mutation == "reorder":
        lines[0], lines[1] = lines[1], lines[0]
    else:
        lines[0]["end"] += 1
    path = tmp_path / "readable.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(review_readable, "CATALOG", path)
    with pytest.raises(ValueError, match="preserve every"):
        readable_view(_index())
    assert not show_readable_evidence(_index(), "invalid", [])


def test_pairs_include_rejected_no_op_without_creating_a_reading():
    item = _packet().questions[1].evidence[1]
    view = readable_view(item)
    assert view is not None
    assert len(view.groups) == 8
    sixth = view.groups[5]
    assert "unchanged" in sixth.title
    old, new = sixth.lines
    assert item.text[old.start : old.end] == item.text[new.start : new.end]
    assert "rejected" in view.explanation
    assert "none of these proposals was applied" in view.explanation


def _setup(tmp_path, monkeypatch):
    path = tmp_path / "review.sqlite"
    monkeypatch.setenv("GLOBE_REVIEW_DATABASE", str(path))
    store = ReviewStore(path)
    store.register(_packet())
    return store


def _app():
    return AppTest.from_string("from congressional_globe.review_app import main\nmain()").run()


def test_original_details_plain_spans_and_notes_remain_accessible(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    app = _app()
    assert not app.exception
    assert _details_count(app) == 9
    assert len(app.text_area) == 11
    tree = _rendered_tree(app)
    assert not tree.xpath('.//span[@class="review-source-text"]//button')
    assert tree.xpath('.//button[@aria-label="Define: fingerprints"]')
    assert any("response provenance" in x.value for x in app.markdown)


def _details_count(app):
    return len([x for x in app.expander if x.label == "Original evidence and technical details"])


def _rendered_tree(app):
    return html.fragment_fromstring("\n".join(x.value for x in app.markdown), create_parent="div")


def test_presentation_keeps_note_identity_draft_reload_and_packet_bytes(tmp_path, monkeypatch):
    store = _setup(tmp_path, monkeypatch)
    packet = store.get_packet("HR-010", 1)
    item = _packet().questions[1].evidence[0]
    key = evidence_note_id("sample-b-grade", 0, item)
    app = _app()
    app.text_input(key="reviewer").set_value("Synthetic tester").run()
    note = next(x for x in app.text_area if key in x.key)
    note.set_value("Index context needs explanation")
    saves = [x for x in app.button if x.label == "Save draft here"]
    saves[5].click().run()
    draft = store.get_draft("HR-010", 1, "Synthetic tester")
    assert draft["answers"][key] == "Index context needs explanation"
    reopened = _app()
    reopened.text_input(key="reviewer").set_value("Synthetic tester").run()
    assert (
        next(x for x in reopened.text_area if key in x.key).value
        == "Index context needs explanation"
    )
    assert packet == store.get_packet("HR-010", 1)
    assert store.submissions() == []


def test_unavailable_card_is_informational_without_changing_question():
    packet = _packet()
    question = packet.questions[-1]
    view = readable_view(question.evidence[0])
    assert view is not None
    assert not question.required
    assert "nothing to grade" in view.explanation
    assert not view.original_body
    assert not view.show_scan


def test_history_note_labels_use_short_titles_without_changing_note_keys():
    packet = _packet()
    labels = review_readable.readable_answer_labels(packet)
    item = packet.questions[1].evidence[0]
    key = evidence_note_id("sample-b-grade", 0, item)
    assert labels[key] == "Your note · Sample B · original index text"
    assert labels["sample-b-grade"] == packet.questions[1].prompt


def test_history_labels_reject_real_question_and_generated_note_collision():
    packet = _packet()
    item = packet.questions[1].evidence[0]
    key = evidence_note_id("sample-b-grade", 0, item)
    data = packet.model_dump(mode="json")
    data["questions"].append({"id": key, "prompt": "Real question", "required": False})
    with pytest.raises(ValueError, match="collide"):
        review_readable.readable_answer_labels(ReviewPacket.model_validate(data))
