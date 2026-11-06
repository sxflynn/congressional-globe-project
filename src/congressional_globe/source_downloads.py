"""Explicit, streamed restoration of pinned Internet Archive source bytes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Literal
from urllib.request import urlopen

from pydantic import BaseModel, ConfigDict, Field

from congressional_globe.inventory import DERIVATIVES, PARTS, sha256_file

MANIFEST = Path(__file__).parent / "data" / "source_downloads.json"


class SourceDownload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item: Literal[
        "congressionalg7391unit",
        "congressionalglo7392unit",
        "congressionalglo7393unit",
        "congressionalglo00unit",
        "congressionalglo7395unit",
    ]
    derivative: Literal["djvu.xml", "hocr.html", "page_numbers.json"]
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    archive_sha1: str = Field(pattern=r"^[0-9a-f]{40}$")

    @property
    def filename(self) -> str:
        return f"{self.item}_{self.derivative}"

    @property
    def url(self) -> str:
        return f"https://archive.org/download/{self.item}/{self.filename}"


def load_manifest() -> list[SourceDownload]:
    records = [SourceDownload.model_validate(row) for row in json.loads(MANIFEST.read_text())]
    expected = {f"{item}_{suffix}" for item in PARTS for suffix in DERIVATIVES}
    if len(records) != len(expected) or {row.filename for row in records} != expected:
        raise ValueError("Source manifest must contain exactly the fifteen source derivatives")
    return records


def verify_file(path: Path, record: SourceDownload) -> None:
    if path.stat().st_size != record.size_bytes or sha256_file(path) != record.sha256:
        raise ValueError(f"Source size/checksum mismatch; preserved for inspection: {path}")


def restore_file(directory: Path, record: SourceDownload) -> dict[str, str]:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / record.filename
    if target.exists():
        verify_file(target, record)
        return {"file": str(target), "status": "verified_existing"}
    partial = target.with_name(target.name + ".partial")
    _fetch(partial, record)
    verify_file(partial, record)
    # Link creation refuses to overwrite a file created by another process.
    os.link(partial, target)
    partial.unlink()
    return {"file": str(target), "status": "downloaded_verified"}


def _fetch(partial: Path, record: SourceDownload) -> None:
    # Exclusive creation retains interrupted/invalid bytes and prevents silent retries.
    with partial.open("xb") as output, urlopen(record.url, timeout=60) as response:
        _copy_bounded(response, output, record.size_bytes)


def _copy_bounded(response, output, limit: int) -> None:
    total = 0
    while block := response.read(1024 * 1024):
        total += len(block)
        if total > limit:
            raise ValueError("Source download exceeds pinned byte size; partial file preserved")
        output.write(block)


def add_source_commands(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("sources", help="Restore or verify pinned source downloads")
    actions = command.add_subparsers(dest="sources_action", required=True)
    for action in ("download", "verify"):
        parser = actions.add_parser(action)
        parser.add_argument("--directory", type=Path, default=Path("downloads"))


def run_sources(arguments: argparse.Namespace, _: Path) -> None:
    for record in load_manifest():
        print(json.dumps(_process(arguments, record)), flush=True)


def _process(arguments: argparse.Namespace, record: SourceDownload) -> dict[str, str]:
    if arguments.sources_action == "download":
        return restore_file(arguments.directory, record)
    target = arguments.directory / record.filename
    verify_file(target, record)
    return {"file": str(target), "status": "verified"}
