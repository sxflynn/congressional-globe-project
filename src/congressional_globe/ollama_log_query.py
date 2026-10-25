"""Read-only, bounded, deterministic queries over Ollama-style server logs."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

PARSER_VERSION = "ollama-log-query-v2"
DEFAULT_PATH = "~/.ollama/logs/server.log"
MAX_LINE_BYTES = 1_048_576
HEAD_BYTES = 65_536
CONTEXT_WINDOW_BYTES = 65_536
ParseStatus = Literal["parsed", "continuation", "malformed", "blank", "oversized"]
_PAIR_PATTERN = re.compile(r'\s*([^\s=]+)=("(?:\\.|[^"\\])*"|\S*)')
_DIRECT_EVENT_FIELDS = frozenset(("level", "component", "source", "message", "parse_status"))
_HTTP_EVENT_FIELDS = frozenset(("status", "method", "path", "route", "duration", "client"))


class LogQueryError(Exception):
    """A deterministic, user-facing query failure with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class HttpInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    method: str
    path: str
    status: int
    duration: str | None = None
    client: str | None = None


class LogEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    line: int = Field(ge=1)
    byte_offset: int = Field(ge=0)
    timestamp: str | None
    level: str | None
    component: str | None
    source: str | None
    message: str | None
    fields: dict[str, str]
    http: HttpInfo | None
    parse_status: ParseStatus
    raw: str | None
    raw_truncated: bool = False


class LogQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    since: datetime | None = None
    until: datetime | None = None
    assume_tz: str = "local"
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    ignore_case: bool = False
    levels: tuple[str, ...] = ()
    components: tuple[str, ...] = ()
    statuses: tuple[int, ...] = ()
    methods: tuple[str, ...] = ()
    parse_statuses: tuple[ParseStatus, ...] = ()
    fields: tuple[tuple[str, str], ...] = ()
    limit: int = Field(default=50, ge=1, le=500)
    max_output_bytes: int = Field(default=262_144, ge=1_024, le=4_194_304)
    max_scan_bytes: int = Field(default=67_108_864, ge=1_024, le=536_870_912)
    raw_bytes: int = Field(default=512, ge=0, le=8_192)
    include_raw: bool = True
    context: int = Field(default=0, ge=0, le=5)


class SourceReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    device: int
    inode: int
    size: int
    mtime_ns: int
    head_sha256: str
    rotation_siblings: list[str]
    scanned_bytes: int
    scanned_lines: int
    start_offset: int


class Counts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    matched: int
    returned: int
    by_level: dict[str, int]
    by_component: dict[str, int]
    by_status: dict[str, int]
    by_method: dict[str, int]
    by_parse_status: dict[str, int]
    missing_timestamp_excluded: int
    scanned_lines: int
    parsed_lines: int


class Completeness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    complete: bool
    has_more: bool
    stopped_at_eof: bool
    scan_limit_reached: bool
    output_limit_reached: bool
    appended_since_cursor: bool
    notes: list[str]


class QueryReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    parser_version: str
    query: dict[str, Any]
    query_hash: str
    source: SourceReport
    counts: Counts
    completeness: Completeness
    events: list[dict[str, Any]]
    next_cursor: str | None
    warnings: list[str]


class CursorState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    parser_version: str
    query_hash: str
    path: str
    device: int
    inode: int
    size: int
    mtime_ns: int
    head_bytes: int = Field(ge=0)
    head_sha256: str
    prefix_sha256: str
    prefix_start: int
    next_offset: int = Field(ge=0)
    next_line: int = Field(ge=1)


@dataclass
class _Scan:
    query: LogQuery
    since: datetime | None
    until: datetime | None
    zone: Any
    path: Path
    handle: Any
    snapshot_size: int
    start_offset: int
    start_line: int
    events: list[dict[str, Any]] = field(default_factory=list)
    matched: int = 0
    returned: int = 0
    missing_timestamp: int = 0
    scanned_bytes: int = 0
    scanned_lines: int = 0
    levels: Counter[str] = field(default_factory=Counter)
    components: Counter[str] = field(default_factory=Counter)
    statuses: Counter[str] = field(default_factory=Counter)
    methods: Counter[str] = field(default_factory=Counter)
    parse_statuses: Counter[str] = field(default_factory=Counter)
    parsed_lines: int = 0
    output_bytes: int = 0
    output_full: bool = False
    scan_limit: bool = False
    stopped_at_eof: bool = True
    next_offset: int | None = None
    next_line: int | None = None
    warnings: list[str] = field(default_factory=list)


