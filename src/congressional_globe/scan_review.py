"""Read-only source-image demonstrations from already fetched, hash-checked crops."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from pydantic import BaseModel, ConfigDict

from congressional_globe.scan_fetch import ScanBundle, read_bundle


class ScanDemo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    directory: str


class ScanCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    demos: list[ScanDemo]


def show_source_images() -> None:
    st.subheader("Original source images")
    st.caption(
        "Compare unchanged OCR with the original print. These cached views make no model calls."
    )
    catalog_path = Path("docs/scan-demos.json")
    if not catalog_path.exists():
        st.info("The first source-image examples are being prepared.")
        return
    try:
        catalog = ScanCatalog.model_validate_json(catalog_path.read_text())
        _show_catalog(catalog)
    except (OSError, ValueError, KeyError) as error:
        st.error(f"This source crop could not be verified: {error}")


def _show_catalog(catalog: ScanCatalog) -> None:
    if not catalog.demos:
        st.info("No source-image examples are registered yet.")
        return
    example = st.selectbox("Original source", catalog.demos, format_func=lambda entry: entry.title)
    directory = Path(example.directory).resolve()
    if not directory.is_relative_to(Path("artifacts").resolve()):
        raise ValueError("Cached scans must be inside the artifacts directory")
    _show_bundle(directory, read_bundle(directory))


def _show_bundle(directory: Path, bundle: ScanBundle) -> None:
    target = bundle.target
    st.caption(
        f"Part {target.part_number} · printed page {target.printed_page or 'unknown'} · "
        f"scan leaf {target.scan_leaf} · {target.paragraph_id}"
    )
    url = f"https://archive.org/details/{target.item_identifier}/page/n{target.scan_leaf}/mode/1up"
    st.link_button("Open the full source page", url)
    st.markdown("**Unchanged OCR**")
    st.text(target.raw_text)
    if target.precision == "word-span":
        st.caption(f"Selected OCR text: {target.selection_text}")
    st.markdown("**Original scanned print**")
    st.caption("Padding includes neighboring print; an OCR box can omit a printed continuation.")
    for image in bundle.images:
        st.image(str(directory / image.file), width="stretch")
    _show_details(bundle)


def _show_details(bundle: ScanBundle) -> None:
    with st.expander("Source and crop details"):
        st.write("This is a source view, not an accepted correction or a new transcription.")
        st.json(
            {
                "item_identifier": bundle.target.item_identifier,
                "scan_leaf": bundle.target.scan_leaf,
                "raw_text_sha256": bundle.target.raw_sha256,
                "source_frame_pixels": [bundle.target.ocr_width, bundle.target.ocr_height],
                "registration": bundle.registration,
                "regions": [image.region for image in bundle.images],
                "downloaded_bytes": bundle.info_receipt.bytes
                + sum(i.receipt.bytes for i in bundle.images),
                "original_request_seconds": bundle.info_receipt.elapsed_seconds
                + sum(i.receipt.elapsed_seconds for i in bundle.images),
                "image_urls": [image.receipt.requested_url for image in bundle.images],
            }
        )
