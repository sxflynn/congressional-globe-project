from __future__ import annotations

import hashlib
import io
import json
import threading
from typing import Any

import pytest
from PIL import Image, UnidentifiedImageError

from congressional_globe import scan_fetch
from congressional_globe.models import BoundingBox
from congressional_globe.scan_models import CropRegion, ScanTarget

ITEM = "congressionalglo7392unit"
LEAF = 20
INFO_URL = f"https://iiif.archive.org/iiif/{ITEM}${LEAF}/info.json"
SERVICE_URL = f"https://iiif.archive.org/iiif/{ITEM}/{ITEM}_{LEAF:04d}.jp2"


class FakeResponse:
    def __init__(self, body: bytes, url: str, content_type: str):
        self.body = body
        self.url = url
        self.headers = {"content-type": content_type}

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]


class FakeOpener:
    def __init__(self, info: bytes, image: bytes, resolved_info: str = INFO_URL):
        self.info = info
        self.image = image
        self.resolved_info = resolved_info
        self.calls: list[str] = []

    def open(self, request, timeout: int) -> FakeResponse:
        url = request.full_url
        self.calls.append(url)
        if url.endswith("/info.json"):
            return FakeResponse(self.info, self.resolved_info, "application/json")
        return FakeResponse(self.image, url, "image/jpeg")


def _target() -> ScanTarget:
    raw_text = "hello world"
    return ScanTarget(
        item_identifier=ITEM,
        part_number=2,
        scan_leaf=LEAF,
        hocr_page_id="page20",
        paragraph_id="p20",
        raw_text=raw_text,
        raw_sha256=hashlib.sha256(raw_text.encode()).hexdigest(),
        hocr_sha256="a" * 64,
        page_map_sha256="b" * 64,
        ocr_width=20,
        ocr_height=20,
        selection_start=0,
        selection_end=5,
        selection_text="hello",
        precision="word-span",
        max_width=100,
        regions=[CropRegion(bbox=BoundingBox(left=5, top=5, right=15, bottom=15))],
    )


def _jpeg(width: int = 10, height: int = 10) -> bytes:
    image = Image.new("RGB", (width, height), color="white")
    output = io.BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def _info(service_id: str = SERVICE_URL, width: int = 20, height: int = 20) -> bytes:
    return json.dumps({"@id": service_id, "width": width, "height": height}).encode()


def _install_opener(monkeypatch, opener: Any) -> None:
    monkeypatch.setattr(scan_fetch, "build_opener", lambda *_args: opener)


def _fetcher(monkeypatch, info: bytes | None = None, image: bytes | None = None) -> FakeOpener:
    opener = FakeOpener(info or _info(), image or _jpeg())
    _install_opener(monkeypatch, opener)
    return opener


def test_fetches_one_info_and_one_exact_crop_with_audit_receipts(tmp_path, monkeypatch) -> None:
    opener = _fetcher(monkeypatch)
    bundle = scan_fetch.fetch_bundle(tmp_path / "bundle", _target())

    assert opener.calls == [INFO_URL, f"{SERVICE_URL}/5,5,10,10/10,/0/default.jpg"]
    assert bundle.info_receipt.requested_url == INFO_URL
    assert bundle.info_receipt.resolved_url == INFO_URL
    assert bundle.info_receipt.bytes == len(_info())
    assert bundle.info_receipt.content_type == "application/json"
    assert bundle.info_receipt.sha256 == scan_fetch.digest(_info())
    assert len(bundle.images) == 1
    assert bundle.images[0].region == (5, 5, 10, 10)
    image_path = tmp_path / "bundle" / "crop-01.jpg"
    assert image_path.is_file()
    image_receipt = bundle.images[0].receipt
    assert image_receipt.requested_url == opener.calls[1]
    assert image_receipt.resolved_url == opener.calls[1]
    assert image_receipt.bytes == image_path.stat().st_size
    assert image_receipt.sha256 == scan_fetch.digest(image_path.read_bytes())
    assert image_receipt.content_type == "image/jpeg"
    events = [
        json.loads(line) for line in (tmp_path / "bundle" / "events.jsonl").read_text().splitlines()
    ]
    assert [event["event"] for event in events].count("request_completed") == 2


