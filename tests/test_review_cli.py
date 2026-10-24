from __future__ import annotations

import json
from pathlib import Path

import pytest

from congressional_globe.cli import _parser
from congressional_globe.review_cli import run_review
from congressional_globe.review_store import ReviewStore


def _command(database: Path, *arguments: str) -> None:
    args = _parser().parse_args(["review", "--database", str(database), *arguments])
    run_review(args, Path.cwd())


def test_review_cli_register_inbox_export_and_apply(tmp_path, capsys) -> None:
    database = tmp_path / "review.sqlite"
    _command(database, "register", "docs/review-demo.json")
    registered = json.loads(capsys.readouterr().out)
    assert registered["id"] == "DEMO-001"
    submission = ReviewStore(database).submit(
        "DEMO-001", 1, "Test reviewer", {"topic": "Voting rights", "notes": "Exactly — yes."}
    )
    sid = submission["submission_id"]
    _command(database, "inbox")
    assert json.loads(capsys.readouterr().out)[0]["submission_id"] == sid
    destination = tmp_path / "archive" / "submission.json"
    _command(database, "export", sid, "--output", str(destination))
    capsys.readouterr()
    assert "Exactly — yes." in destination.read_text()
    with pytest.raises(FileExistsError):
        _command(database, "export", sid, "--output", str(destination))
    _command(database, "applied", sid, "--reference", "commit:test-fixture-only")
    assert json.loads(capsys.readouterr().out)["applied"]
    _command(database, "inbox")
    assert json.loads(capsys.readouterr().out) == []


def test_review_schema_does_not_open_database(tmp_path, capsys) -> None:
    database = tmp_path / "not-created.sqlite"
    _command(database, "schema")
    assert json.loads(capsys.readouterr().out)["title"] == "ReviewPacket"
    assert not database.exists()
