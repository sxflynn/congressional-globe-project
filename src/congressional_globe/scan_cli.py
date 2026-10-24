"""Explicit on-demand scan crop commands; no model requests or corpus edits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from congressional_globe.inventory import PARTS
from congressional_globe.scan_fetch import fetch_bundle, prepare_bundle, read_bundle
from congressional_globe.scan_geometry import prepare_target
from congressional_globe.scan_models import ScanTarget


def add_scan_commands(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("scan", help="Prepare/fetch a bounded original-scan crop")
    actions = command.add_subparsers(dest="scan_action", required=True)
    crop = actions.add_parser("crop", help="Plan offline; --fetch explicitly downloads regions")
    crop.add_argument("--root", type=Path, default=Path("."))
    crop.add_argument("--item", choices=PARTS, required=True)
    crop.add_argument("--leaf", type=int, required=True)
    crop.add_argument("--paragraph", required=True)
    crop.add_argument("--start", type=int, help="Original OCR Unicode character offset, inclusive")
    crop.add_argument("--end", type=int, help="Original OCR Unicode character offset, exclusive")
    crop.add_argument("--expected", help="Exact original OCR text at the selected offsets")
    crop.add_argument("--padding", type=int, default=64)
    crop.add_argument("--max-width", type=int, default=1600)
    crop.add_argument("--output", type=Path, required=True)
    crop.add_argument("--fetch", action="store_true")
    inspect = actions.add_parser("inspect", help="Verify and inspect a cached bundle offline")
    inspect.add_argument("directory", type=Path)


def run_scan(arguments: argparse.Namespace, _: Path) -> None:
    if arguments.scan_action == "inspect":
        print(read_bundle(arguments.directory).model_dump_json(indent=2))
        return
    target = prepare_target(
        arguments.root,
        arguments.item,
        arguments.leaf,
        arguments.paragraph,
        arguments.start,
        arguments.end,
        arguments.padding,
        arguments.max_width,
    )
    _check_expected(target, arguments.expected)
    target_hash = prepare_bundle(arguments.output, target)
    if arguments.fetch:
        print(fetch_bundle(arguments.output, target).model_dump_json(indent=2))
        return
    print(
        json.dumps(
            {
                "status": "offline_plan",
                "target_sha256": target_hash,
                "regions": len(target.regions),
                "provider_calls": 0,
                "next": "Repeat with --fetch to download these scan regions",
            },
            indent=2,
        )
    )


def _check_expected(target: ScanTarget, expected: str | None) -> None:
    if target.precision == "word-span" and expected is None:
        raise ValueError(
            "Raw-text spans require --expected; normalized-text offsets are not accepted"
        )
    if expected is not None and target.selection_text != expected:
        raise ValueError("Expected patch text does not match the original OCR selection")