@pytest.mark.parametrize(
    ("service_id", "width", "height"),
    [
        ("https://iiif.archive.org/iiif/other/other_0020.jp2", 20, 20),
        (f"https://iiif.archive.org/iiif/{ITEM}/{ITEM}_0021.jp2", 20, 20),
        (SERVICE_URL, 21, 20),
    ],
    ids=["wrong-item", "wrong-leaf", "wrong-dimensions"],
)
def test_rejects_service_item_leaf_and_dimension_mismatches(
    tmp_path, monkeypatch, service_id: str, width: int, height: int
) -> None:
    opener = _fetcher(monkeypatch, _info(service_id, width, height))
    with pytest.raises(ValueError):
        scan_fetch.fetch_bundle(tmp_path / "bundle", _target())
    assert opener.calls == [INFO_URL]


def test_rejects_unexpected_redirect_host(tmp_path, monkeypatch) -> None:
    opener = FakeOpener(_info(), _jpeg(), "https://example.org/redirected/info.json")
    _install_opener(monkeypatch, opener)
    with pytest.raises(ValueError, match="official HTTPS"):
        scan_fetch.fetch_bundle(tmp_path / "bundle", _target())
    assert len(opener.calls) == 1
    assert not (tmp_path / "bundle" / "info.json").exists()


@pytest.mark.parametrize("body,limit", [(b"", 10), (b"too many bytes", 4)])
def test_download_rejects_empty_and_over_limit_bodies(
    tmp_path, monkeypatch, body: bytes, limit: int
) -> None:
    opener = FakeOpener(_info(), body)
    _install_opener(monkeypatch, opener)
    output = tmp_path / "bounded" / "payload.bin"
    output.parent.mkdir()
    with pytest.raises(ValueError, match="Empty image response or download exceeds byte limit"):
        scan_fetch.download(INFO_URL, output, limit)
    assert not output.exists()
    assert not output.with_suffix(".bin.receipt.json").exists()


def test_fetch_rejects_malformed_jpeg_payload(tmp_path, monkeypatch) -> None:
    _fetcher(monkeypatch, image=b"not a JPEG")
    with pytest.raises(UnidentifiedImageError):
        scan_fetch.fetch_bundle(tmp_path / "bundle", _target())


def test_compatible_cached_fetch_uses_no_network(tmp_path, monkeypatch) -> None:
    opener = _fetcher(monkeypatch)
    directory = tmp_path / "bundle"
    target = _target()
    first = scan_fetch.fetch_bundle(directory, target)
    _install_opener(monkeypatch, _NoNetworkOpener())
    second = scan_fetch.fetch_bundle(directory, target)

    assert second.target_sha256 == first.target_sha256
    assert [image.receipt.sha256 for image in second.images] == [
        image.receipt.sha256 for image in first.images
    ]
    assert len(opener.calls) == 2
    assert (
        sum(
            json.loads(line)["event"] == "cache_hit"
            for line in (directory / "events.jsonl").read_text().splitlines()
        )
        == 2
    )


class _NoNetworkOpener:
    def open(self, *_args, **_kwargs):
        raise AssertionError("cached fetch must never call the network opener")


def test_cached_fetch_rejects_tampered_image_hash(tmp_path, monkeypatch) -> None:
    _fetcher(monkeypatch)
    directory = tmp_path / "bundle"
    scan_fetch.fetch_bundle(directory, _target())
    image_path = directory / "crop-01.jpg"
    image_payload = image_path.read_bytes()
    image_path.write_bytes(bytes([image_payload[0] ^ 1]) + image_payload[1:])
    _install_opener(monkeypatch, _NoNetworkOpener())

    with pytest.raises(ValueError, match="Cached download SHA-256 mismatch"):
        scan_fetch.fetch_bundle(directory, _target())