def query_log(query: LogQuery, cursor_token: str | None = None) -> QueryReport:
    path = Path(query.path).expanduser().resolve()
    _require_source(path)
    query_hash = _query_hash(query, path)
    cursor = _decode_cursor(cursor_token) if cursor_token else None
    with path.open("rb") as handle:
        snapshot = _snapshot(handle, path)
        start_offset, start_line, appended = _resume(cursor, handle, query_hash, path)
        scan = _Scan(
            query=query,
            since=_normalize(query.since, query.assume_tz),
            until=_normalize(query.until, query.assume_tz),
            zone=_zone(query.assume_tz),
            path=path,
            handle=handle,
            snapshot_size=snapshot.size,
            start_offset=start_offset,
            start_line=start_line,
        )
        _scan(handle, scan)
        report = _bounded_report(scan, snapshot, query_hash, path, appended)
        _check_snapshot(handle, path, snapshot)
        return report


def _bounded_report(
    scan: _Scan, snapshot: _Snapshot, query_hash: str, path: Path, appended: bool
) -> QueryReport:
    while True:
        cursor = _next_cursor(scan, snapshot, query_hash, path)
        report = _report(scan, snapshot, query_hash, path, appended, cursor)
        if len((json.dumps(report.model_dump()) + "\n").encode()) <= scan.query.max_output_bytes:
            return report
        _reduce_output(scan)


def _reduce_output(scan: _Scan) -> None:
    if not scan.events:
        raise LogQueryError(
            "output_budget_too_small", "Increase max_output_bytes for query metadata"
        )
    if len(scan.events) == 1:
        raise LogQueryError(
            "event_too_large", "Event exceeds output budget; increase max_output_bytes"
        )
    event = scan.events.pop()
    scan.returned -= 1
    scan.output_full = True
    _hold(scan, event["byte_offset"], event["line"])


def serialize_report(report: QueryReport, indent: int | None = None) -> str:
    text = json.dumps(report.model_dump(), indent=indent) + "\n"
    if len(text.encode()) > report.query["max_output_bytes"]:
        raise LogQueryError(
            "output_budget_too_small", "Serialized response exceeds max_output_bytes"
        )
    return text


def _report(
    scan: _Scan,
    snapshot: _Snapshot,
    query_hash: str,
    path: Path,
    appended: bool,
    next_cursor: str | None,
) -> QueryReport:
    query = scan.query
    return QueryReport(
        parser_version=PARSER_VERSION,
        query=_query_payload(query, path),
        query_hash=query_hash,
        source=SourceReport(
            path=str(path),
            device=snapshot.device,
            inode=snapshot.inode,
            size=snapshot.size,
            mtime_ns=snapshot.mtime_ns,
            head_sha256=snapshot.head_sha256,
            rotation_siblings=_rotation_siblings(path),
            scanned_bytes=scan.scanned_bytes,
            scanned_lines=scan.scanned_lines,
            start_offset=scan.start_offset,
        ),
        counts=Counts(
            matched=scan.matched,
            returned=scan.returned,
            by_level=dict(sorted(scan.levels.items())),
            by_component=dict(sorted(scan.components.items())),
            by_status=dict(sorted(scan.statuses.items())),
            by_method=dict(sorted(scan.methods.items())),
            by_parse_status=dict(sorted(scan.parse_statuses.items())),
            missing_timestamp_excluded=scan.missing_timestamp,
            scanned_lines=scan.scanned_lines,
            parsed_lines=scan.parsed_lines,
        ),
        completeness=Completeness(
            complete=scan.stopped_at_eof and not scan.scan_limit,
            has_more=scan.next_offset is not None,
            stopped_at_eof=scan.stopped_at_eof,
            scan_limit_reached=scan.scan_limit,
            output_limit_reached=scan.output_full,
            appended_since_cursor=appended,
            notes=_notes(scan, appended),
        ),
        events=scan.events,
        next_cursor=next_cursor,
        warnings=scan.warnings,
    )


