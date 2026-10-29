"""Throwaway spike: copy Streamlit's static tree and patch its index.html."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

DARK = "#1e1b17"
LIGHT = "#faf6ed"

STYLE = (
    '<meta name="color-scheme" content="dark light" />'
    "<style>"
    f"html{{background:{DARK}}}"
    "@media (prefers-color-scheme: light){html{background:%s}}"
    "</style>" % LIGHT
)


def main() -> None:
    import streamlit.file_util as file_util

    source = Path(file_util.get_static_dir())
    target = Path(__file__).resolve().parent / "static"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    index = target / "index.html"
    html = index.read_text(encoding="utf-8")
    marker = "<head>"
    if marker not in html or "color-scheme" in html:
        raise SystemExit("unexpected index.html template")
    html = html.replace(marker, marker + STYLE, 1)
    index.write_text(html, encoding="utf-8")
    print(f"patched {index}")


if __name__ == "__main__":
    sys.exit(main())
