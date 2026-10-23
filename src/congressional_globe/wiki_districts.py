"""Extract the district listings from Wikipedia's overview article."""

from __future__ import annotations

import re
from typing import Any

from lxml import html

_YEAR = re.compile(r"\b(?:1[0-9]{3}|20[0-9]{2})\b")
_DISTRICT_HREF = re.compile(r"congressional[_ ]district", re.IGNORECASE)
_SECTION_IDS = {
    "Alabama",
    "Alaska",
    "American Samoa",
    "Arizona",
    "Arkansas",
    "California",
    "Colorado",
    "Connecticut",
    "Delaware",
    "District of Columbia",
    "Florida",
    "Georgia",
    "Guam",
    "Hawaii",
    "Idaho",
    "Illinois",
    "Indiana",
    "Iowa",
    "Kansas",
    "Kentucky",
    "Louisiana",
    "Maine",
    "Maryland",
    "Massachusetts",
    "Michigan",
    "Minnesota",
    "Mississippi",
    "Missouri",
    "Montana",
    "Nebraska",
    "Nevada",
    "New Hampshire",
    "New Jersey",
    "New Mexico",
    "New York",
    "North Carolina",
    "North Dakota",
    "Ohio",
    "Oklahoma",
    "Oregon",
    "Pennsylvania",
    "Puerto Rico",
    "Rhode Island",
    "South Carolina",
    "South Dakota",
    "Tennessee",
    "Texas",
    "United States Virgin Islands",
    "Utah",
    "Vermont",
    "Virginia",
    "Washington",
    "West Virginia",
    "Wisconsin",
    "Wyoming",
    "Northern Mariana Islands",
    "Non-voting delegations",
}


def extract_districts(source_html: str) -> list[dict[str, Any]]:
    """Return linked district list entries with their displayed temporal context.

    The article is a current/historical overview; its year ranges are not evidence
    that any district existed in a particular Congress or had a particular map.
    """
    document = html.fromstring(source_html)
    content = document.xpath('//*[@id="mw-content-text"]')
    root = content[0] if content else document
    headings = [
        heading
        for heading in root.xpath(".//h2[@id]")
        if heading.get("id", "").replace("_", " ") in _SECTION_IDS
    ]
    return [record for heading in headings for record in _section_records(heading)]


def _section_records(heading: Any) -> list[dict[str, Any]]:
    section = heading.get("id", "").replace("_", " ")
    listing = _section_list(heading)
    if listing is None:
        return []
    return [
        record
        for item_index, item in enumerate(listing.xpath("./li"))
        if (record := _district_item(item, section, 0, item_index)) is not None
    ]


def _section_list(heading: Any) -> Any | None:
    wrapper = heading.getparent()
    node = wrapper.getnext()
    while node is not None and not node.xpath(".//h2"):
        if node.tag == "ul":
            return node
        node = node.getnext()
    return None


def _district_item(
    item: Any, section: str, list_index: int, item_index: int
) -> dict[str, Any] | None:
    links = [
        link for link in item.xpath(".//a[@href]") if _DISTRICT_HREF.search(link.get("href", ""))
    ]
    if not links:
        return None
    link = links[0]
    raw_text = "".join(item.itertext())
    label = " ".join("".join(link.itertext()).split())
    remainder = " ".join(raw_text.replace(label, "", 1).split()).lstrip(" :,")
    years = _YEAR.findall(remainder)
    notes = [" ".join("".join(node.itertext()).split()) for node in item.xpath(".//i|.//b")]
    parenthetical = re.findall(r"\(([^()]*)\)", remainder)
    return {
        "section": section,
        "label": label,
        "district_url": link.get("href"),
        "displayed_years": years,
        "displayed_temporal_text": remainder,
        "status_notes": parenthetical or notes,
        "congressional_39th_applicability": None,
        "provenance": {
            "section_heading": section,
            "list_index": list_index,
            "item_index": item_index,
            "raw_text": raw_text,
        },
    }
