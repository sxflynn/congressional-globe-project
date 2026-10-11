"""Source discovery and completeness reporting."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

PARTS = {
    "congressionalg7391unit": 1,
    "congressionalglo7392unit": 2,
    "congressionalglo7393unit": 3,
    "congressionalglo00unit": 4,
    "congressionalglo7395unit": 5,
}
DERIVATIVES = ("hocr.html", "djvu.xml", "page_numbers.json")


@dataclass(frozen=True)
class SourceFile:
    path: Path
    size_bytes: int
    sha256: str | None


def expected_paths(root: Path, identifier: str) -> dict[str, Path]:
    return {suffix: root / f"{identifier}_{suffix}" for suffix in DERIVATIVES}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory(root: Path, include_hashes: bool) -> dict[str, dict[str, SourceFile | None]]:
    return {identifier: _inventory_part(root, identifier, include_hashes) for identifier in PARTS}


def _inventory_part(
    root: Path, identifier: str, include_hashes: bool
) -> dict[str, SourceFile | None]:
    return {
        suffix: _source_file(path, include_hashes)
        for suffix, path in expected_paths(root, identifier).items()
    }


def _source_file(path: Path, include_hashes: bool) -> SourceFile | None:
    if not path.is_file():
        return None
    return SourceFile(path, path.stat().st_size, sha256_file(path) if include_hashes else None)
