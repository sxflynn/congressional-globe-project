"""Offline, JSON-based agent operations for the human review desk."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from congressional_globe.review_models import ReviewPacket
from congressional_globe.review_store import ReviewStore


def database_path() -> Path:
    return Path(os.environ.get("GLOBE_REVIEW_DATABASE", "artifacts/human-review/reviews.sqlite"))


def add_review_commands(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("review", help="Manage human review packets; no model calls")
    command.add_argument("--database", type=Path, default=database_path())
    actions = command.add_subparsers(dest="review_action", required=True)
    register = actions.add_parser("register", help="Register an immutable JSON packet version")
    register.add_argument("packet", type=Path)
    actions.add_parser("inbox", help="Read submitted reviews awaiting agent application")
    actions.add_parser("list", help="List registered packet versions")
    export = actions.add_parser("export", help="Archive exact packet, answers and receipt")
    export.add_argument("submission_id")
    export.add_argument("--output", type=Path, required=True)
    applied = actions.add_parser("applied", help="Record a completed plan/archive commit reference")
    applied.add_argument("submission_id")
    applied.add_argument("--reference", required=True)
    schema = actions.add_parser("schema", help="Print the packet schema")
    schema.set_defaults(review_action="schema")


def run_review(arguments: argparse.Namespace, _: Path) -> None:
    if arguments.review_action == "schema":
        _print(ReviewPacket.model_json_schema())
        return
    store = ReviewStore(arguments.database)
    _print(_dispatch(store, arguments))


def _dispatch(store: ReviewStore, arguments: argparse.Namespace) -> object:
    handlers = {
        "register": lambda: store.register(
            ReviewPacket.model_validate_json(arguments.packet.read_text(encoding="utf-8"))
        ),
        "inbox": lambda: store.submissions(pending_only=True),
        "list": store.packets,
        "export": lambda: _export(store, arguments),
        "applied": lambda: store.mark_applied(arguments.submission_id, arguments.reference),
    }
    return handlers[arguments.review_action]()


def _export(store: ReviewStore, arguments: argparse.Namespace) -> dict:
    result = store.export(arguments.submission_id)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    with arguments.output.open("x", encoding="utf-8") as output:
        output.write(serialized)
    return {"output": str(arguments.output), "submission_id": arguments.submission_id}


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))
