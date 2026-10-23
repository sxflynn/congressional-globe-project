"""Validated, source-derived Wikipedia records; never verified historical authority."""

from __future__ import annotations

import hashlib
from typing import Literal
from urllib.parse import urljoin

from pydantic import BaseModel, ConfigDict, JsonValue


class SourceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: Literal["house", "senate", "districts"]
    requested_url: str
    resolved_url: str
    retrieved_at_utc: str
    sha256: str
    bytes: int
    revision_id: str | None
    headers: dict[str, str | None]


class WikiRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: str
    source_id: Literal["house", "senate", "districts"]
    kind: Literal["representative", "delegate", "senator", "district_directory_entry"]
    name: str
    linked_page: str | None = None
    chamber: Literal["house", "senate"] | None = None
    congress_number: Literal[39] | None = None
    party: str | None = None
    state: str | None = None
    district: str | None = None
    section: str | None = None
    verification_status: Literal["unverified_wikipedia_extraction"] = (
        "unverified_wikipedia_extraction"
    )
    service_start: None = None
    service_end: None = None
    applies_to_39th_congress: bool | None = None
    source_details: dict[str, JsonValue]


def _identity(source_id: str, link: str | None, name: str) -> str:
    digest = hashlib.sha256(f"{source_id}\n{link}\n{name}".encode()).hexdigest()[:24]
    return f"wikipedia:{source_id}:{digest}"


def member_record(source_id: Literal["house", "senate"], data: dict) -> WikiRecord:
    senate = source_id == "senate"
    name = data["full_name"] if senate else data["name"]
    link = data.get("person_url") if senate else data.get("person_page")
    return WikiRecord(
        record_id=_identity(source_id, link, name),
        source_id=source_id,
        kind="senator" if senate else data["kind"],
        name=name,
        linked_page=urljoin("https://en.wikipedia.org", link) if link else None,
        chamber="senate" if senate else "house",
        congress_number=39,
        party=data.get("party"),
        state=data.get("state") if senate else _district_code(data.get("district")),
        district=data.get("district"),
        applies_to_39th_congress=True,
        source_details=data,
    )


def district_record(data: dict) -> WikiRecord:
    link = data.get("district_url")
    name = data["label"]
    return WikiRecord(
        record_id=_identity("districts", link, f"{data['section']}:{name}"),
        source_id="districts",
        kind="district_directory_entry",
        name=name,
        linked_page=urljoin("https://en.wikipedia.org", link) if link else None,
        section=data["section"],
        source_details=data,
    )


def _district_code(district: str | None) -> str | None:
    if district is None:
        return None
    code = district.partition("-")[0]
    return code if len(code) == 2 and code.isupper() else None
