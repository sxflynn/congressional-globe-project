"""Start the review desk with an early system-theme-aware document canvas."""

from __future__ import annotations

import os
import re
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

SUPPORTED_STREAMLIT_VERSION = "1.66.1"
APP_PATH = "src/congressional_globe/review_app.py"
_COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")


def theme_backgrounds(config_path: Path) -> tuple[str, str]:
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    try:
        light = config["theme"]["light"]["backgroundColor"]
        dark = config["theme"]["dark"]["backgroundColor"]
    except (KeyError, TypeError) as exc:
        raise ValueError("review desk needs light and dark backgroundColor values") from exc
    if not isinstance(light, str) or not _COLOR.fullmatch(light):
        raise ValueError("light backgroundColor must be a six-digit hex color")
    if not isinstance(dark, str) or not _COLOR.fullmatch(dark):
        raise ValueError("dark backgroundColor must be a six-digit hex color")
    return light, dark


def patch_index(index_html: str, light: str, dark: str) -> str:
    if "review-desk-first-paint" in index_html:
        raise ValueError("Streamlit index already contains the review-desk first-paint patch")
    marker = "<head>"
    if marker not in index_html:
        raise ValueError("unsupported Streamlit index: <head> marker not found")
    early_style = (
        '<meta name="color-scheme" content="dark light" />'
        '<style id="review-desk-first-paint">'
        f"html{{background:{dark}}}"
        f"@media(prefers-color-scheme:light){{html{{background:{light}}}}}"
        "</style>"
    )
    return index_html.replace(marker, marker + early_style, 1)


def create_static_overlay(source: Path, target: Path, light: str, dark: str) -> None:
    source_index = source / "index.html"
    if not source_index.is_file():
        raise ValueError(f"Streamlit static index not found: {source_index}")
    for resource in source.iterdir():
        if resource.name != "index.html":
            os.symlink(resource, target / resource.name, target_is_directory=resource.is_dir())
    html = source_index.read_text(encoding="utf-8")
    (target / "index.html").write_text(patch_index(html, light, dark), encoding="utf-8")


def _run_cli(file_util: Any, overlay: Path) -> int:
    original_get_static_dir = file_util.get_static_dir
    original_argv = sys.argv
    file_util.get_static_dir = lambda: str(overlay)
    sys.argv = [
        "streamlit",
        "run",
        APP_PATH,
        "--server.address",
        "0.0.0.0",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    try:
        # Import after the process-local override and before route creation.
        from streamlit.web import cli as stcli

        return int(stcli.main() or 0)
    finally:
        file_util.get_static_dir = original_get_static_dir
        sys.argv = original_argv


def main() -> int:
    import streamlit
    from streamlit import file_util

    if streamlit.__version__ != SUPPORTED_STREAMLIT_VERSION:
        raise RuntimeError(
            "review-desk first-paint integration supports Streamlit "
            f"{SUPPORTED_STREAMLIT_VERSION}; found {streamlit.__version__}"
        )
    config_path = Path(".streamlit/config.toml")
    light, dark = theme_backgrounds(config_path)
    source = Path(file_util.get_static_dir())
    with tempfile.TemporaryDirectory(prefix="globe-review-static-") as temp_dir:
        overlay = Path(temp_dir)
        create_static_overlay(source, overlay, light, dark)
        return _run_cli(file_util, overlay)


if __name__ == "__main__":
    sys.exit(main())
