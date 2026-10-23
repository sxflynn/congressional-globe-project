from congressional_globe.wiki_districts import extract_districts


def test_extracts_state_district_labels_and_preserves_temporal_notes() -> None:
    source = """
    <html><body><div id="mw-content-text"><div class="mw-parser-output">
      <div class="mw-heading mw-heading2"><h2 id="California">California</h2></div>
      <figure>California's districts since 2025</figure>
      <ul>
        <li><a href="https://en.wikipedia.org/wiki/California's_at-large_congressional_district">At-large</a>
          : 1849\u20131865, 1883\u20131885 (obsolete)</li>
        <li><a href="https://en.wikipedia.org/wiki/California's_1st_congressional_district">
          1st district</a> : 1865\u2013present</li>
      </ul>
      <div class="mw-heading mw-heading2"><h2 id="References">References</h2></div>
      <ul><li><a href="https://en.wikipedia.org/wiki/California's_2nd_congressional_district">duplicate</a></li></ul>
    </div></div></body></html>
    """

    records = extract_districts(source)

    assert [record["label"] for record in records] == ["At-large", "1st district"]
    assert records[0]["displayed_years"] == ["1849", "1865", "1883", "1885"]
    assert records[0]["displayed_temporal_text"] == "1849\u20131865, 1883\u20131885 (obsolete)"
    assert records[0]["status_notes"] == ["obsolete"]
    assert records[1]["congressional_39th_applicability"] is None
    assert records[1]["provenance"]["raw_text"].endswith("1865\u2013present")


def test_ignores_unrelated_links_and_nonarticle_duplicate_headings() -> None:
    source = """
    <html><body>
      <nav><h2 id="Alabama">Alabama</h2><ul>
        <li><a href="/Alabama_1st_congressional_district">nav</a></li>
      </ul></nav>
      <div id="mw-content-text">
        <div class="mw-heading mw-heading2">
          <h2 id="Non-voting_delegations">Non-voting delegations</h2>
        </div>
        <ul>
          <li><a href="/American_Samoa's_at-large_congressional_district">American Samoa</a>,
            1978\u2013present</li>
          <li><a href="/Cherokee_Nation">Cherokee Nation</a>, 1835 and
            2019\u2013present (yet to be seated)</li>
        </ul>
      </div>
    </body></html>
    """

    records = extract_districts(source)

    assert len(records) == 1
    assert records[0]["section"] == "Non-voting delegations"
    assert records[0]["label"] == "American Samoa"
    assert records[0]["displayed_temporal_text"] == "1978\u2013present"
