"""Repeatable Wikipedia source acquisition, extraction, and local JSON querying.

Run ``uv run python -m congressional_globe.wikipedia --help``. No models are used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode

from congressional_globe.wiki_districts import extract_districts
from congressional_globe.wiki_house import extract_house
from congressional_globe.wiki_records import WikiRecord, district_record, member_record
from congressional_globe.wiki_senate import extract_senate
from congressional_globe.wiki_sources import TITLES, fetch_sources, read_snapshot, write_json


def extract(sources: Path, output: Path) -> dict:
    snapshots = {key: read_snapshot(sources, key) for key in TITLES}
    records = _records(snapshots)
    identifiers = [record.record_id for record in records]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate record identities; inspect source before exporting")
    output.mkdir(parents=True, exist_ok=False)
    serialized = "".join(record.model_dump_json() + "\n" for record in records)
    (output / "records.jsonl").write_text(serialized)
    manifest = _manifest(snapshots, records, serialized)
    write_json(output / "manifest.json", manifest)
    write_json(output / "record.schema.json", WikiRecord.model_json_schema())
    write_json(output / "actions.json", _actions(sources, output))
    return manifest


def _records(snapshots: dict) -> list[WikiRecord]:
    members = [member_record("house", row) for row in extract_house(snapshots["house"][1])]
    members.extend(member_record("senate", row) for row in extract_senate(snapshots["senate"][1]))
    districts = [district_record(row) for row in extract_districts(snapshots["districts"][1])]
    counts: Counter[str] = Counter(record.source_id for record in [*members, *districts])
    _check_counts(counts)
    return [*members, *districts]


def _check_counts(counts: Counter[str]) -> None:
    if any(counts[key] == 0 for key in TITLES):
        raise ValueError("A requested page produced no records; inspect source layout")


def _manifest(snapshots: dict, records: list[WikiRecord], serialized: str) -> dict:
    return {
        "schema_version": "wikipedia-candidates-v1",
        "extractor_sha256": _code_hashes(),
        "sources": [_source_manifest(key, value[0]) for key, value in snapshots.items()],
        "counts": dict(Counter(record.kind for record in records)),
        "records_sha256": hashlib.sha256(serialized.encode()).hexdigest(),
        "scope": "39th Congress membership lists cover both sessions, not first-session attendance",
        "limitations": [
            "Wikipedia extraction is unverified; no Bioguide or official service crosscheck yet.",
            "Seniority dates are not service intervals; all individual service dates remain null.",
            "Party strings are source labels, not independently verified temporal affiliations.",
            "District directory mixes historical/current entries; 39th applicability is unknown.",
            "District lists only: overview population/representation tables are not exported.",
            "House/delegate state codes use displayed district codes; territories included.",
            "Non-voting list entries without a congressional-district link are not exported.",
            "Membership inclusion does not establish that a person spoke in a given passage.",
        ],
        "attribution": "Wikipedia contributors; retain page revisions and CC BY-SA attribution.",
    }


def _source_manifest(key: str, metadata) -> dict:
    parameters = urlencode({"title": TITLES[key], "oldid": metadata.revision_id})
    return {
        **metadata.model_dump(),
        "permanent_url": f"https://en.wikipedia.org/w/index.php?{parameters}",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
    }


def _code_hashes() -> dict[str, str]:
    names = (
        "wikipedia.py",
        "wiki_records.py",
        "wiki_sources.py",
        "wiki_house.py",
        "wiki_senate.py",
        "wiki_districts.py",
    )
    base = Path(__file__).parent
    return {name: hashlib.sha256((base / name).read_bytes()).hexdigest() for name in names}


def _actions(sources: Path, output: Path) -> dict:
    prefix = ["uv", "run", "python", "-m", "congressional_globe.wikipedia"]
    return {
        "working_directory": "repository root",
        "network_policy": "fetch contacts three requested pages; extract/query are offline",
        "actions": {
            "fetch_new_snapshot": [*prefix, "fetch", "--sources", "NEW_SNAPSHOT_DIRECTORY"],
            "replay_saved_snapshot": [
                *prefix,
                "extract",
                "--sources",
                str(sources),
                "--output",
                "NEW_OUTPUT_DIRECTORY",
            ],
            "query_member": [
                *prefix,
                "query",
                str(output / "records.jsonl"),
                "--where",
                "name=Stevens",
            ],
            "query_ohio_members": [
                *prefix,
                "query",
                str(output / "records.jsonl"),
                "--where",
                "state=OH",
            ],
            "query_district_directory": [
                *prefix,
                "query",
                str(output / "records.jsonl"),
                "--where",
                "section=Ohio",
            ],
        },
        "matching": "Case-insensitive literal substring; AND filters; null never matches.",
        "output_policy": "Fresh output directories required; no snapshot/export overwrites.",
    }


def query(path: Path, filters: list[str]) -> list[dict]:
    conditions = [_condition(value) for value in filters]
    with path.open() as stream:
        records = (WikiRecord.model_validate_json(line) for line in stream)
        return [record.model_dump() for record in records if _matches(record, conditions)]


def _condition(value: str) -> tuple[str, str]:
    field, separator, needle = value.partition("=")
    if not separator or field not in WikiRecord.model_fields or not needle:
        raise ValueError("Use --where FIELD=TEXT with a record field and nonempty literal text")
    return field, needle.casefold()


def _matches(record: WikiRecord, conditions: list[tuple[str, str]]) -> bool:
    return all(_contains(getattr(record, field), needle) for field, needle in conditions)


def _contains(value: object, needle: str) -> bool:
    return value is not None and needle in str(value).casefold()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch", help="Download three pages into a new source directory")
    fetch.add_argument("--sources", type=Path, required=True)
    replay = commands.add_parser("extract", help="Validate snapshot hashes and extract offline")
    replay.add_argument("--sources", type=Path, required=True)
    replay.add_argument("--output", type=Path, required=True)
    lookup = commands.add_parser(
        "query", help="Read validated JSONL; literal filters combine with AND"
    )
    lookup.add_argument("records", type=Path)
    lookup.add_argument("--where", action="append", default=[])
    return parser


def main() -> None:
    arguments = _parser().parse_args()
    handlers = {"fetch": _fetch_command, "extract": _extract_command, "query": _query_command}
    try:
        handlers[arguments.command](arguments)
    except (ValueError, OSError) as error:
        sys.exit(str(error))


def _fetch_command(arguments: argparse.Namespace) -> None:
    fetch_sources(arguments.sources)


def _extract_command(arguments: argparse.Namespace) -> None:
    print(json.dumps(extract(arguments.sources, arguments.output), indent=2))


def _query_command(arguments: argparse.Namespace) -> None:
    print(json.dumps(query(arguments.records, arguments.where), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
