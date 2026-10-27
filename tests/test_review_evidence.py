from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from lxml import html
from streamlit.testing.v1 import AppTest

from congressional_globe import review_evidence
from congressional_globe.review_evidence import SourceSpan, _render_parts, evidence_html
from congressional_globe.review_glossary import definitions
from congressional_globe.review_store import ReviewStore


def _tree(rendered):
    return html.fragment_fromstring(rendered, create_parent="div")


def _visible_text(tree):
    for popup in tree.xpath(".//*[@popover]"):
        popup.drop_tree()
    return tree.text_content()


def test_mixed_explanation_keeps_help_but_historical_words_are_plain():
    packet = json.loads(Path("docs/review-packets/HR-010-v1.json").read_text())
    question = packet["questions"][0]
    text = question["evidence"][0]["text"]
    tree = _tree(evidence_html(text, "mixed", packet["glossary"]))
    quotes = tree.xpath('.//span[@class="review-source-text"]')
    assert len(quotes) == 2
    assert all(not quote.xpath(".//button") for quote in quotes)
    assert all("broom corn" in quote.text_content() for quote in quotes)
    assert tree.xpath('.//button[@aria-label="Define: Original OCR"]')
    assert tree.xpath('.//button[@aria-label="Define: Proposed reading"]')
    assert _visible_text(tree) == text


def test_rejected_reply_explanation_retains_glossary_and_old_new_words_stay_plain():
    packet = json.loads(Path("docs/review-packets/HR-010-v1.json").read_text())
    text = packet["questions"][1]["evidence"][1]["text"]
    tree = _tree(evidence_html(text, "rejected", packet["glossary"]))
    assert tree.xpath('.//button[@aria-label="Define: rejected"]')
    assert tree.xpath('.//button[@aria-label="Define: complete proposed reading"]')
    assert len(tree.xpath('.//span[@class="review-source-text"]')) == 16
    assert not tree.xpath('.//span[@class="review-source-text"]//button')
    assert _visible_text(tree) == text


@pytest.mark.parametrize("packet_id", ["HR-004", "HR-010"])
def test_all_registered_historical_passages_use_exact_plain_spans(packet_id):
    packet = json.loads(Path(f"docs/review-packets/{packet_id}-v1.json").read_text())
    items = [item for question in packet["questions"] for item in question["evidence"]]
    presentation = json.loads(review_evidence.SOURCE_PRESENTATION.read_text())["source_spans"]
    for index, item in enumerate(items):
        _check_plain_spans(item["text"], presentation, str(index))


def _check_plain_spans(text, presentation, scope):
    tree = _tree(evidence_html(text, scope))
    spans = presentation.get(hashlib.sha256(text.encode()).hexdigest(), [])
    assert [node.text_content() for node in tree.xpath('.//span[@class="review-source-text"]')] == [
        text[span["start"] : span["end"]] for span in spans
    ]
    assert not tree.xpath('.//span[@class="review-source-text"]//button')
    assert _visible_text(tree) == text


def test_entire_historical_passage_is_plain_even_when_terms_are_in_catalog():
    packet = json.loads(Path("docs/review-packets/HR-004-v1.json").read_text())
    text = packet["questions"][0]["evidence"][0]["text"]
    tree = _tree(evidence_html(text, "original"))
    assert tree.xpath('.//span[@class="review-source-text"]')[0].text_content() == text
    assert not tree.xpath(".//button")


def test_plain_source_is_escaped_and_surrounding_explanation_keeps_help():
    text = "OCR: <script>tariff</script> provenance"
    start, end = text.index("<"), text.rindex(">") + 1
    tree = _tree(_render_parts(text, [SourceSpan(start=start, end=end)], definitions(), "escape"))
    assert not tree.xpath(".//script")
    assert not tree.xpath('.//span[@class="review-source-text"]//button')
    assert tree.xpath('.//button[@aria-label="Define: provenance"]')
    assert _visible_text(tree) == text


@pytest.mark.parametrize("text", ["A tariff bill with <script>OCR</script>.", "The duty changed."])
def test_unclassified_evidence_stays_plain_by_default(text):
    tree = _tree(evidence_html(text, "unclassified"))
    assert not tree.xpath(".//button | .//script")
    assert tree.text_content() == text


def test_changed_mixed_evidence_cannot_inherit_old_source_boundaries():
    packet = json.loads(Path("docs/review-packets/HR-010-v1.json").read_text())
    text = packet["questions"][0]["evidence"][0]["text"] + " changed"
    tree = _tree(evidence_html(text, "changed"))
    assert not tree.xpath(".//button")
    assert tree.text_content() == text


@pytest.mark.parametrize("spans", [[(2, 2)], [(2, 30)], [(2, 5), (4, 6)], [(4, 6), (1, 2)]])
def test_invalid_source_ranges_cannot_render_wrong_content(spans):
    with pytest.raises(ValueError, match="ordered, disjoint and within"):
        _render_parts(
            "OCR tariff", [SourceSpan(start=a, end=b) for a, b in spans], definitions(), "bad"
        )


def test_live_packet_app_keeps_ai_question_help_and_plain_source(tmp_path, monkeypatch):
    database = tmp_path / "review.sqlite"
    monkeypatch.setenv("GLOBE_REVIEW_DATABASE", str(database))
    packet = json.loads(Path("docs/review-packets/HR-010-v1.json").read_text())
    ReviewStore(database).register(packet)
    app = AppTest.from_string("from congressional_globe.review_app import main\nmain()").run()
    tree = _tree("\n".join(item.value for item in app.markdown))
    assert not app.exception
    assert tree.xpath('.//button[@aria-label="Define: paragraph boundaries"]')
    assert tree.xpath('.//button[@aria-label="Define: rejected"]')
    assert tree.xpath('.//span[@class="review-source-text"]')
    assert not tree.xpath('.//span[@class="review-source-text"]//button')
    assert not tree.xpath('.//button[@aria-label="Define: broom corn"]')
