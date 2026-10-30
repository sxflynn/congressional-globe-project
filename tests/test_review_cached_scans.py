"""A real cached scan and matching OCR remain verifiable in desk walkthroughs."""

import json
import shutil

import pytest
from lxml import html
from streamlit.testing.v1 import AppTest

from congressional_globe import review_cached_scans, review_scans, scan_fetch
from congressional_globe.review_cached_scans import CachedReviewScan, _entry, _view
from congressional_globe.review_evidence import evidence_html
from congressional_globe.review_models import ReviewPacket
from congressional_globe.review_store import ReviewStore


def _scan():
    catalog = json.loads(review_cached_scans.CATALOG.read_text())
    return CachedReviewScan.model_validate(catalog["scans"][0])


def test_cached_review_image_uses_verified_existing_bytes_without_download(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Image display must not fetch or run a model")

    monkeypatch.setattr(scan_fetch, "build_opener", forbidden)
    entry = _scan()
    payload, source, width = _view(entry)
    assert scan_fetch.digest(payload) == entry.image_sha256
    assert width == 1012
    assert source.endswith("/congressionalglo7392unit/page/n328/mode/1up")


@pytest.mark.parametrize(
    "change",
    [
        {"bundle_sha256": "0" * 64},
        {"raw_sha256": "0" * 64},
        {"source_id": "wrong-source"},
        {"image_sha256": "0" * 64},
        {"directory": "../outside-artifacts"},
    ],
)
def test_cached_review_image_rejects_wrong_identity_or_path(change):
    with pytest.raises(ValueError):
        _view(_scan().model_copy(update=change))


def test_cached_review_image_rejects_tampered_bytes(tmp_path, monkeypatch):
    entry = _scan()
    directory = tmp_path / entry.directory
    shutil.copytree(review_cached_scans.ROOT / entry.directory, directory)
    with (directory / "crop-01.jpg").open("ab") as image:
        image.write(b"changed")
    monkeypatch.setattr(review_cached_scans, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="URL/size mismatch"):
        _view(entry)


def test_duplicate_cache_entries_cannot_silently_choose_an_image(tmp_path, monkeypatch):
    entry = _scan()
    catalog = tmp_path / "cache.json"
    catalog.write_text(json.dumps({"version": 1, "scans": [entry.model_dump(mode="json")] * 2}))
    monkeypatch.setattr(review_cached_scans, "CATALOG", catalog)
    with pytest.raises(ValueError, match="Multiple"):
        _entry(str(entry.source_url))


def test_unverified_cache_shows_warning_without_rendering_remote_image(monkeypatch):
    messages, links = [], []

    def invalid(_):
        raise ValueError("wrong image")

    monkeypatch.setattr(review_scans, "show_cached_scan", invalid)
    monkeypatch.setattr(review_scans.st, "warning", messages.append)
    monkeypatch.setattr(review_scans.st, "link_button", lambda label, url: links.append(url))
    review_scans.show_inline_scan(str(_scan().source_url))
    assert messages == ["The saved image could not be verified. Use the original image link."]
    assert links == [str(_scan().source_url)]


def test_walkthrough_keeps_exact_raw_ocr_and_all_reading_examples_plain():
    packet = ReviewPacket.model_validate_json(
        (review_cached_scans.ROOT / "docs/review-packets/HR-011-v2.json").read_text()
    )
    source = json.loads(
        (review_cached_scans.ROOT / "docs/review-packets/HR-011-v2-sources.json").read_text()
    )
    evidence = packet.questions[0].evidence
    assert evidence[2].text == source["raw_text"]
    assert scan_fetch.digest(evidence[2].text.encode()) == source["raw_sha256"]
    assert source["walkthrough_focus"]["raw_quote"] == "GCO"
    assert source["illustrative_preview"] == source["raw_text"].replace("GCO", "660")
    for index, item in enumerate(evidence):
        tree = html.fragment_fromstring(
            evidence_html(item.text, f"walkthrough-{index}"), create_parent="div"
        )
        assert not tree.xpath('.//span[@class="review-source-text"]//button')
        for popup in tree.xpath(".//*[@popover]"):
            popup.drop_tree()
        assert tree.text_content() == item.text


def _raw_position(nodes, raw):
    return next(
        i
        for i, node in enumerate(nodes)
        if node.type == "markdown" and raw in getattr(node, "value", "")
    )


def test_walkthrough_renders_cached_images_before_raw_ocr(tmp_path, monkeypatch):
    database = tmp_path / "reviews.sqlite"
    monkeypatch.setenv("GLOBE_REVIEW_DATABASE", str(database))
    packet = ReviewPacket.model_validate_json(
        (review_cached_scans.ROOT / "docs/review-packets/HR-011-v2.json").read_text()
    )
    ReviewStore(database).register(packet)
    app = AppTest.from_string("from congressional_globe.review_app import main\nmain()").run()
    app.text_input(key="reviewer").set_value("Synthetic reviewer").run()
    assert not app.exception
    assert len(app.get("image")) == 2
    assert len(app.get("link_button")) == 4
    nodes = list(app)
    image_positions = [i for i, node in enumerate(nodes) if node.type == "image"]
    raw = packet.questions[0].evidence[2].text
    raw_position = _raw_position(nodes, raw)
    assert max(image_positions) < raw_position
    rendered = "\n".join(item.value for item in app.markdown)
    assert "2 · Actual" in rendered
    assert "GCO" in rendered
    assert "This is a real saved" in rendered
