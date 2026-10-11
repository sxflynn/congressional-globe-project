from __future__ import annotations

import pytest

from congressional_globe.cli import _parser


def test_cleanup_run_accepts_optional_positive_time_budget() -> None:
    parser = _parser()
    arguments = parser.parse_args(
        [
            "cleanup",
            "run",
            "--run-directory",
            "artifacts/run",
            "--run-id",
            "qwen-hour",
            "--model",
            "qwen",
            "--max-seconds",
            "3600",
        ]
    )
    assert arguments.max_seconds == 3600

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "cleanup",
                "run",
                "--run-directory",
                "artifacts/run",
                "--run-id",
                "qwen-hour",
                "--model",
                "qwen",
                "--max-seconds",
                "0",
            ]
        )
