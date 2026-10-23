from congressional_globe.wiki_senate import extract_senate


def test_extracts_source_rows_without_conflating_seniority_and_service() -> None:
    source = """
    <table><tr><th>Class</th>
      <th>Terms of service of senators that expired in years</th></tr></table>
    <table>
      <tr><th>Rank</th><th>Senator (party-state)</th>
      <th>Seniority date</th><th>Other factors</th></tr>
      <tr><td>1</td><td><a href="https://en.wikipedia.org/wiki/Solomon_Foot">Solomon Foot</a>
      (<a>R</a>-<a>VT</a>)</td><td>March 4, 1851</td><td></td></tr>
      <tr><td></td><td><a href="https://en.wikipedia.org/wiki/Luke_P._Poland">Luke P. Poland</a>
      (<a>R</a>-<a>VT</a>)</td><td>November 21, 1865</td><td></td></tr>
      <tr><td></td><td></td><td></td><td></td></tr>
    </table>
    """

    rows = extract_senate(source)

    assert len(rows) == 2
    senior = rows[0]
    assert senior["full_name"] == "Solomon Foot"
    assert senior["state"] == "VT"
    assert senior["party"] == "R"
    assert senior["rank"] == 1
    assert senior["senior_term_start"] == "March 4, 1851"
    assert senior["service_during_congress"] == {
        "listed_in_congress_roster": True,
        "start": None,
        "end": None,
    }
    senior_source = senior["source"]
    assert isinstance(senior_source, dict)
    assert senior_source["table_index"] == 1
    assert senior_source["row_index"] == 1
    senior_cells = senior_source["cells"]
    assert isinstance(senior_cells, dict)
    assert senior_cells["seniority_date"] == "March 4, 1851"

    joiner = rows[1]
    assert joiner["full_name"] == "Luke P. Poland"
    assert joiner["rank"] is None
    assert joiner["senior_term_start"] == "November 21, 1865"
    joiner_source = joiner["source"]
    assert isinstance(joiner_source, dict)
    assert joiner_source["row_index"] == 2


def test_preserves_other_factor_remarks_and_missing_fields() -> None:
    rows = extract_senate(
        """<table><tr><th>Rank</th><th>Senator (party-state)</th><th>Seniority date</th>
        <th>Other factors</th></tr><tr><td>13</td>
        <td><a href="/wiki/Henry_B._Anthony">Henry B. Anthony</a>
        (R-RI)</td><td>March 4, 1859</td><td>Former governor</td></tr></table>"""
    )

    assert rows[0]["remarks"] == "Former governor"
    assert rows[0]["senate_class"] is None
    source = rows[0]["source"]
    assert isinstance(source, dict)
    row_text = source["row_text"]
    assert isinstance(row_text, str)
    assert row_text.endswith("Former governor")


def test_expands_seniority_date_rowspan_and_retains_its_source_row() -> None:
    rows = extract_senate(
        """<table><tr><th>Rank</th><th>Senator (party-state)</th>
        <th>Seniority date</th><th>Other factors</th></tr>
        <tr><td>1</td><td>First (R-VT)</td><td rowspan="2">March 4, 1851</td><td></td></tr>
        <tr><td>2</td><td>Second (R-OH)</td><td></td></tr></table>"""
    )

    assert [row["senior_term_start"] for row in rows] == [
        "March 4, 1851",
        "March 4, 1851",
    ]
    source = rows[1]["source"]
    assert isinstance(source, dict)
    cell_rows = source["cell_row_indices"]
    assert isinstance(cell_rows, dict)
    assert cell_rows["seniority_date"] == 1


def test_raises_when_roster_table_is_missing() -> None:
    try:
        extract_senate("<html><table><tr><th>Name</th></tr></table></html>")
    except ValueError as error:
        assert "Senate seniority table" in str(error)
    else:
        raise AssertionError("missing roster table should be rejected")
