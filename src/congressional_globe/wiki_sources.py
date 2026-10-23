"""Explicit download and hash-checked offline replay of three requested Wikipedia pages."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from congressional_globe.wiki_records import SourceSnapshot

TITLES = {
    "house": "List_of_United_States_representatives_in_the_39th_Congress",
    "senate": "List_of_United_States_senators_in_the_39th_Congress",
    "districts": "List_of_United_States_congressional_districts",
}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def fetch_sources(directory: Path) -> None:
    """Fetch only the requested pages into a fresh directory; never overwrite snapshots."""
    directory.mkdir(parents=True, exist_ok=False)
    for source_id, title in TITLES.items():
        _fetch_one(directory, source_id, title)


def _fetch_one(directory: Path, source_id: str, title: str) -> None:
    url = f"https://en.wikipedia.org/wiki/{title}"
    request = Request(url, headers={"User-Agent": "CongressionalGlobeResearch/0.1"})
    with urlopen(request, timeout=45) as response:
        payload = response.read()
        revision = re.search(rb'"wgRevisionId"\s*:\s*(\d+)', payload)
        metadata = SourceSnapshot.model_validate(
            {
                "source_id": source_id,
                "requested_url": url,
                "resolved_url": response.url,
                "retrieved_at_utc": datetime.now(UTC).isoformat(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
                "revision_id": revision[1].decode() if revision else None,
                "headers": {
                    key: response.headers.get(key) for key in ("last-modified", "content-type")
                },
            }
        )
    (directory / f"{source_id}.html").write_bytes(payload)
    write_json(directory / f"{source_id}.metadata.json", metadata.model_dump())


def read_snapshot(directory: Path, source_id: str) -> tuple[SourceSnapshot, str]:
    metadata = SourceSnapshot.model_validate_json(
        (directory / f"{source_id}.metadata.json").read_text()
    )
    payload = (directory / f"{source_id}.html").read_bytes()
    if metadata.source_id != source_id:
        raise ValueError("Source identity mismatch")
    if hashlib.sha256(payload).hexdigest() != metadata.sha256 or len(payload) != metadata.bytes:
        raise ValueError(f"Snapshot hash/size mismatch: {source_id}")
    return metadata, payload.decode("utf-8")
