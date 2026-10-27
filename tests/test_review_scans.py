from __future__ import annotations

import pytest
from lxml import html
from test_review_app import _app, _store

from congressional_globe.review_scans import scan_disclosure, scan_image_url


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "https://example.org/page.jpg",
        "https://archive.org/details/example",
        "https://iiif.archive.org.evil/a.jpg",
    ],
)
def test_non_image_citations_never_become_scan_images(url):
    assert scan_image_url(url) is None


def test_page_reference_resolves_same_item_and_leaf():
    assert scan_image_url(
        "https://archive.org/details/congressionalglo7392unit/page/n1009/mode/1up"
    ) == ("https://iiif.archive.org/iiif/congressionalglo7392unit$1009/full/full/0/default.jpg")


def test_official_crop_stays_exact_and_disclosure_is_closed_and_clickable():
    url = "https://iiif.archive.org/image/iiif/2/example/full/945,/0/default.jpg"
    markup = scan_disclosure(url)
    assert markup is not None
    assert '<details class="globe-scan">' in markup
    assert "<summary>Show original scan</summary>" in markup
    assert " open" not in markup.split("<summary>")[0]
    assert f'<a href="{url}" target="_blank" rel="noopener noreferrer"><img' in markup
    assert 'loading="lazy"' in markup


def test_scan_markup_escapes_url_attributes():
    markup = scan_disclosure('https://iiif.archive.org/a.jpg?x=" onerror="bad')
    assert markup is not None
    assert "&quot;" in markup
    assert 'x=" onerror="' not in markup


def test_passage_precedes_inline_scan_and_source_tab_removed(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    packet = store.get_packet("DEMO-TEST", 1)
    assert packet is not None
    packet.pop("packet_sha256")
    packet["version"] = 2
    packet["questions"][0]["evidence"] = [
        {
            "label": "Synthetic UI source",
            "text": "Text before image.",
            "url": "https://archive.org/details/example/page/n12/mode/1up",
        }
    ]
    store.register(packet)
    app = _app()
    assert not app.exception
    assert app.radio[0].options == ["Pending", "Submitted", "History"]
    rendered = "\n".join(item.value for item in app.markdown)
    visible_text = html.fragment_fromstring(rendered, create_parent="div").text_content()
    assert visible_text.index("Text before image.") < visible_text.index("Show original scan")
    assert 'target="_blank"' in rendered