@dataclass(frozen=True)
class _Snapshot:
    device: int
    inode: int
    size: int
    mtime_ns: int
    head_bytes: int
    head_sha256: str


def _require_source(path: Path) -> None:
    if not path.exists():
        raise LogQueryError("source_missing", f"Log file does not exist: {path}")
    if not path.is_file():
        raise LogQueryError("source_not_file", f"Log path is not a regular file: {path}")


def _snapshot(handle: Any, path: Path) -> _Snapshot:
    stat = os.fstat(handle.fileno())
    handle.seek(0)
    head = handle.read(min(stat.st_size, HEAD_BYTES))
    return _Snapshot(
        device=stat.st_dev,
        inode=stat.st_ino,
        size=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        head_bytes=len(head),
        head_sha256=_sha256(head),
    )


def _check_snapshot(handle: Any, path: Path, snapshot: _Snapshot) -> None:
    current = os.fstat(handle.fileno())
    try:
        named = path.stat()
    except OSError as error:
        raise LogQueryError("source_changed", "Log changed during query; retry") from error
    identity = (named.st_dev, named.st_ino)
    expected = (snapshot.device, snapshot.inode)
    changed = (current.st_size, current.st_mtime_ns) != (snapshot.size, snapshot.mtime_ns)
    if identity != expected or changed:
        raise LogQueryError("source_changed", "Log changed during query; retry")


def _rotation_siblings(path: Path) -> list[str]:
    names = {candidate.name for candidate in path.parent.glob(f"{path.stem}-*{path.suffix}")}
    names.update(
        candidate.name for candidate in path.parent.glob(f"{path.name}.*") if candidate != path
    )
    return sorted(names)


def _query_hash(query: LogQuery, path: Path) -> str:
    payload = _selection_payload(query, path)
    return _sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


def _selection_payload(query: LogQuery, path: Path) -> dict[str, Any]:
    return {
        "parser_version": PARSER_VERSION,
        "path": str(path.resolve()),
        "since": _iso_or_none(_normalize(query.since, query.assume_tz)),
        "until": _iso_or_none(_normalize(query.until, query.assume_tz)),
        "assume_tz": query.assume_tz,
        "include": list(query.include),
        "exclude": list(query.exclude),
        "ignore_case": query.ignore_case,
        "levels": list(query.levels),
        "components": list(query.components),
        "statuses": list(query.statuses),
        "methods": list(query.methods),
        "parse_statuses": list(query.parse_statuses),
        "fields": [list(item) for item in query.fields],
    }


def _query_payload(query: LogQuery, path: Path) -> dict[str, Any]:
    payload = _selection_payload(query, path)
    payload["time_rules"] = {
        "since": "inclusive",
        "until": "exclusive",
        "naive_timestamps": "interpreted with assume_tz, then compared in UTC",
    }
    payload["assume_tz_resolved"] = str(_zone(query.assume_tz))
    payload["order"] = "source byte offset ascending"
    payload["limit"] = query.limit
    payload["max_output_bytes"] = query.max_output_bytes
    payload["max_scan_bytes"] = query.max_scan_bytes
    payload["raw_bytes"] = query.raw_bytes
    payload["include_raw"] = query.include_raw
    payload["context"] = query.context
    return payload


def _iso_or_none(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


def _zone(name: str) -> Any:
    if name in ("local", "", None):
        return _local_zone()
    if name.upper() == "UTC":
        return UTC
    try:
        return ZoneInfo(name)
    except Exception as error:
        raise LogQueryError("invalid_timezone", f"Unknown timezone: {name}") from error


def _local_zone() -> Any:
    configured = (os.environ.get("TZ") or "").lstrip(":")
    if configured and (zone := _try_zone(configured)):
        return zone
    local_name = _local_zone_name()
    if local_name and (zone := _try_zone(local_name)):
        return zone
    return datetime.now().astimezone().tzinfo


def _try_zone(name: str) -> Any:
    try:
        return ZoneInfo(name)
    except Exception:
        return None


def _local_zone_name() -> str | None:
    try:
        target = Path("/etc/localtime").resolve()
        index = target.parts.index("zoneinfo")
        return "/".join(target.parts[index + 1 :])
    except (OSError, ValueError):
        return None


def _normalize(value: datetime | None, assume_tz: str) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=_zone(assume_tz))
    return value.astimezone(UTC)


