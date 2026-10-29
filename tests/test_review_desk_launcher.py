from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from congressional_globe.review_desk_launcher import (
    create_static_overlay,
    patch_index,
    theme_backgrounds,
)


def test_patch_index_puts_device_colors_in_head_before_app_assets() -> None:
    source = '<html><head><script src="bundle.js"></script></head></html>'

    result = patch_index(source, "#faf6ed", "#1e1b17")

    assert result.index("review-desk-first-paint") < result.index("bundle.js")
    assert "html{background:#1e1b17}" in result
    assert "prefers-color-scheme:light" in result
    assert "html{background:#faf6ed}" in result


def test_patch_index_refuses_unexpected_or_already_patched_html() -> None:
    with pytest.raises(ValueError, match="marker not found"):
        patch_index("<html></html>", "#faf6ed", "#1e1b17")
    with pytest.raises(ValueError, match="already contains"):
        patch_index('<head id="review-desk-first-paint">', "#faf6ed", "#1e1b17")


def test_theme_backgrounds_uses_config_and_rejects_non_hex(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        '[theme.light]\nbackgroundColor="#faf6ed"\n[theme.dark]\nbackgroundColor="#1e1b17"\n',
        encoding="utf-8",
    )

    assert theme_backgrounds(config) == ("#faf6ed", "#1e1b17")
    config.write_text(
        '[theme.light]\nbackgroundColor="red;body{display:none}"\n'
        '[theme.dark]\nbackgroundColor="#1e1b17"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="six-digit hex"):
        theme_backgrounds(config)


def test_static_overlay_symlinks_assets_and_writes_only_new_index(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "overlay"
    source.mkdir()
    target.mkdir()
    (source / "index.html").write_text('<head><script src="app.js">', encoding="utf-8")
    (source / "app.js").write_text("unchanged", encoding="utf-8")

    create_static_overlay(source, target, "#faf6ed", "#1e1b17")

    assert (target / "app.js").is_symlink()
    assert (target / "app.js").read_text(encoding="utf-8") == "unchanged"
    assert "review-desk-first-paint" in (target / "index.html").read_text(encoding="utf-8")
    assert (source / "index.html").read_text(encoding="utf-8") == '<head><script src="app.js">'


def test_streamlit_static_route_serves_overlay_document_and_original_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from starlette.applications import Starlette
    from starlette.testclient import TestClient
    from streamlit import file_util
    from streamlit.web.server.starlette.starlette_static_routes import (
        create_streamlit_static_assets_routes,
    )

    source = tmp_path / "source"
    overlay = tmp_path / "overlay"
    source.mkdir()
    overlay.mkdir()
    (source / "index.html").write_text("<head><title>app</title>", encoding="utf-8")
    (source / "asset.js").write_text("original bundled asset", encoding="utf-8")
    create_static_overlay(source, overlay, "#faf6ed", "#1e1b17")
    monkeypatch.setattr(file_util, "get_static_dir", lambda: str(overlay))
    app = Starlette(routes=create_streamlit_static_assets_routes(None))

    with TestClient(app) as client:
        document = client.get("/")
        asset = client.get("/asset.js")

    assert document.status_code == 200
    assert "html{background:#1e1b17}" in document.text
    assert asset.status_code == 200
    assert asset.text == "original bundled asset"


@pytest.mark.parametrize("raises", [False, True])
def test_cli_restores_process_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raises: bool
) -> None:
    from congressional_globe.review_desk_launcher import _run_cli

    file_util = ModuleType("fake_file_util")

    def original_get_static_dir() -> str:
        return "original-static"

    monkeypatch.setattr(file_util, "get_static_dir", original_get_static_dir, raising=False)
    web = ModuleType("streamlit.web")
    cli = ModuleType("streamlit.web.cli")

    def main() -> int:
        assert file_util.get_static_dir() == str(tmp_path)
        assert sys.argv[:3] == [
            "streamlit",
            "run",
            "src/congressional_globe/review_app.py",
        ]
        if raises:
            raise RuntimeError("serve failed")
        return 0

    monkeypatch.setattr(cli, "main", main, raising=False)
    monkeypatch.setattr(web, "cli", cli, raising=False)
    monkeypatch.setitem(sys.modules, "streamlit.web", web)
    monkeypatch.setitem(sys.modules, "streamlit.web.cli", cli)
    old_argv = sys.argv
    if raises:
        with pytest.raises(RuntimeError, match="serve failed"):
            _run_cli(file_util, tmp_path)
    else:
        assert _run_cli(file_util, tmp_path) == 0
    assert file_util.get_static_dir is original_get_static_dir
    assert sys.argv is old_argv