def test_output_directory_rejects_a_different_frozen_target(tmp_path, monkeypatch) -> None:
    opener = _fetcher(monkeypatch)
    directory = tmp_path / "bundle"
    target = _target()
    scan_fetch.fetch_bundle(directory, target)
    changed = target.model_copy(update={"max_width": 101})

    with pytest.raises(ValueError, match="different frozen target"):
        scan_fetch.fetch_bundle(directory, changed)
    assert len(opener.calls) == 2


def test_read_bundle_verifies_target_info_and_image_hashes(tmp_path, monkeypatch) -> None:
    _fetcher(monkeypatch)
    directory = tmp_path / "bundle"
    expected = scan_fetch.fetch_bundle(directory, _target())
    assert scan_fetch.read_bundle(directory).target_sha256 == expected.target_sha256

    info = directory / "info.json"
    info_payload = info.read_bytes()
    info.write_bytes(info_payload.replace(b'"width": 20', b'"width": 21'))
    with pytest.raises(ValueError, match="Cached download SHA-256 mismatch"):
        scan_fetch.read_bundle(directory)
    info.write_bytes(info_payload)

    image = directory / "crop-01.jpg"
    image_payload = image.read_bytes()
    image.write_bytes(bytes([image_payload[0] ^ 1]) + image_payload[1:])
    with pytest.raises(ValueError, match="Cached download SHA-256 mismatch"):
        scan_fetch.read_bundle(directory)
    image.write_bytes(image_payload)

    bundle_path = directory / "bundle.json"
    document = json.loads(bundle_path.read_text())
    document["target_sha256"] = "0" * 64
    bundle_path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="Bundle target hash mismatch"):
        scan_fetch.read_bundle(directory)


def test_read_bundle_binds_manifest_to_separate_frozen_target(tmp_path, monkeypatch) -> None:
    _fetcher(monkeypatch)
    directory = tmp_path / "bundle"
    target = _target()
    scan_fetch.fetch_bundle(directory, target)
    changed = target.model_copy(update={"max_width": 101})
    (directory / "target.json").write_text(changed.model_dump_json())

    with pytest.raises(ValueError):
        scan_fetch.read_bundle(directory)


@pytest.mark.parametrize("change", ["region", "count", "dimensions"])
def test_read_bundle_rejects_image_manifest_mismatch(tmp_path, monkeypatch, change: str) -> None:
    _fetcher(monkeypatch)
    directory = tmp_path / "bundle"
    scan_fetch.fetch_bundle(directory, _target())
    bundle_path = directory / "bundle.json"
    document = json.loads(bundle_path.read_text())
    if change == "region":
        document["images"][0]["region"] = [4, 5, 10, 10]
    elif change == "count":
        document["images"].clear()
    else:
        document["images"][0]["width"] = 9
    bundle_path.write_text(json.dumps(document))

    with pytest.raises(ValueError):
        scan_fetch.read_bundle(directory)


def test_concurrent_fetch_cannot_overlap_for_one_output_directory(tmp_path, monkeypatch) -> None:
    entered = threading.Event()
    release = threading.Event()
    result: list[object] = []
    opener = _BlockingOpener(_info(), _jpeg(), entered, release)
    _install_opener(monkeypatch, opener)
    directory = tmp_path / "bundle"

    def fetch_first() -> None:
        try:
            result.append(scan_fetch.fetch_bundle(directory, _target()))
        except Exception as exc:  # captured for assertion in the test thread
            result.append(exc)

    worker = threading.Thread(target=fetch_first)
    worker.start()
    assert entered.wait(timeout=3)
    try:
        with pytest.raises(BlockingIOError):
            scan_fetch.fetch_bundle(directory, _target())
    finally:
        release.set()
        worker.join(timeout=5)
    assert not worker.is_alive()
    assert len(result) == 1 and not isinstance(result[0], Exception)
    assert len(opener.calls) == 2


class _BlockingOpener(FakeOpener):
    def __init__(
        self, info: bytes, image: bytes, entered: threading.Event, release: threading.Event
    ):
        super().__init__(info, image)
        self.entered = entered
        self.release = release

    def open(self, request, timeout: int) -> FakeResponse:
        self.entered.set()
        assert self.release.wait(timeout=4)
        return super().open(request, timeout)
