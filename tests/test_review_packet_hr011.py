"""HR-011 design prose has help while illustrative readings remain plain."""

import json
from pathlib import Path

import pytest
from lxml import html

from congressional_globe.review_evidence import evidence_html
from congressional_globe.review_glossary import annotated_html, definitions
from congressional_globe.review_models import ReviewPacket


def test_hr011_packet_preserves_design_scope_and_plain_illustrative_readings():
    packet = ReviewPacket.model_validate_json(
        Path("docs/review-packets/HR-011-v1.json").read_text()
    )
    evidence = packet.questions[0].evidence[3]
    tree = html.fragment_fromstring(
        evidence_html(evidence.text, "hr011-example"), create_parent="div"
    )
    spans = tree.xpath('.//span[@class="review-source-text"]')
    assert [node.text_content() for node in spans] == ["The year was 1866.", "The year was 1865."]
    assert not tree.xpath('.//span[@class="review-source-text"]//button')
    assert tree.xpath('.//button[@aria-label="Define: exact quote"]')
    assert tree.xpath('.//button[@aria-label="Define: source binding"]')
    for popup in tree.xpath(".//*[@popover]"):
        popup.drop_tree()
    assert tree.text_content() == evidence.text
    assert packet.questions[0].options[-1] == "Not reviewed"
    assert sum(question.required for question in packet.questions) == 1


@pytest.mark.parametrize(
    ("text", "term"),
    [
        ("image-only readings", "image-only reading"),
        ("combined repair and audit", "combined repair and audit"),
        ("No findings", "no finding"),
        ("independent workflow evaluations", "independent workflow evaluation"),
    ],
)
def test_hr011_shared_glossary_aliases_and_longest_phrases(text, term):
    tree = html.fragment_fromstring(
        annotated_html(text, definitions(), "hr011-help"), create_parent="div"
    )
    assert tree.xpath('.//button[@class="glossary-term"]/text()') == [text]
    assert tree.xpath('.//*[@role="dialog"]/@aria-label') == [term]


def test_hr011_evidence_explanations_all_have_glossary_help():
    packet = json.loads(Path("docs/review-packets/HR-011-v1.json").read_text())
    evidence = [item for question in packet["questions"] for item in question["evidence"]]
    for index, item in enumerate(evidence):
        tree = html.fragment_fromstring(
            evidence_html(item["text"], f"hr011-{index}"), create_parent="div"
        )
        assert tree.xpath('.//button[@class="glossary-term"]')
        for popup in tree.xpath(".//*[@popover]"):
            popup.drop_tree()
        assert tree.text_content() == item["text"]
