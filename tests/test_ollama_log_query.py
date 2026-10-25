from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from congressional_globe import ollama_log_query as log_query
from congressional_globe.cli import _parser
from congressional_globe.ollama_log_cli import run_ollama_logs
from congressional_globe.ollama_log_query import (
    LogQuery,
    LogQueryError,
    _zone,
    query_log,
    serialize_report,
)


def _write(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _slog(
    timestamp: str,
    message: str = "event",
    level: str = "INFO",
    source: str = "pipeline.go:228",
    **fields: str,
) -> str:
    pairs = " ".join(
        f'{key}="{value}"' if " " in value else f"{key}={value}" for key, value in fields.items()
    )
    suffix = f" {pairs}" if pairs else ""
    return f'time={timestamp} level={level} source={source} msg="{message}"{suffix}'


def _serve_http(method: str, path: str, status: str, timestamp: str, duration: str = "82us") -> str:
    return (
        f"time={timestamp} level=INFO source=server.go:252 msg=ServeHTTP "
        f'method={method} path={path} took={duration} status="{status}"'
    )


def _gin(status: str, method: str, path: str, timestamp: str = "2026/10/25 - 11:59:10") -> str:
    return f'[GIN] {timestamp} | {status} | 2m0s | 127.0.0.1 | {method}     "{path}"'


def _query(path: Path, **overrides: Any):
    return query_log(LogQuery(path=str(path), **overrides))


def _cursor_page(path: Path, cursor: str | None, **overrides: Any):
    return query_log(LogQuery(path=str(path), **overrides), cursor)


def _pages(path: Path, **overrides: Any):
    pages = []
    cursor = None
    while True:
        page = _cursor_page(path, cursor, **overrides)
        pages.append(page)
        if page.next_cursor is None:
            return pages
        cursor = page.next_cursor


def test_real_slog_gin_and_json_formats_are_parsed(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [
            _slog("2026-10-25T11:57:36.343-04:00", "Prompt processing progress", processed="2048"),
            _serve_http(
                "POST",
                "/v1/completions",
                "200 OK",
                "2026-10-25T11:59:10.826-04:00",
                duration="1m59s",
            ),
            _gin("500", "POST", "/api/chat"),
            '{"time":"2026-10-25T12:00:00Z","level":"info","msg":"json event","model":"qwen"}',
        ],
    )

    report = _query(path, assume_tz="UTC")

    assert [event["line"] for event in report.events] == [1, 2, 3, 4]
    assert report.events[0]["fields"] == {"processed": "2048"}
    assert report.events[1]["http"] == {
        "method": "POST",
        "path": "/v1/completions",
        "status": 200,
        "duration": "1m59s",
        "client": None,
    }
    assert report.events[2]["http"] == {
        "method": "POST",
        "path": "/api/chat",
        "status": 500,
        "duration": "2m0s",
        "client": "127.0.0.1",
    }
    assert report.events[3]["fields"] == {"model": "qwen"}
    assert report.counts.by_parse_status == {"parsed": 4}
    assert report.parser_version == "ollama-log-query-v2"


def test_gin_without_brackets_and_malformed_pipe_count(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [
            'GIN 2026/10/25 - 11:59:10 | 500 | 2m0s | 127.0.0.1 | POST     "/api/chat"',
            "[GIN] 2026/10/25 - 11:59:10 | 500 | 2m0s",
        ],
    )

    report = _query(path, assume_tz="UTC")

    assert report.events[0]["http"]["path"] == "/api/chat"
    assert report.events[0]["http"]["method"] == "POST"
    assert report.counts.by_parse_status == {"malformed": 1, "parsed": 1}


def test_time_window_is_inclusive_since_and_exclusive_until(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [
            _slog("2026-10-25T00:00:00+00:00", "first"),
            _slog("2026-10-25T00:00:01+00:00", "second"),
            _slog("2026-10-25T00:00:02+00:00", "third"),
        ],
    )

    report = _query(
        path,
        since=datetime(2026, 10, 25, 0, 0, 1, tzinfo=UTC),
        until=datetime(2026, 10, 25, 0, 0, 2, tzinfo=UTC),
    )

    assert [event["message"] for event in report.events] == ["second"]
    assert report.counts.matched == 1


def test_naive_bounds_use_assume_tz_then_compare_in_utc(tmp_path: Path) -> None:
    path = _write(tmp_path / "server.log", [_slog("2026-10-25T10:00:00+00:00", "event")])
    naive = datetime(2026, 10, 25, 10, 0, 0)

    included = _query(path, since=naive, assume_tz="UTC")
    excluded = _query(path, since=naive, assume_tz="America/New_York")

    assert included.counts.matched == 1
    assert excluded.counts.matched == 0
    assert excluded.query["since"] == "2026-10-25T14:00:00+00:00"


def test_local_timezone_uses_configured_iana_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TZ", "America/New_York")

    assert _zone("local") == ZoneInfo("America/New_York")


def test_include_exclude_and_ignore_case_are_literal(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [
            _slog("2026-10-25T00:00:00+00:00", "Timeout"),
            _slog("2026-10-25T00:00:01+00:00", "timeout"),
            _slog("2026-10-25T00:00:02+00:00", "timeout debug"),
        ],
    )

    exact = _query(path, include=("timeout",), exclude=("debug",))
    folded = _query(path, include=("timeout",), exclude=("debug",), ignore_case=True)

    assert [event["line"] for event in exact.events] == [2]
    assert [event["line"] for event in folded.events] == [1, 2]


def test_level_component_status_method_and_field_filters(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [
            _slog(
                "2026-10-25T00:00:00Z",
                "Request terminated",
                level="ERROR",
                source="runner.go:300",
                error="context canceled",
            ),
            _gin("500", "POST", "/api/chat"),
            _serve_http("GET", "/v1/status", "200 OK", "2026-10-25T00:00:01Z"),
        ],
    )

    assert _query(path, levels=("error",)).counts.matched == 1
    assert _query(path, components=("runner.go",)).counts.matched == 1
    assert _query(path, statuses=(500,)).counts.matched == 1
    assert _query(path, statuses=(200,)).counts.matched == 1
    assert _query(path, methods=("get",)).counts.matched == 1
    assert _query(path, fields=(("error", "context canceled"),)).counts.matched == 1
    assert _query(path, fields=(("missing", "value"),)).counts.matched == 0


def test_mixed_malformed_continuation_and_blank_lines_are_counted(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [
            "not a structured log line",
            "  continuation without a timestamp",
            "",
            '{"time":"2026-10-25T00:00:00Z","level":"info","message":"json"}',
        ],
    )

    report = _query(path, parse_statuses=("parsed",))

    assert report.counts.by_parse_status == {
        "blank": 1,
        "continuation": 1,
        "malformed": 1,
        "parsed": 1,
    }
    assert [event["line"] for event in report.events] == [4]
    assert report.counts.scanned_lines == 4


def test_missing_timestamps_are_excluded_from_a_window_but_counted(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [_slog("2026-10-25T00:00:00Z"), '{"level":"info","msg":"no timestamp"}'],
    )

    report = _query(
        path,
        since=datetime(2026, 10, 25, tzinfo=UTC),
        assume_tz="UTC",
    )

    assert report.counts.matched == 1
    assert report.counts.missing_timestamp_excluded == 1


def test_pagination_is_stable_and_does_not_duplicate_events(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [_slog(f"2026-10-25T00:00:0{index}Z", f"match {index}") for index in range(5)],
    )

    first = _query(path, include=("match",), limit=2)
    second = _cursor_page(path, first.next_cursor, include=("match",), limit=2)
    third = _cursor_page(path, second.next_cursor, include=("match",), limit=2)

    lines = [event["line"] for page in (first, second, third) for event in page.events]
    assert lines == [1, 2, 3, 4, 5]
    assert first.completeness.has_more is True
    assert third.completeness.has_more is False


def test_appending_after_a_cursor_is_allowed_and_reported(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [_slog("2026-10-25T00:00:00Z", "match one"), _slog("2026-10-25T00:00:01Z", "match two")],
    )
    first = _query(path, include=("match",), limit=1)

    without_append = _cursor_page(path, first.next_cursor, include=("match",))
    assert without_append.completeness.appended_since_cursor is False
    assert [event["line"] for event in without_append.events] == [2]

    with path.open("a", encoding="utf-8") as handle:
        handle.write(_slog("2026-10-25T00:00:02Z", "match three") + "\n")
    appended = _cursor_page(path, first.next_cursor, include=("match",))

    assert appended.completeness.appended_since_cursor is True
    assert [event["line"] for event in appended.events] == [2, 3]
    assert "appended" in appended.completeness.notes[0]


def test_cursor_is_bound_to_its_query(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [_slog("2026-10-25T00:00:00Z", "match one"), _slog("2026-10-25T00:00:01Z", "match two")],
    )
    first = _query(path, include=("match",), limit=1)

    with pytest.raises(LogQueryError, match="different query") as error:
        _cursor_page(path, first.next_cursor, include=("other",))
    assert error.value.code == "cursor_query_mismatch"


def test_invalid_cursor_token_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path / "server.log", [_slog("2026-10-25T00:00:00Z")])

    with pytest.raises(LogQueryError) as error:
        query_log(LogQuery(path=str(path)), "not-a-valid-cursor")
    assert error.value.code == "invalid_cursor"


