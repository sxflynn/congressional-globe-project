import json

from congressional_globe import cli


def test_reading_status_explicit_run_dir_no_writes(tmp_path, capsys):
    # Use existing expansion run as fixture
    from pathlib import Path

    run_dir = Path("artifacts/reading-quote-expansion-run-20261025-01")
    assert run_dir.exists()
    # Run via CLI
    cli.main.__globals__  # ensure loaded
    # Simpler: call function directly
    from congressional_globe.reading_cli import run_reading
    import argparse

    args = argparse.Namespace(reading_action="status", run_dir=run_dir, json_out=True)
    run_reading(args, Path("."))
    out = capsys.readouterr().out
    report = json.loads(out)
    assert report["run_dir"].endswith("reading-quote-expansion-run-20261025-01")
    assert report["task_count"] == 36
    assert report["journal_counts"]["terminal"] == 36
    assert "unknown_usage" in report
    assert "review/ownership_state" in report
    assert "next_action" in report
    assert report["bounded_output"] is True
