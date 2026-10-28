"""Hash-checked, explicitly supplied source-line registry; never inferred geometry."""

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from pydantic import Field, TypeAdapter

from congressional_globe.bracket_cues import Contract, SourceId
from congressional_globe.deterministic_models import OCRLine, ParagraphInput
from congressional_globe.scan_models import Sha256


class GeometryRecord(Contract):
    source_id: SourceId
    raw_sha256: Sha256
    page_line_sha256: Sha256
    lines: tuple[OCRLine, ...] = Field(min_length=1, max_length=256)


@dataclass(frozen=True)
class GeometryRegistry:
    data: bytes = field(repr=False)
    expected_sha256: str
    records: Mapping[str, GeometryRecord] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.data, bytes) or len(self.data) > 8 * 1024 * 1024:
            raise ValueError("geometry registry must be bytes within 8MiB")
        if hashlib.sha256(self.data).hexdigest() != self.expected_sha256:
            raise ValueError("geometry registry fingerprint mismatch")
        records = TypeAdapter(tuple[GeometryRecord, ...]).validate_json(self.data)
        by_id = _index_records(records)
        object.__setattr__(self, "records", MappingProxyType(by_id))

    def matches(self, source: ParagraphInput) -> bool:
        record = self.records.get(source.source.source_id)
        if record is None:
            raise ValueError("source missing from pinned geometry registry")
        expected = (record.raw_sha256, record.page_line_sha256, record.lines)
        actual = (source.source.raw_sha256, source.line_evidence_sha256, source.lines)
        if actual != expected:
            raise ValueError("declared lines disagree with pinned geometry registry")
        return True


def _index_records(records: tuple[GeometryRecord, ...]) -> dict[str, GeometryRecord]:
    if not records or len(records) > 32:
        raise ValueError("geometry registry needs 1 to32 explicit records")
    by_id = {r.source_id: r for r in records}
    if len(by_id) != len(records):
        raise ValueError("duplicate geometry source ID")
    return by_id