def test_cursor_rejects_a_shrunk_file(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [_slog("2026-10-25T00:00:00Z"), _slog("2026-10-25T00:00:01Z")],
    )
    first = _query(path, limit=1)
    path.write_text("x\n", encoding="utf-8")

    with pytest.raises(LogQueryError) as error:
        _cursor_page(path, first.next_cursor, limit=1)
    assert error.value.code == "stale_cursor_shrunk"


def test_cursor_rejects_a_modified_prefix(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [_slog("2026-10-25T00:00:00Z"), _slog("2026-10-25T00:00:01Z")],
    )
    first = _query(path, limit=1)
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace("00:00:00", "00:00:09"), encoding="utf-8")

    with pytest.raises(LogQueryError) as error:
        _cursor_page(path, first.next_cursor, limit=1)
    assert error.value.code == "stale_cursor_modified"


def test_cursor_rejects_rotation_to_a_new_file(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [_slog("2026-10-25T00:00:00Z"), _slog("2026-10-25T00:00:01Z")],
    )
    original_inode = path.stat().st_ino
    first = _query(path, limit=1)
    path.rename(tmp_path / "server-1.log")
    path.write_text(_slog("2026-10-25T00:00:02Z") + "\n", encoding="utf-8")
    if path.stat().st_ino == original_inode:
        pytest.skip("Filesystem reused the inode")

    with pytest.raises(LogQueryError) as error:
        _cursor_page(path, first.next_cursor, limit=1)
    assert error.value.code == "stale_cursor_rotated"


