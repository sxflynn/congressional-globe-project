"""Deterministic extraction of the 39th Congress House and delegate tables.

Wikipedia is a secondary source. These records preserve its displayed claims;
they are not independently verified service assertions.
"""

from __future__ import annotations

from lxml import html

_TABLE_HEADERS = ("rank", "person", "party", "district", "seniority_date", "term", "notes")
_PERSON_HEADERS = {"representative": "representative", "delegate": "delegate"}


def _text(node: html.HtmlElement) -> str:
    return " ".join(" ".join(node.itertext()).split())


def _headers(table: html.HtmlElement) -> list[str]:
    row = table.xpath(".//tr[1]")
    return [_text(cell) for cell in row[0].xpath("./th|./td")] if row else []


def _table_kind(headers: list[str]) -> str | None:
    normalized = [header.lower() for header in headers]
    if not _valid_headers(normalized):
        return None
    return _PERSON_HEADERS.get(normalized[1])


def _valid_headers(headers: list[str]) -> bool:
    return (
        len(headers) == len(_TABLE_HEADERS)
        and headers[0] == "rank"
        and headers[1] in _PERSON_HEADERS
        and headers[4].startswith("seniority date")
        and headers[5].startswith("no.")
    )


def _row_cells(row: html.HtmlElement, headers: list[str]) -> list[html.HtmlElement]:
    cells = row.xpath("./th|./td")
    if len(cells) == len(headers) - 1 and headers[-1].lower() == "notes":
        cells.append(row.makeelement("td"))
    return cells


def _seniority_parts(value: str) -> tuple[str | None, str | None]:
    marker = "Previous service, "
    if marker not in value:
        return value or None, None
    date_text, previous = value.split(marker, 1)
    return date_text.strip() or None, marker + previous


def _rank(value: str) -> int | None:
    return int(value) if value.isdigit() else None


def _person_page(cell: html.HtmlElement) -> str | None:
    links = cell.xpath(".//a[1]/@href")
    return links[0] if links else None


def _row_record(
    table_index: int,
    row_index: int,
    kind: str,
    headers: list[str],
    row: html.HtmlElement,
) -> dict[str, object] | None:
    cells = _row_cells(row, headers)
    if not cells or len(cells) != len(headers):
        return None
    values = [_text(cell) for cell in cells]
    if not values[1]:
        return None
    return _record_fields(table_index, row_index, kind, headers, values, cells[1])


def _record_fields(
    table_index: int,
    row_index: int,
    kind: str,
    headers: list[str],
    values: list[str],
    name_cell: html.HtmlElement,
) -> dict[str, object]:
    seniority, previous_service = _seniority_parts(values[4])
    return {
        "table_index": table_index,
        "row_index": row_index,
        "kind": kind,
        "row_text": " | ".join(values),
        "displayed_fields": dict(zip(headers, values, strict=True)),
        "rank": _rank(values[0]),
        "name": values[1],
        "person_page": _person_page(name_cell),
        "party": values[2] or None,
        "district": values[3] or None,
        "seniority_date_text": seniority,
        "previous_service_text": previous_service,
        "terms_text": values[5] or None,
        "notes_text": values[6] or None,
    }


def _data_rows(table: html.HtmlElement) -> list[tuple[int, html.HtmlElement]]:
    return [
        (row_index, row)
        for row_index, row in enumerate(table.xpath("./tbody/tr|./tr"))
        if not row.xpath("./th")
    ]


def _table_records(table: html.HtmlElement, table_index: int) -> list[dict[str, object]]:
    headers = _headers(table)
    kind = _table_kind(headers)
    if kind is None:
        return []
    return [
        record
        for row_index, row in _data_rows(table)
        if (record := _row_record(table_index, row_index, kind, headers, row)) is not None
    ]


def extract_house(source_html: str) -> list[dict[str, object]]:
    """Extract House representative and delegate rows in page order.

    The seniority date and term fields remain verbatim text: neither is a
    complete service interval or a count of terms served in this Congress.
    Notes remain verbatim because departures may be dated, undated, or generic.
    """
    document = html.fromstring(source_html)
    return [
        record
        for table_index, table in enumerate(document.xpath("//table"))
        for record in _table_records(table, table_index)
    ]
