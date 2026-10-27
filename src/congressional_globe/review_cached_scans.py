"""Verified local source crops in review evidence, without image downloads."""

from pathlib import Path
from typing import Literal

import streamlit as st
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from congressional_globe.scan_fetch import ScanBundle, ScanImage, digest, read_bundle
from congressional_globe.scan_models import NonBlank, Sha256

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "docs" / "review-scan-cache.json"


class CachedReviewScan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_url: HttpUrl
    directory: NonBlank
    bundle_sha256: Sha256
    source_id: NonBlank
    raw_sha256: Sha256
    image_sha256: Sha256


class ReviewScanCache(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1]
    scans: list[CachedReviewScan] = Field(max_length=16)


def _entry(source_url: str) -> CachedReviewScan | None:
    if not CATALOG.exists():
        return None
    catalog = ReviewScanCache.model_validate_json(CATALOG.read_text())
    matches = [entry for entry in catalog.scans if str(entry.source_url) == source_url]
    if len(matches) > 1:
        raise ValueError("Multiple cached scans match the source URL")
    return next(iter(matches), None)


def _directory(entry: CachedReviewScan) -> Path:
    directory = (ROOT / entry.directory).resolve()
    if not directory.is_relative_to((ROOT / "artifacts").resolve()):
        raise ValueError("Review scans must be inside artifacts")
    if digest((directory / "bundle.json").read_bytes()) != entry.bundle_sha256:
        raise ValueError("Review scan bundle fingerprint mismatch")
    return directory


def _check_source(entry: CachedReviewScan, bundle: ScanBundle) -> None:
    target = bundle.target
    source_id = f"{target.item_identifier}:{target.scan_leaf}:{target.paragraph_id}"
    if (source_id, target.raw_sha256) != (entry.source_id, entry.raw_sha256):
        raise ValueError("Review scan does not match its declared OCR source")


def _matches(image: ScanImage, entry: CachedReviewScan) -> bool:
    return (image.receipt.requested_url, image.receipt.sha256) == (
        str(entry.source_url),
        entry.image_sha256,
    )


def _image_bytes(directory: Path, image: ScanImage) -> bytes:
    path = (directory / image.file).resolve()
    if not path.is_relative_to(directory):
        raise ValueError("Review image must remain inside its verified bundle")
    return path.read_bytes()


def _view(entry: CachedReviewScan) -> tuple[bytes, str, int]:
    directory = _directory(entry)
    bundle = read_bundle(directory)
    _check_source(entry, bundle)
    images = [image for image in bundle.images if _matches(image, entry)]
    if len(images) != 1:
        raise ValueError("Review image URL or fingerprint mismatch")
    target = bundle.target
    source = (
        f"https://archive.org/details/{target.item_identifier}/page/n{target.scan_leaf}/mode/1up"
    )
    return _image_bytes(directory, images[0]), source, images[0].width


def show_cached_scan(source_url: str) -> bool:
    """Display a catalogued crop immediately; no network or model request."""
    entry = _entry(source_url)
    if entry is None:
        return False
    payload, source_page, width = _view(entry)
    st.caption("Original page image, from a saved copy. Nearby print provides context.")
    st.image(payload, width="stretch" if width >= 400 else width * 3)
    st.link_button("Open original image to zoom", source_url)
    st.link_button("Open full source page", source_page)
    return True