def test_output_byte_cap_paginates_without_losing_events(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [
            _slog(f"2026-10-25T00:00:0{index}Z", f"match {index}", detail="x" * 300)
            for index in range(6)
        ],
    )

    pages = _pages(
        path,
        include=("match",),
        limit=50,
        raw_bytes=100,
        max_output_bytes=4_096,
    )

    assert all(len(serialize_report(page).encode()) <= 4_096 for page in pages)
    lines = [event["line"] for page in pages for event in page.events]
    assert lines == [1, 2, 3, 4, 5, 6]
    assert all(page.completeness.output_limit_reached for page in pages[:-1])


def test_combined_output_and_scan_caps_resume_at_first_unreturned_event(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path / "server.log",
        [
            _slog(f"2026-10-25T00:00:0{index}Z", f"match {index}", detail="x" * 300)
            for index in range(10)
        ],
    )
    overrides = {
        "include": ("match",),
        "limit": 1,
        "raw_bytes": 0,
        "max_scan_bytes": 1_024,
    }

    first = _cursor_page(path, None, **overrides)
    second = _cursor_page(path, first.next_cursor, **overrides)

    assert first.events[0]["line"] == 1
    assert second.events[0]["line"] == 2


def test_limit_caps_returned_events_and_reports_more(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [_slog(f"2026-10-25T00:00:0{index}Z", "match") for index in range(5)],
    )

    report = _query(path, include=("match",), limit=2)

    assert report.counts.matched == 5
    assert report.counts.returned == 2
    assert report.completeness.output_limit_reached is True
    assert report.completeness.has_more is True


def test_scan_byte_cap_reports_incomplete_scan(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [_slog(f"2026-10-25T00:00:{index:02d}Z", "match") for index in range(60)],
    )

    report = _query(path, include=("match",), limit=500, max_scan_bytes=1_024)

    assert report.source.scanned_bytes <= 1_024
    assert report.completeness.scan_limit_reached is True
    assert report.completeness.complete is False
    assert report.completeness.has_more is True
    assert report.counts.returned < 60


