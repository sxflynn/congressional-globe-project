from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from lxml import html

from congressional_globe.review_glossary import annotated_html, definitions
from congressional_globe.review_models import ReviewPacket
from congressional_globe.review_store import ReviewStore


def test_literal_matching_longest_phrase_case_and_escaped_content():
    rendered = annotated_html(
        "<script>alert(1)</script> STATIC CLEANUP; cleanupx; raw OCR.", definitions(), "test"
    )
    tree = html.fragment_fromstring(rendered, create_parent="div")
    assert not tree.xpath(".//script")
    labels = tree.xpath('.//button[@class="glossary-term"]/text()')
    assert labels == ["STATIC CLEANUP", "raw OCR"]
    assert "<script>" in tree.text_content()
    assert len(tree.xpath('.//*[@popover="auto"]')) == 2
    assert not tree.xpath('.//button[not(@type="button")]')


def test_repeated_terms_have_distinct_targets_across_fields():
    rendered = annotated_html("OCR OCR", definitions(), "first")
    rendered += annotated_html("OCR", definitions(), "second")
    tree = html.fragment_fromstring(rendered, create_parent="div")
    targets = tree.xpath('.//button[@class="glossary-term"]/@popovertarget')
    assert len(set(targets)) == 3
    assert set(targets) == set(tree.xpath(".//*[@popover]/@id"))


def test_custom_definitions_are_escaped_and_override_shared_meaning():
    entries = definitions(
        [
            {
                "term": "OCR",
                "definition": "<img src=x onerror=alert(1)>",
                "aliases": ["reading machine"],
            }
        ]
    )
    tree = html.fragment_fromstring(
        annotated_html("OCR reading machine", entries, "custom"), create_parent="div"
    )
    assert not tree.xpath(".//img")
    assert len(tree.xpath(".//*[@popover]")) == 2
    assert "<img src=x" in tree.text_content()


def test_old_registered_packets_keep_their_exact_hashes(tmp_path):
    store = ReviewStore(tmp_path / "reviews.sqlite")
    expected = {
        "HR-003": "d24bdfd502063ce392c84990bdc78023d829d7c5573176933f0e1c4623e7d12b",
        "HR-004": "4f46eaf3b9e8565909b52ac3114bd53690adb4c3007b805be83fdd384cf1f7b6",
    }
    for packet_id, digest in expected.items():
        packet = json.loads(Path(f"docs/review-packets/{packet_id}-v1.json").read_text())
        assert store.register(packet)["packet_sha256"] == digest


def test_packet_glossary_is_validated_hashed_and_exported(tmp_path):
    packet = json.loads(Path("docs/review-packets/HR-003-v1.json").read_text())
    original = ReviewPacket.model_validate(packet).model_dump(mode="json")
    assert "glossary" not in original
    packet["glossary"] = [{"term": "pilot", "definition": "A small trial.", "aliases": ["trial"]}]
    store = ReviewStore(tmp_path / "reviews.sqlite")
    saved = store.register(packet)
    assert saved["glossary"] == packet["glossary"]
    answers = {q["id"]: q["options"][0] for q in packet["questions"] if q["required"]}
    submitted = store.submit("HR-003", 1, "Synthetic test", answers)
    exported = store.export(submitted["submission_id"])
    assert exported["packet"]["glossary"] == packet["glossary"]
    payload = exported["packet_snapshot"]["packet_json"]
    assert hashlib.sha256(payload.encode()).hexdigest() == saved["packet_sha256"]
    packet["glossary"].append({"term": "TRIAL", "definition": "Conflicting alias"})
    with pytest.raises(ValueError, match="unique"):
        ReviewPacket.model_validate(packet)


def test_shared_catalog_names_are_unambiguous_and_definitions_are_nonblank():
    from congressional_globe.review_glossary import CATALOG, GlossaryCatalog

    catalog = GlossaryCatalog.model_validate_json(CATALOG.read_text())
    names = [name.casefold() for entry in catalog.terms for name in [entry.term, *entry.aliases]]
    assert len(names) == len(set(names))
    assert all(len(entry.definition) > 30 for entry in catalog.terms)


def test_review_vocabulary_and_historical_phrases_have_neutral_help():
    entries = definitions()
    text = (
        "Paragraph boundaries; fixed selection; raw reply; provenance; faithful; "
        "automated validation; complete proposed reading; source-boundary issue; "
        "prohibitory tariff; broom corn; tub to the whale; the hammer fell; "
        "franking privilege; H. R. No.; S. No."
    )
    tree = html.fragment_fromstring(annotated_html(text, entries, "expanded"), create_parent="div")
    labels = tree.xpath('.//button[@class="glossary-term"]/text()')
    assert labels == text.split("; ")
    assert "without changing its wording or meaning" in entries["faithful"].definition
    assert "not" in entries["automated validation"].definition


def test_distinct_meanings_and_longest_phrase_preserve_source_words():
    entries = definitions()
    assert entries["json"] != entries["schema"]
    assert entries["imports"] != entries["importers"]
    assert entries["habeas corpus"] != entries["corpus"]
    source = "Imports and importers; habeas corpus. [Here the hammer fell.] A mere blind."
    tree = html.fragment_fromstring(annotated_html(source, entries, "source"), create_parent="div")
    assert tree.xpath('.//button[@class="glossary-term"]/text()') == [
        "Imports",
        "importers",
        "habeas corpus",
        "Here the hammer fell",
        "mere blind",
    ]
    for popup in tree.xpath(".//*[@popover]"):
        popup.drop_tree()
    assert tree.text_content() == source
    assert "blind" not in entries
    assert "blind review" in entries
