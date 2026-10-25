"""CLI adapter for bounded, read-only Ollama log queries."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_settings import CliApp, CliSubCommand, SettingsError

from congressional_globe.ollama_log_query import (
    DEFAULT_PATH,
    LogQuery,
    LogQueryError,
    ParseStatus,
    query_log,
)


class OllamaLogQueryCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(default=DEFAULT_PATH, description="Log file to scan")
    since: datetime | None = Field(default=None, description="Inclusive ISO 8601 lower bound")
    until: datetime | None = Field(default=None, description="Exclusive ISO 8601 upper bound")
    assume_tz: str = Field(
        default="local",
        description="Timezone for naive timestamps: local, UTC, offset or IANA name",
    )
    include: list[str] = Field(default_factory=list, description="Literal text that must appear")
    exclude: list[str] = Field(
        default_factory=list, description="Literal text that must not appear"
    )
    ignore_case: bool = Field(default=False, description="Case-insensitive include/exclude")
    level: list[str] = Field(default_factory=list, description="Allowed log level")
    component: list[str] = Field(default_factory=list, description="Allowed component/source file")
    status: list[int] = Field(default_factory=list, description="Allowed HTTP status code")
    method: list[str] = Field(default_factory=list, description="Allowed HTTP method")
    parse_status: list[ParseStatus] = Field(
        default_factory=list, description="Allowed parse status"
    )
    field: list[str] = Field(default_factory=list, description="Exact parsed field match KEY=VALUE")
    limit: int = Field(default=50, ge=1, le=500, description="Maximum returned events")
    max_output_bytes: int = Field(
        default=262_144, ge=1_024, le=4_194_304, description="Returned-event byte cap"
    )
    max_scan_bytes: int = Field(
        default=67_108_864, ge=1_024, le=536_870_912, description="Maximum bytes scanned"
    )
    raw_bytes: int = Field(
        default=512, ge=0, le=8_192, description="Maximum raw bytes retained per event"
    )
    raw: bool = Field(default=True, description="Include raw log lines in results")
    context: int = Field(default=0, ge=0, le=5, description="Surrounding lines per event")
    cursor: str | None = Field(default=None, description="Opaque continuation token")
    indent: int | None = Field(default=None, description="JSON indentation")

    def cli_cmd(self) -> None:
        report = query_log(self._query(), self.cursor)
        print(json.dumps(report.model_dump(), indent=self.indent))

    def _query(self) -> LogQuery:
        return LogQuery(
            path=str(Path(self.path).expanduser()),
            since=self.since,
            until=self.until,
            assume_tz=self.assume_tz,
            include=tuple(self.include),
            exclude=tuple(self.exclude),
            ignore_case=self.ignore_case,
            levels=tuple(item.lower() for item in self.level),
            components=tuple(self.component),
            statuses=tuple(self.status),
            methods=tuple(item.upper() for item in self.method),
            parse_statuses=tuple(self.parse_status),
            fields=tuple(_field(item) for item in self.field),
            limit=self.limit,
            max_output_bytes=self.max_output_bytes,
            max_scan_bytes=self.max_scan_bytes,
            raw_bytes=self.raw_bytes,
            include_raw=self.raw,
            context=self.context,
        )


class OllamaLogsCommand(BaseModel):
    query: CliSubCommand[OllamaLogQueryCommand]

    def cli_cmd(self) -> None:
        CliApp.run_subcommand(self, cli_exit_on_error=False)


class OllamaCommand(BaseModel):
    logs: CliSubCommand[OllamaLogsCommand]

    def cli_cmd(self) -> None:
        CliApp.run_subcommand(self, cli_exit_on_error=False)


def add_ollama_log_commands(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    command = commands.add_parser(
        "ollama",
        help="Query Ollama server logs deterministically (read-only, capped output)",
        usage="globe ollama logs query [options]",
        description=(
            "Read-only, bounded Ollama log queries. Run 'globe ollama logs query --help' for "
            "the full option list. Time windows are inclusive at --since and exclusive at "
            "--until; output is ordered by source byte offset with no follow mode."
        ),
    )
    command.add_argument("ollama_args", nargs=argparse.REMAINDER)


def run_ollama_logs(arguments: argparse.Namespace, _: Path) -> None:
    if not arguments.ollama_args:
        _fail(LogQueryError("invalid_query", "An ollama subcommand is required: logs query"))
    try:
        CliApp.run(
            OllamaCommand,
            cli_args=list(arguments.ollama_args),
            cli_exit_on_error=False,
        )
    except LogQueryError as error:
        _fail(error)
    except ValidationError as error:
        _fail(LogQueryError("invalid_query", _validation_message(error)))
    except SettingsError as error:
        _fail(LogQueryError("invalid_query", str(error)))
    except OSError as error:
        _fail(LogQueryError("source_unreadable", str(error)))


def _field(value: str) -> tuple[str, str]:
    key, separator, expected = value.partition("=")
    if not separator or not key:
        raise LogQueryError("invalid_field", f"Field filter must be KEY=VALUE: {value}")
    return key, expected


def _validation_message(error: ValidationError) -> str:
    parts = [
        f"{'.'.join(str(item) for item in detail['loc'])}: {detail['msg']}"
        for detail in error.errors()
    ]
    return "; ".join(parts)


def _fail(error: LogQueryError) -> None:
    print(json.dumps({"error": {"code": error.code, "message": str(error)}}), file=sys.stderr)
    raise SystemExit(2) from error
