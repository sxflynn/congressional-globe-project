"""Display one verified experimental region without inventing a fetch receipt."""

import streamlit as st

from congressional_globe.productive_ocr_host import sha256_bytes
from congressional_globe.productive_ocr_image_statute import load_image_inputs, provider_image_bytes
from congressional_globe.productive_ocr_measurement_scoped import REGION_PACKAGE
from congressional_globe.productive_ocr_region_statute import (
    CROP_SHA,
    crop_bytes,
    load_region_inputs,
)
from congressional_globe.review_cached_scans import ROOT

PARENT_URL = (
    "https://iiif.archive.org/image/iiif/2/congressionalglo7395unit%2f"
    "congressionalglo7395unit_jp2.zip%2fcongressionalglo7395unit_jp2%2f"
    "congressionalglo7395unit_0741.jp2/59,42,2824,1547/1600,/0/default.jpg"
)
REGION_URL = PARENT_URL + "#globe-p8-pixel-region-20261102-01"


def _parent_bytes():
    _host, projection, _registry = load_image_inputs(ROOT)
    return provider_image_bytes(projection)


def verified_region():
    parent = _parent_bytes()
    host, projection, _registry = load_region_inputs(ROOT)
    if sha256_bytes(parent) != host["payload"]["image"]["sha256"]:
        raise ValueError("Derived display parent differs from model source")
    payload = (ROOT / REGION_PACKAGE / "crop.png").read_bytes()
    if sha256_bytes(payload) != CROP_SHA:
        raise ValueError("Derived display PNG changed")
    if payload != crop_bytes(parent) or payload != provider_image_bytes(projection):
        raise ValueError("Displayed crop differs from exact pixels or actual model input")
    image = host["payload"]["image"]
    source_page = (
        f"https://archive.org/details/{image['source_item_identifier']}"
        f"/page/n{image['source_scan_leaf']}/mode/1up"
    )
    return payload, source_page


def show_region_scan(source_url):
    if source_url != REGION_URL:
        return False
    payload, source_page = verified_region()
    st.caption(
        "Selected paragraph, copied exactly from the saved original image. "
        "The original image is unchanged. This is the image supplied in this experiment."
    )
    st.image(payload, width="stretch")
    st.link_button("Open original image for context", PARENT_URL)
    st.link_button("Open full source page", source_page)
    return True