def test_scan_budget_ending_exactly_at_eof_is_complete(tmp_path: Path) -> None:
    path = tmp_path / "server.log"
    path.write_bytes(b"a" * 1_023 + b"\n")

    report = _query(path, max_scan_bytes=1_024)

    assert report.completeness.scan_limit_reached is False
    assert report.completeness.complete is True
    assert report.next_cursor is None


def test_raw_and_context_are_truncated_by_utf8_bytes(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "server.log",
        [
            _slog("2026-10-25T00:00:00Z", "before", detail="b" * 40),
            _slog("2026-10-25T00:00:01Z", "match", detail="é" * 20),
            _slog("2026-10-25T00:00:02Z", "after", detail="a" * 40),
        ],
    )

    report = _query(path, include=("match",), raw_bytes=5, context=1)

    event = report.events[0]
    assert event["raw_truncated"] is True
    assert len(event["raw"].encode("utf-8")) <= 5
    assert [line["role"] for line in event["context"]] == ["before", "after"]
    assert all(len(line["raw"].encode("utf-8")) <= 5 for line in event["context"])


def test_rotation_siblings_are_reported(tmp_path: Path) -> None:
    path = _write(tmp_path / "server.log", [_slog("2026-10-25T00:00:00Z")])
    _write(tmp_path / "server-1.log", ["old"])
    _write(tmp_path / "server-2.log", ["older"])

    report = _query(path)

    assert report.source.rotation_siblings == ["server-1.log", "server-2.log"]


def test_cli_returns_json_with_exit_zero_for_no_matches(tmp_path: Path, capsys) -> None:
    path = _write(tmp_path / "server.log", [_slog("2026-10-25T00:00:00Z", "present")])
    arguments = _parser().parse_args(
        ["ollama", "logs", "query", "--path", str(path), "--include", "absent"]
    )

    run_ollama_logs(arguments, tmp_path)

    output = json.loads(capsys.readouterr().out)
    assert output["counts"]["matched"] == 0
    assert output["events"] == []
    assert output["next_cursor"] is None


def test_cli_errors_are_json_on_stderr_with_exit_two(tmp_path: Path, capsys) -> None:
    arguments = _parser().parse_args(
        ["ollama", "logs", "query", "--path", str(tmp_path / "missing.log")]
    )

    with pytest.raises(SystemExit) as exit_info:
        run_ollama_logs(arguments, tmp_path)

    error = json.loads(capsys.readouterr().err)
    assert exit_info.value.code == 2
    assert error["error"]["code"] == "source_missing"


def test_cli_validation_errors_are_json_on_stderr(tmp_path: Path, capsys) -> None:
    arguments = _parser().parse_args(["ollama", "logs", "query", "--limit", "600"])

    with pytest.raises(SystemExit) as exit_info:
        run_ollama_logs(arguments, tmp_path)

    error = json.loads(capsys.readouterr().err)
    assert exit_info.value.code == 2
    assert error["error"]["code"] == "invalid_query"


def test_cli_invalid_field_filter_is_json_on_stderr(tmp_path: Path, capsys) -> None:
    path = _write(tmp_path / "server.log", [_slog("2026-10-25T00:00:00Z")])
    arguments = _parser().parse_args(
        ["ollama", "logs", "query", "--path", str(path), "--field", "not-a-pair"]
    )

    with pytest.raises(SystemExit) as exit_info:
        run_ollama_logs(arguments, tmp_path)

    error = json.loads(capsys.readouterr().err)
    assert exit_info.value.code == 2
    assert error["error"]["code"] == "invalid_field"


def test_cli_missing_subcommand_is_json_on_stderr(tmp_path: Path, capsys) -> None:
    arguments = _parser().parse_args(["ollama"])

    with pytest.raises(SystemExit) as exit_info:
        run_ollama_logs(arguments, tmp_path)

    error = json.loads(capsys.readouterr().err)
    assert exit_info.value.code == 2
    assert error["error"]["code"] == "invalid_query"


