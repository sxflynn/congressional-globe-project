from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from congressional_globe import scan_cli
from congressional_globe.cli import _parser
from congressional_globe.scan_models import ScanTarget


def _target() -> ScanTarget:
    return ScanTarget.model_validate(
        {
            "item_identifier": "congressionalglo7392unit",
            "part_number": 2,
            "scan_leaf": 328,
            "hocr_page_id": "page328",
            "paragraph_id": "p1",
            "raw_text": "word",
            "raw_sha256": hashlib.sha256(b"word").hexdigest(),
            "hocr_sha256": "0" * 64,
            "page_map_sha256": "1" * 64,
            "ocr_width": 20,
            "ocr_height": 20,
            "selection_start": 0,
            "selection_end": 4,
            "selection_text": "word",
            "precision": "paragraph",
            "max_width": 100,
            "regions": [{"bbox": {"left": 5, "top": 5, "right": 15, "bottom": 15}}],
        }
    )


def _arguments(output: Path, *extra: str):
    return _parser().parse_args(
        [
            "scan",
            "crop",
            "--item",
            "congressionalglo7392unit",
            "--leaf",
            "328",
            "--paragraph",
            "p1",
            "--output",
            str(output),
            *extra,
        ]
    )


def _forbid_fetch(*args):
    raise RuntimeError("explicit fetch reached")


def test_scan_cli_plans_without_network(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(scan_cli, "prepare_target", lambda *args: _target())
    monkeypatch.setattr(scan_cli, "fetch_bundle", _forbid_fetch)
    scan_cli.run_scan(_arguments(tmp_path), Path.cwd())
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "offline_plan"
    assert (tmp_path / "target.json").exists()
    assert not (tmp_path / "info.json").exists()


def test_scan_cli_fetch_requires_explicit_flag(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(scan_cli, "prepare_target", lambda *args: _target())
    monkeypatch.setattr(scan_cli, "fetch_bundle", _forbid_fetch)
    with pytest.raises(RuntimeError, match="explicit fetch"):
        scan_cli.run_scan(_arguments(tmp_path, "--fetch"), Path.cwd())


def test_expected_text_mismatch_stops_before_output_or_fetch(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(scan_cli, "prepare_target", lambda *args: _target())
    monkeypatch.setattr(scan_cli, "fetch_bundle", _forbid_fetch)
    with pytest.raises(ValueError, match="Expected patch text"):
        scan_cli.run_scan(_arguments(tmp_path, "--expected", "other", "--fetch"), Path.cwd())
    assert not (tmp_path / "target.json").exists()
