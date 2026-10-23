"""Deterministic extraction of the 39th Congress Senate roster from Wikipedia."""

from __future__ import annotations

import re

from lxml import html

_HEADER = ("Rank", "Senator (party-state)", "Seniority date", "Other factors")
_FIELD_NAMES = ("rank", "senator", "seniority_date", "other_factors")


def extract_senate(source_html: str) -> list[dict[str, object]]:
    """Extract senator rows and their source mapping from saved article HTML.

    The article gives Congress-wide scope, while its seniority date means the
    commencement of a senator's first term. It does not provide individual
    service intervals, so those dates are deliberately left unknown.
    """
    document = html.fromstring(source_html)
    table_index, table = _roster_table(document)
    output: list[dict[str, object]] = []
    inherited: dict[int, tuple[int, str, int]] = {}
    for row_index, row in enumerate(table.xpath(".//tr")):
        record = _record_for_row(row, row_index, table_index, inherited)
        if record is not None:
            output.append(record)
    return output


def _record_for_row(
    row: html.HtmlElement,
    row_index: int,
    table_index: int,
    inherited: dict[int, tuple[int, str, int]],
) -> dict[str, object] | None:
    cells = _logical_cells(row, row_index, inherited)
    if row_index == 0 or cells is None or not cells[0][1]:
        return None
    cell_text, cell_origins = cells
    name, href = _name_and_href(row, cell_text[1])
    party, state = _party_state(cell_text[1])
    return {
        "full_name": name,
        "person_url": href,
        "state": state,
        "senate_class": None,
        "rank": _integer(cell_text[0]),
        "party": party,
        "senior_term_start": cell_text[2] or None,
        "service_during_congress": {
            "listed_in_congress_roster": True,
            "start": None,
            "end": None,
        },
        "remarks": cell_text[3] or None,
        "source": {
            "table_index": table_index,
            "row_index": row_index,
            "row_text": " | ".join(cell_text),
            "cells": dict(zip(_FIELD_NAMES, cell_text, strict=True)),
            "cell_row_indices": dict(zip(_FIELD_NAMES, cell_origins, strict=True)),
        },
    }


def _name_and_href(row: html.HtmlElement, text: str) -> tuple[str, str | None]:
    person_cell = next((cell for cell in row.xpath("./td") if _text(cell) == text), None)
    links = person_cell.xpath(".//a[1]") if person_cell is not None else []
    if not links:
        return _person_name(text), None
    return _text(links[0]), links[0].get("href")


def _roster_table(document: html.HtmlElement) -> tuple[int, html.HtmlElement]:
    for table_index, table in enumerate(document.xpath("//table")):
        headers = tuple(_text(cell) for cell in table.xpath(".//tr[1]/*"))
        if headers == _HEADER:
            return table_index, table
    raise ValueError("Wikipedia Senate seniority table was not found")


def _text(element: html.HtmlElement) -> str:
    return " ".join(" ".join(element.itertext()).split())


def _logical_cells(
    row: html.HtmlElement, row_index: int, inherited: dict[int, tuple[int, str, int]]
) -> tuple[list[str], list[int]] | None:
    values, origins = _active_cells(inherited, row_index)
    for cell in row.xpath("./th|./td"):
        _place_cell(cell, row_index, inherited, values, origins)
    if len(values) != len(_HEADER):
        return None
    return (
        [values[index] for index in range(len(_HEADER))],
        [origins[index] for index in range(len(_HEADER))],
    )


def _active_cells(
    inherited: dict[int, tuple[int, str, int]], row_index: int
) -> tuple[dict[int, str], dict[int, int]]:
    active = {column: cell for column, cell in inherited.items() if cell[2] >= row_index}
    inherited.clear()
    inherited.update(active)
    return (
        {column: value for column, (_, value, _) in active.items()},
        {column: origin for column, (origin, _, _) in active.items()},
    )


def _place_cell(
    cell: html.HtmlElement,
    row_index: int,
    inherited: dict[int, tuple[int, str, int]],
    values: dict[int, str],
    origins: dict[int, int],
) -> None:
    column = next(index for index in range(len(values) + 1) if index not in values)
    span = int(cell.get("colspan", "1"))
    row_span = int(cell.get("rowspan", "1"))
    text = _text(cell)
    for offset in range(span):
        values[column + offset] = text
        origins[column + offset] = row_index
        if row_span > 1:
            inherited[column + offset] = (row_index, text, row_index + row_span - 1)


def _party_state(text: str) -> tuple[str | None, str | None]:
    match = re.search(r"\(\s*([A-Z]+)\s*-\s*([A-Z]{2})\s*\)", text)
    return (match.group(1), match.group(2)) if match else (None, None)


def _person_name(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()


def _integer(value: str) -> int | None:
    return int(value) if value.isdigit() else None
