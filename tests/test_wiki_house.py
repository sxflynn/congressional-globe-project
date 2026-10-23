from typing import cast

from congressional_globe.wiki_house import extract_house


def test_extracts_representatives_and_delegates_without_reinterpreting_service() -> None:
    source = """
    <h2>U.S. House seniority list</h2>
    <table><tr><th>Rank</th><th>Representative</th><th>Party</th><th>District</th>
    <th>Seniority date<br/>(Previous service, if any)</th>
    <th>No.# of term(s)</th><th>Notes</th></tr>
    <tr><td>1</td><td><a href="/wiki/Ada_Person">Ada Person</a></td><td>R</td>
    <td>IL-03</td><td>March 4, 1853<br/>Previous service, 1849\u20131851.</td>
    <td>6th term*</td><td>Resigned on July 2, 1865.</td></tr>
    <tr><td></td><td><a href="/wiki/Bea_Person">Bea Person</a></td><td></td>
    <td>NV</td><td>March 4, 1865</td><td>1st term</td><td>Left the House in 1867.</td></tr>
    </table>
    <h2>Delegates</h2>
    <table><tr><th>Rank</th><th>Delegate</th><th>Party</th><th>District</th>
    <th>Seniority date (Previous service, if any)</th><th>No.# of term(s)</th><th>Notes</th></tr>
    <tr><td>1</td><td>Cal Chaves</td><td>R</td><td>NM</td><td>March 4, 1865</td>
    <td>1st term</td><td></td></tr></table>
    """

    rows = extract_house(source)

    assert len(rows) == 3
    first = rows[0]
    assert first["kind"] == "representative"
    assert first["rank"] == 1
    assert first["name"] == "Ada Person"
    assert first["person_page"] == "/wiki/Ada_Person"
    assert first["district"] == "IL-03"
    assert first["seniority_date_text"] == "March 4, 1853"
    assert first["previous_service_text"] == "Previous service, 1849\u20131851."
    assert first["terms_text"] == "6th term*"
    assert first["notes_text"] == "Resigned on July 2, 1865."
    assert rows[1]["rank"] is None
    assert rows[1]["party"] is None
    assert rows[1]["notes_text"] == "Left the House in 1867."
    assert rows[2]["kind"] == "delegate"
    displayed = cast(dict[str, str], rows[2]["displayed_fields"])
    assert displayed["No.# of term(s)"] == "1st term"


def test_ignores_unrelated_tables_and_header_rows() -> None:
    source = """
    <table><tr><th>Rank</th><th>Name</th></tr><tr><td>1</td><td>Not a member</td></tr></table>
    <table><tr><th>Rank</th><th>Representative</th><th>Party</th><th>District</th>
    <th>Seniority date</th><th>No.# of term(s)</th><th>Notes</th></tr>
    <tr><th>2</th><td>Header noise</td><td></td><td></td><td></td><td></td><td></td></tr>
    <tr><td>3</td><td>Valid Member</td><td>D</td><td>PA-01</td><td>March 4, 1865</td>
    <td>1st term</td><td></td></tr></table>
    """

    rows = extract_house(source)

    assert len(rows) == 1
    assert rows[0]["table_index"] == 1
    assert rows[0]["name"] == "Valid Member"