def _parse_timestamp(value: str | None, zone: Any) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(UTC)


def _parse_gin_timestamp(date_text: str, time_text: str, zone: Any) -> datetime | None:
    try:
        parsed = datetime.strptime(f"{date_text} {time_text}", "%Y/%m/%d %H:%M:%S")
    except ValueError:
        return None
    return parsed.replace(tzinfo=zone).astimezone(UTC)


def _component(source: str | None) -> str | None:
    if not source:
        return None
    return source.split(":", 1)[0]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_pairs(text: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    position = 0
    while match := _PAIR_PATTERN.match(text, position):
        token = match.group(2)
        value = _unescape(token[1:-1]) if token.startswith('"') else token
        pairs[match.group(1)] = value
        position = match.end()
    return pairs


def _unescape(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value


def _slog_event(raw: str, line: int, offset: int, zone: Any) -> LogEvent | None:
    pairs = _read_pairs(raw)
    if "time" not in pairs or "level" not in pairs:
        return None
    message = pairs.pop("msg", None)
    source = pairs.pop("source", None)
    timestamp = pairs.pop("time", None)
    level = pairs.pop("level", None)
    return _event(
        line=line,
        offset=offset,
        raw=raw,
        timestamp=timestamp,
        level=level,
        source=source,
        message=message,
        fields=pairs,
        http=_slog_http(message, pairs),
        status="parsed",
        zone=zone,
    )


def _slog_http(message: str | None, pairs: dict[str, str]) -> HttpInfo | None:
    if message != "ServeHTTP":
        return None
    method = pairs.get("method")
    path = pairs.get("path") or pairs.get("route")
    status = _status_code(pairs.get("status"))
    if not method or not path or status is None:
        return None
    return HttpInfo(
        method=method.upper(),
        path=path,
        status=status,
        duration=pairs.get("took") or pairs.get("duration"),
        client=pairs.get("client"),
    )


def _status_code(value: str | None) -> int | None:
    if not value:
        return None
    head = value.split()[0].rstrip(",")
    return int(head) if head.isdigit() else None


def _gin_event(raw: str, line: int, offset: int, zone: Any) -> LogEvent | None:
    parsed = _gin_parts(raw)
    if parsed is None:
        return None
    stamp_parts, http = parsed
    return _event(
        line=line,
        offset=offset,
        raw=raw,
        timestamp=None,
        level=None,
        source="gin",
        message=f"{http.method} {http.path}",
        fields={"status": str(http.status), "duration": http.duration or ""},
        http=http,
        status="parsed",
        zone=zone,
        stamp=_parse_gin_timestamp(stamp_parts[0], stamp_parts[1], zone),
    )


def _gin_parts(raw: str) -> tuple[list[str], HttpInfo] | None:
    prefix = _gin_prefix(raw)
    if prefix is None:
        return None
    parsed = _gin_fields(raw[len(prefix) :])
    if parsed is None:
        return None
    parts, stamp_parts = parsed
    method, path = _gin_request(parts[4])
    if not method or not path:
        return None
    http = HttpInfo(
        method=method,
        path=path,
        status=int(parts[1]),
        duration=parts[2] or None,
        client=parts[3] or None,
    )
    return stamp_parts, http


def _gin_fields(text: str) -> tuple[list[str], list[str]] | None:
    parts = [part.strip() for part in text.split("|")]
    if len(parts) != 5:
        return None
    stamp_parts = parts[0].split(" - ")
    if len(stamp_parts) != 2:
        return None
    if not parts[1].isdigit():
        return None
    return parts, stamp_parts


def _gin_prefix(raw: str) -> str | None:
    for prefix in ("[GIN] ", "GIN "):
        if raw.startswith(prefix):
            return prefix
    return None


def _gin_request(value: str) -> tuple[str, str]:
    method, _, path = value.strip().partition(" ")
    return method.strip().upper(), path.strip().strip('"')


def _json_event(raw: str, line: int, offset: int, zone: Any) -> LogEvent | None:
    if not raw.lstrip().startswith("{"):
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    fields = {key: _stringify(value) for key, value in payload.items()}
    timestamp = _first_present(fields, ("time", "@timestamp", "ts"))
    level = _first_present(fields, ("level", "severity"))
    source = _first_present(fields, ("source", "component"))
    message = _first_present(fields, ("msg", "message"))
    for key in (
        "time",
        "@timestamp",
        "ts",
        "level",
        "severity",
        "source",
        "component",
        "msg",
        "message",
    ):
        fields.pop(key, None)
    return _event(
        line=line,
        offset=offset,
        raw=raw,
        timestamp=timestamp,
        level=level,
        source=source,
        message=message,
        fields=fields,
        http=None,
        status="parsed",
        zone=zone,
    )


def _first_present(payload: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _stringify(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, sort_keys=True)


def _event(
    *,
    line: int,
    offset: int,
    raw: str,
    timestamp: str | None,
    level: str | None,
    source: str | None,
    message: str | None,
    fields: dict[str, str],
    http: HttpInfo | None,
    status: ParseStatus,
    zone: Any,
    stamp: datetime | None = None,
) -> LogEvent:
    resolved = stamp or _parse_timestamp(timestamp, zone)
    return LogEvent(
        line=line,
        byte_offset=offset,
        timestamp=_iso_or_none(resolved),
        level=level.lower() if level else None,
        component=_component(source),
        source=source,
        message=message,
        fields={key: value for key, value in fields.items() if value != ""},
        http=http,
        parse_status=status,
        raw=raw,
    )


def parse_event(raw: str, line: int, offset: int, zone: Any) -> LogEvent:
    for parser in (_gin_event, _json_event, _slog_event):
        event = parser(raw, line, offset, zone)
        if event is not None:
            return event
    return _event(
        line=line,
        offset=offset,
        raw=raw,
        timestamp=None,
        level=None,
        source=None,
        message=raw if raw.strip() else None,
        fields={},
        http=None,
        status=_unparsed_status(raw),
        zone=zone,
    )


def _unparsed_status(raw: str) -> ParseStatus:
    if not raw.strip():
        return "blank"
    return "continuation" if raw[0].isspace() else "malformed"


def _matches(event: LogEvent, scan: _Scan) -> bool:
    if not _matches_text(event, scan.query):
        return False
    if not _matches_fields(event, scan.query):
        return False
    return _matches_time(event, scan)


def _matches_text(event: LogEvent, query: LogQuery) -> bool:
    text = event.raw or ""
    if query.ignore_case:
        text = text.casefold()
    includes = [_fold(item, query.ignore_case) for item in query.include]
    excludes = [_fold(item, query.ignore_case) for item in query.exclude]
    return all(item in text for item in includes) and not any(item in text for item in excludes)


def _fold(value: str, ignore_case: bool) -> str:
    return value.casefold() if ignore_case else value


def _matches_fields(event: LogEvent, query: LogQuery) -> bool:
    checks = (
        _in_set(event.level, query.levels),
        _in_set(event.component, query.components),
        _status_match(event, query),
        _method_match(event, query),
        _parse_status_match(event, query),
        _field_match(event, query),
    )
    return all(checks)


def _in_set(value: str | None, allowed: tuple[str, ...]) -> bool:
    return not allowed or (value is not None and value in allowed)


def _status_match(event: LogEvent, query: LogQuery) -> bool:
    if not query.statuses:
        return True
    return event.http is not None and event.http.status in query.statuses


def _method_match(event: LogEvent, query: LogQuery) -> bool:
    if not query.methods:
        return True
    return event.http is not None and event.http.method.upper() in {
        item.upper() for item in query.methods
    }


def _parse_status_match(event: LogEvent, query: LogQuery) -> bool:
    return not query.parse_statuses or event.parse_status in query.parse_statuses


def _field_match(event: LogEvent, query: LogQuery) -> bool:
    return all(_event_value(event, key) == expected for key, expected in query.fields)


def _event_value(event: LogEvent, key: str) -> str | None:
    if key in _DIRECT_EVENT_FIELDS:
        return _direct_event_value(event, key)
    if key in _HTTP_EVENT_FIELDS:
        return _http_event_value(event, key) or event.fields.get(key)
    return event.fields.get(key)


def _direct_event_value(event: LogEvent, key: str) -> str | None:
    value = getattr(event, key)
    return value if value is not None else event.fields.get(key)


def _http_event_value(event: LogEvent, key: str) -> str | None:
    if event.http is None:
        return None
    value = event.http.path if key == "route" else getattr(event.http, key, None)
    return str(value) if value is not None else None


def _matches_time(event: LogEvent, scan: _Scan) -> bool:
    if scan.since is None and scan.until is None:
        return True
    if event.timestamp is None:
        scan.missing_timestamp += 1
        return False
    return _in_window(datetime.fromisoformat(event.timestamp), scan.since, scan.until)


def _in_window(moment: datetime, since: datetime | None, until: datetime | None) -> bool:
    return (since is None or moment >= since) and (until is None or moment < until)


def _scan(handle: Any, scan: _Scan) -> None:
    handle.seek(scan.start_offset)
    line = scan.start_line
    while scan.scanned_bytes < scan.query.max_scan_bytes:
        record = _read_record(handle, scan, line)
        if record is None:
            return
        raw, offset, consumed = record
        _consume(scan, raw, offset, consumed, line)
        scan.scanned_bytes += consumed
        line += 1
    _finish_scan_budget(handle, scan, line)


def _read_record(handle: Any, scan: _Scan, line: int) -> tuple[str, int, int] | None:
    remaining = scan.query.max_scan_bytes - scan.scanned_bytes
    offset = handle.tell()
    available = scan.snapshot_size - offset
    if available <= 0:
        return None
    cap = min(MAX_LINE_BYTES, remaining, available)
    payload = handle.readline(cap)
    if not payload:
        return None
    if _record_complete(payload, cap, offset, scan.snapshot_size):
        return payload.decode("utf-8", "replace").rstrip("\r\n"), offset, len(payload)
    _incomplete_record(scan, payload, offset, line)
    return None


def _record_complete(payload: bytes, cap: int, offset: int, size: int) -> bool:
    return payload.endswith(b"\n") or len(payload) < cap or offset + len(payload) >= size


def _incomplete_record(scan: _Scan, payload: bytes, offset: int, line: int) -> None:
    if len(payload) >= MAX_LINE_BYTES:
        raise LogQueryError(
            "record_too_large",
            f"Record at byte {offset} exceeds the per-line byte cap; cannot paginate past it",
        )
    _stop_for_limit(scan, offset, line)


def _finish_scan_budget(handle: Any, scan: _Scan, line: int) -> None:
    offset = handle.tell()
    if offset >= scan.snapshot_size:
        return
    scan.scan_limit = True
    scan.stopped_at_eof = False
    _hold(scan, offset, line)
    _warn(scan, "Scan budget ended at a line boundary; results are incomplete")


def _stop_for_limit(scan: _Scan, offset: int, line: int) -> None:
    if offset == scan.start_offset:
        raise LogQueryError(
            "scan_budget_too_small", "Increase max_scan_bytes to fit the next record"
        )
    scan.scan_limit = True
    scan.stopped_at_eof = False
    _hold(scan, offset, line)
    _warn(scan, "Scan budget ended mid-line; scan stopped before it")


def _warn(scan: _Scan, message: str) -> None:
    if message not in scan.warnings:
        scan.warnings.append(message)


def _consume(scan: _Scan, raw: str, offset: int, consumed: int, line: int) -> None:
    event = parse_event(raw, line, offset, scan.zone)
    scan.scanned_lines += 1
    scan.parse_statuses[event.parse_status] += 1
    if event.parse_status == "parsed":
        scan.parsed_lines += 1
    if _matches(event, scan):
        _matched(scan, event, line, offset, consumed)


def _matched(scan: _Scan, event: LogEvent, line: int, offset: int, consumed: int) -> None:
    scan.matched += 1
    _count_dimensions(scan, event)
    if scan.output_full:
        _hold(scan, offset, line)
        return
    rendered = _render(scan, event, offset + consumed)
    if _fits(scan, rendered):
        _keep(scan, rendered)
        return
    scan.output_full = True
    if scan.events:
        _hold(scan, offset, line)
        return
    raise LogQueryError("event_too_large", "Event exceeds output budget; increase max_output_bytes")


def _hold(scan: _Scan, offset: int, line: int) -> None:
    if scan.next_offset is None or offset < scan.next_offset:
        scan.next_offset = offset
    if scan.next_line is None or line < scan.next_line:
        scan.next_line = line


def _keep(scan: _Scan, rendered: dict[str, Any]) -> None:
    scan.events.append(rendered)
    scan.output_bytes += len(json.dumps(rendered, default=str).encode())
    scan.returned += 1


def _count_dimensions(scan: _Scan, event: LogEvent) -> None:
    if event.level:
        scan.levels[event.level] += 1
    if event.component:
        scan.components[event.component] += 1
    if event.http:
        scan.statuses[str(event.http.status)] += 1
        scan.methods[event.http.method] += 1


def _render(scan: _Scan, event: LogEvent, end_offset: int) -> dict[str, Any]:
    raw, truncated = _raw(scan, event)
    payload = event.model_dump()
    payload["raw"] = raw
    payload["raw_truncated"] = truncated
    payload["context"] = _context(scan, event, end_offset) if scan.query.context else []
    return payload


def _raw(scan: _Scan, event: LogEvent) -> tuple[str | None, bool]:
    if not scan.query.include_raw or event.raw is None:
        return None, False
    text, truncated = _truncate_bytes(event.raw, scan.query.raw_bytes)
    if truncated:
        _warn(scan, "At least one event raw line was truncated to raw_bytes")
    return text, truncated


def _context(scan: _Scan, event: LogEvent, end_offset: int) -> list[dict[str, Any]]:
    return _before(scan, event) + _after(scan, event, end_offset)


def _before(scan: _Scan, event: LogEvent) -> list[dict[str, Any]]:
    start = max(0, event.byte_offset - CONTEXT_WINDOW_BYTES)
    payload = _read_range(scan.handle, start, event.byte_offset)
    lines = payload.split(b"\n")
    if start > 0:
        lines = lines[1:]
    if lines and lines[-1] == b"":
        lines = lines[:-1]
    selected = lines[-scan.query.context :]
    base = event.line - len(selected)
    return [
        _context_line(raw, base + index, "before", scan.query.raw_bytes)
        for index, raw in enumerate(selected)
    ]


def _after(scan: _Scan, event: LogEvent, end_offset: int) -> list[dict[str, Any]]:
    payload = _read_range(
        scan.handle, end_offset, min(scan.snapshot_size, end_offset + CONTEXT_WINDOW_BYTES)
    )
    selected = payload.split(b"\n")[: scan.query.context]
    return [
        _context_line(raw, event.line + 1 + index, "after", scan.query.raw_bytes)
        for index, raw in enumerate(selected)
    ]


def _read_range(handle: Any, start: int, end: int) -> bytes:
    return os.pread(handle.fileno(), max(0, end - start), start)


def _context_line(raw: bytes, line: int, role: str, cap: int) -> dict[str, Any]:
    text, truncated = _truncate_bytes(raw.decode("utf-8", "replace").rstrip("\r"), cap)
    return {"line": line, "role": role, "raw": text, "raw_truncated": truncated}


def _truncate_bytes(text: str, cap: int) -> tuple[str, bool]:
    if cap <= 0:
        return "", bool(text)
    payload = text.encode("utf-8")
    if len(payload) <= cap:
        return text, False
    return payload[:cap].decode("utf-8", "ignore"), True


def _fits(scan: _Scan, rendered: dict[str, Any]) -> bool:
    if scan.returned >= scan.query.limit:
        return False
    size = len(json.dumps(rendered, default=str).encode())
    return scan.output_bytes + size <= scan.query.max_output_bytes


def _notes(scan: _Scan, appended: bool) -> list[str]:
    notes: list[str] = []
    if scan.scan_limit:
        notes.append("Scan stopped at max_scan_bytes or an oversized line; results are incomplete")
    if scan.output_full:
        notes.append("Output cap reached; continue with next_cursor for more matches")
    if appended:
        notes.append("File grew since the cursor was issued; appended events are included")
    if scan.query.context:
        notes.append("Context lines are bounded to a nearby byte window, not the full file")
    return notes


def _next_cursor(scan: _Scan, snapshot: _Snapshot, query_hash: str, path: Path) -> str | None:
    if scan.next_offset is None:
        return None
    prefix_start = max(0, scan.next_offset - HEAD_BYTES)
    prefix = _read_range(scan.handle, prefix_start, scan.next_offset)
    cursor = CursorState(
        parser_version=PARSER_VERSION,
        query_hash=query_hash,
        path=str(path),
        device=snapshot.device,
        inode=snapshot.inode,
        size=snapshot.size,
        mtime_ns=snapshot.mtime_ns,
        head_bytes=snapshot.head_bytes,
        head_sha256=snapshot.head_sha256,
        prefix_sha256=_sha256(prefix),
        prefix_start=prefix_start,
        next_offset=scan.next_offset,
        next_line=scan.next_line or 1,
    )
    payload = json.dumps(cursor.model_dump(), sort_keys=True, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(token: str) -> CursorState:
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(token + padding))
        return CursorState.model_validate(payload)
    except Exception as error:
        raise LogQueryError("invalid_cursor", "Cursor is not a valid continuation token") from error


def _resume(
    cursor: CursorState | None, handle: Any, query_hash: str, path: Path
) -> tuple[int, int, bool]:
    if cursor is None:
        return 0, 1, False
    _validate_cursor(cursor, handle, query_hash, path)
    size = os.fstat(handle.fileno()).st_size
    return cursor.next_offset, cursor.next_line, size > cursor.size


def _validate_cursor(cursor: CursorState, handle: Any, query_hash: str, path: Path) -> None:
    stat = os.fstat(handle.fileno())
    _check_cursor_context(cursor, query_hash)
    _check_file_identity(cursor, stat, path)
    _check_cursor_position(cursor, stat.st_size)
    _check_head(cursor, handle)
    _check_prefix(cursor, handle)


def _check_cursor_context(cursor: CursorState, query_hash: str) -> None:
    if cursor.parser_version != PARSER_VERSION:
        raise LogQueryError("stale_cursor", "Cursor was produced by another parser version")
    if cursor.query_hash != query_hash:
        raise LogQueryError("cursor_query_mismatch", "Cursor belongs to a different query")


def _check_file_identity(cursor: CursorState, stat: os.stat_result, path: Path) -> None:
    if cursor.path != str(path):
        raise LogQueryError("stale_cursor_rotated", "Log file identity changed since cursor")
    if cursor.device != stat.st_dev or cursor.inode != stat.st_ino:
        raise LogQueryError("stale_cursor_rotated", "Log file identity changed since cursor")


def _check_cursor_position(cursor: CursorState, size: int) -> None:
    if size < cursor.size:
        raise LogQueryError("stale_cursor_shrunk", "Log file shrank since cursor")
    if cursor.next_offset > size:
        raise LogQueryError("stale_cursor_offset", "Cursor offset is beyond the current file")


def _check_head(cursor: CursorState, handle: Any) -> None:
    handle.seek(0)
    if _sha256(handle.read(cursor.head_bytes)) != cursor.head_sha256:
        raise LogQueryError("stale_cursor_modified", "Log file prefix changed since cursor")


def _check_prefix(cursor: CursorState, handle: Any) -> None:
    start = max(0, cursor.next_offset - HEAD_BYTES)
    handle.seek(start)
    actual = _sha256(handle.read(cursor.next_offset - start))
    if actual != cursor.prefix_sha256 or start != cursor.prefix_start:
        raise LogQueryError("stale_cursor_modified", "Log content before the cursor changed")
