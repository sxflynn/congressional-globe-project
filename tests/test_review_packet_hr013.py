"""Recent-work desk preserves the actual failure and permits comments without a run decision."""

import hashlib
import json
from pathlib import Path

from lxml import html

from congressional_globe.review_cached_scans import _entry, _view
from congressional_globe.review_evidence import evidence_html
from congressional_globe.review_glossary import annotated_html, definitions
from congressional_globe.review_models import ReviewPacket
from congressional_globe.review_store import ReviewStore

PACKET = Path("docs/review-packets/HR-013-v1.json")


def test_recent_work_packet_uses_exact_actual_ocr_reply_and_verified_cached_scan():
    packet = ReviewPacket.model_validate_json(PACKET.read_text())
    source = json.loads(PACKET.with_name("HR-013-v1-sources.json").read_text())
    evidence = packet.questions[0].evidence
    assert evidence[1].text == source["raw_text"]
    assert hashlib.sha256(evidence[1].text.encode()).hexdigest() == source["raw_sha256"]
    assert evidence[2].text == source["actual_full_reading"]
    result = json.loads(Path("artifacts/s5-measurement-20261029-01/run/result.json").read_text())
    assert (
        json.loads(result["output_text"])["target_readings"][0]["proposed_text"] == evidence[2].text
    )
    entry = _entry(str(evidence[1].url))
    assert entry is not None
    image, _url, _width = _view(entry)
    assert hashlib.sha256(image).hexdigest() == source["source_image_sha256"]


def test_recent_work_glossary_help_leaves_quotes_and_readings_plain():
    packet = ReviewPacket.model_validate_json(PACKET.read_text())
    for index, evidence in enumerate(packet.questions[0].evidence):
        _check_rendered_evidence(evidence.text, index not in {1, 2})
    _check_rendered_evidence(packet.questions[1].evidence[0].text, True)
    terms = "input-fit exception; complete native input-fit evidence; conditional-schema support"
    tree = html.fragment_fromstring(
        annotated_html(terms, definitions(), "new"), create_parent="div"
    )
    assert tree.xpath('.//button[@class="glossary-term"]/text()') == terms.split("; ")


def _check_rendered_evidence(text, expects_help):
    tree = html.fragment_fromstring(evidence_html(text, "test"), create_parent="div")
    assert not tree.xpath('.//span[@class="review-source-text"]//button')
    assert bool(tree.xpath('.//button[@class="glossary-term"]')) is expects_help


def test_comments_can_be_submitted_without_any_run_decision_in_separate_test_store(tmp_path):
    packet = ReviewPacket.model_validate_json(PACKET.read_text())
    assert not any(question.required for question in packet.questions)
    store = ReviewStore(tmp_path / "reviews.sqlite")
    store.register(json.loads(PACKET.read_text()))
    submitted = store.submit(
        "HR-013", 1, "Synthetic software test", {"work-comments": "Test comment."}
    )
    assert submitted["answers"] == {"work-comments": "Test comment."}