@pytest.mark.parametrize("kind", ["message", "field", "malformed"])
def test_large_parsed_content_cannot_escape_output_cap(tmp_path: Path, kind: str) -> None:
    large = "é" * 100_000
    lines = {
        "message": _slog("2026-10-25T00:00:00Z", large),
        "field": _slog("2026-10-25T00:00:00Z", detail=large),
        "malformed": large,
    }
    path = _write(tmp_path / "server.log", [lines[kind]])
    with pytest.raises(LogQueryError) as error:
        _query(path, raw_bytes=0, include_raw=False, max_output_bytes=1_024)
    assert error.value.code == "event_too_large"
    assert len(str(error.value).encode()) < 200


def test_metadata_alone_must_fit_output_budget(tmp_path: Path) -> None:
    path = tmp_path / "server.log"
    path.write_bytes(b"")
    with pytest.raises(LogQueryError) as error:
        _query(path, max_output_bytes=1_024)
    assert error.value.code == "output_budget_too_small"


def test_oversized_line_is_terminal_instead_of_repeating_cursor(tmp_path: Path) -> None:
    path = tmp_path / "server.log"
    path.write_bytes(b"x" * (log_query.MAX_LINE_BYTES + 1) + b"\nvalid later\n")
    with pytest.raises(LogQueryError) as error:
        _query(path)
    assert error.value.code == "record_too_large"


def test_scan_budget_cannot_return_no_progress_cursor(tmp_path: Path) -> None:
    path = _write(tmp_path / "server.log", ["x" * 2_000, "later"])
    with pytest.raises(LogQueryError) as error:
        _query(path, max_scan_bytes=1_024)
    assert error.value.code == "scan_budget_too_small"


@pytest.mark.parametrize("change", ["append", "rotate", "rewrite", "remove"])
def test_in_query_source_changes_return_error_not_mixed_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    path = _write(
        tmp_path / "server.log",
        [
            _slog("2026-10-25T00:00:00Z", "original"),
            _slog("2026-10-25T00:00:01Z", "old context"),
        ],
    )
    consume = log_query._consume

    def changed(scan, raw, offset, consumed, line):
        consume(scan, raw, offset, consumed, line)
        if line == 1:
            _change_source(path, change)

    monkeypatch.setattr(log_query, "_consume", changed)
    with pytest.raises(LogQueryError) as error:
        _query(path, context=1, limit=1)
    assert error.value.code == "source_changed"


def _change_source(path: Path, change: str) -> None:
    if change == "append":
        with path.open("a") as handle:
            handle.write(_slog("2026-10-25T00:00:02Z", "appended") + "\n")
        return
    if change == "rotate":
        path.rename(path.with_name("server-1.log"))
        _write(path, ["replacement", "new context"])
        return
    if change == "remove":
        path.unlink()
        return
    path.write_text(path.read_text().replace("original", "modified"))


def test_rotation_before_context_never_reads_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write(
        tmp_path / "server.log", [_slog("2026-10-25T00:00:00Z", "original"), "old context"]
    )
    context = log_query._context
    observed = []

    def rotated(scan, event, end_offset):
        _change_source(path, "rotate")
        result = context(scan, event, end_offset)
        observed.extend(result)
        return result

    monkeypatch.setattr(log_query, "_context", rotated)
    with pytest.raises(LogQueryError) as error:
        _query(path, include=("original",), context=1)
    assert error.value.code == "source_changed"
    assert observed[0]["raw"] == "old context"


def test_cli_never_prints_over_budget_response(tmp_path: Path, capsys) -> None:
    path = _write(tmp_path / "server.log", [_slog("2026-10-25T00:00:00Z", "x" * 100_000)])
    arguments = _parser().parse_args(
        [
            "ollama",
            "logs",
            "query",
            "--path",
            str(path),
            "--max-output-bytes",
            "1024",
            "--raw-bytes",
            "0",
        ]
    )
    with pytest.raises(SystemExit) as error:
        run_ollama_logs(arguments, tmp_path)
    captured = capsys.readouterr()
    assert error.value.code == 2
    assert captured.out == ""
    assert len(captured.err.encode()) <= 1024
    assert json.loads(captured.err)["error"]["code"] == "event_too_large"


def test_indented_serialization_also_obeys_total_cap(tmp_path: Path) -> None:
    path = _write(tmp_path / "server.log", [_slog("2026-10-25T00:00:00Z")])
    report = _query(path, max_output_bytes=2_500)
    assert len(serialize_report(report).encode()) <= 2_500
    with pytest.raises(LogQueryError) as error:
        serialize_report(report, indent=8)
    assert error.value.code == "output_budget_too_small"
