"""Derived source display is identical to actual model input and fails closed."""

import pytest

from congressional_globe import review_region_scans as scans
from congressional_globe import review_scans


def test_real_derived_display_uses_exact_actual_request_bytes_without_fetch():
    payload, page = scans.verified_region()
    assert (
        payload == (scans.ROOT / "artifacts/exact-region-statute-20261102-01/crop.png").read_bytes()
    )
    assert page.endswith("/page/n741/mode/1up")


def test_display_cites_original_and_reports_derivative_honestly(monkeypatch):
    shown = []
    captions = []
    links = []
    monkeypatch.setattr(scans.st, "image", lambda payload, **kwargs: shown.append(payload))
    monkeypatch.setattr(scans.st, "caption", captions.append)
    monkeypatch.setattr(scans.st, "link_button", lambda label, url: links.append(url))
    assert scans.show_region_scan(scans.REGION_URL)
    assert len(shown) == 1 and "unchanged" in captions[0]
    assert links[0] == scans.PARENT_URL
    assert not scans.show_region_scan(scans.PARENT_URL)


def test_changed_parent_and_changed_crop_fail_closed(monkeypatch):
    original = scans._parent_bytes
    monkeypatch.setattr(scans, "_parent_bytes", lambda: b"changed")
    with pytest.raises(ValueError, match="parent"):
        scans.verified_region()
    monkeypatch.setattr(scans, "_parent_bytes", original)
    monkeypatch.setattr(scans, "CROP_SHA", "0" * 64)
    with pytest.raises(ValueError, match="PNG"):
        scans.verified_region()


def test_inline_error_never_falls_back_to_unverified_network_crop(monkeypatch):
    warnings = []
    links = []

    def invalid(_url):
        raise ValueError("changed")

    monkeypatch.setattr(review_scans, "show_region_scan", invalid)
    monkeypatch.setattr(review_scans.st, "warning", warnings.append)
    monkeypatch.setattr(review_scans.st, "link_button", lambda label, url: links.append(url))
    review_scans.show_inline_scan(scans.REGION_URL)
    assert len(warnings) == 1 and links == [scans.REGION_URL]
