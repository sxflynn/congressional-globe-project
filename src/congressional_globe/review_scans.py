"""Inline source-image disclosure without changing immutable review evidence."""

from __future__ import annotations

import html
import re
from urllib.parse import urlsplit

import streamlit as st


def scan_image_url(source_url: str) -> str | None:
    """Resolve only explicit Archive page citations or official IIIF image URLs."""
    parsed = urlsplit(source_url)
    if parsed.scheme != "https":
        return None
    if parsed.netloc == "iiif.archive.org" and parsed.path.endswith((".jpg", ".png")):
        return source_url
    if parsed.netloc != "archive.org":
        return None
    match = re.fullmatch(r"/details/([A-Za-z0-9_.-]+)/page/n(\d+)(?:/mode/1up)?/?", parsed.path)
    if match is None:
        return None
    item, leaf = match.groups()
    return f"https://iiif.archive.org/iiif/{item}${leaf}/full/full/0/default.jpg"


def scan_disclosure(source_url: str) -> str | None:
    image_url = scan_image_url(source_url)
    if image_url is None:
        return None
    image = html.escape(image_url, quote=True)
    source = html.escape(source_url, quote=True)
    return (
        '<details class="globe-scan"><summary>Show original scan</summary>'
        "<p>Tap the image to open it in a new tab, then zoom to inspect the print.</p>"
        f'<a href="{image}" target="_blank" rel="noopener noreferrer">'
        f'<img src="{image}" alt="Original scanned source; open image in a new tab" '
        'loading="lazy" style="width:100%;height:auto;display:block"></a>'
        f'<p><a href="{source}" target="_blank" rel="noopener noreferrer">'
        "Open source page</a></p></details>"
    )


def show_inline_scan(source_url: str) -> None:
    disclosure = scan_disclosure(source_url)
    if disclosure:
        st.markdown(disclosure, unsafe_allow_html=True)
    else:
        st.markdown(f"[Open source]({source_url})")
