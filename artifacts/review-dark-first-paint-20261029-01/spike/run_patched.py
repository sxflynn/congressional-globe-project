"""Throwaway spike: serve Streamlit's desk with a patched index.html.

Not a proposal and not wired into any project command. It exists only to
measure whether an earliest-paint document change removes the white startup
flash before asking for an adoption review.
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
PATCHED_STATIC = HERE / "static"


def main() -> None:
    import streamlit.file_util as file_util

    original = file_util.get_static_dir
    if not (PATCHED_STATIC / "index.html").is_file():
        raise SystemExit(f"missing patched static dir: {PATCHED_STATIC}")

    def patched() -> str:
        return str(PATCHED_STATIC)

    file_util.get_static_dir = patched  # type: ignore[assignment]
    try:
        from streamlit.web import cli as stcli

        sys.argv = [
            "streamlit",
            "run",
            "src/congressional_globe/review_app.py",
            "--server.address",
            "0.0.0.0",
            "--server.port",
            "8502",
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ]
        sys.exit(stcli.main())
    finally:
        file_util.get_static_dir = original


if __name__ == "__main__":
    main()
