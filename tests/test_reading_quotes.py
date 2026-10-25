from __future__ import annotations

import pytest
from pydantic import ValidationError

from congressional_globe.models import PrintedPage
from congressional_globe.reading_contracts import (
    EvidenceSpan,
    ReadingCandidate,
    ReadingParagraph,
    text_hash,
)
from congressional_globe.reading_quotes import (
    QuoteReadingReply,
    validate_quote_reply,
)


def paragraph(raw="café GCO dollars"):
    return ReadingParagraph(
        item_identifier="congressionalg7391unit",
        part_number=1,
        scan_leaf=10,
        printed_page=PrintedPage(),
        paragraph_id="par_000010_000001",
        reading_order=0,
        hocr_page_id="page_000010",
        line_ids=["line_1"],
        bbox=None,
        raw=raw,
        raw_sha256=text_hash(raw),
        static=raw,
        static_sha256=text_hash(raw),
        static_patches=[],
    )


def unit(raw="café GCO dollars"):
    return ReadingCandidate(
        id="test",
        part_number=1,
        stratum="damage_cue",
        split="primary",
        target=[paragraph(raw)],
        selection_reason="Synthetic test",
    )


def patch(old="GCO", new="660", **changes):
    return {
        "source_id": paragraph().source_id,
        "old": old,
        "new": new,
        "image_ids": ["crop"],
        "reason": "Synthetic source evidence",
        **changes,
    }


def reply(patches=None, uncertain=None, status="proposed", **changes):
    return QuoteReadingReply.model_validate(
        {
            "unit_id": "test",
            "status": status,
            "patches": patches or [],
            "uncertain": uncertain or [],
            **changes,
        }
    )


def coverage(raw="café GCO dollars", start=0, end=None, **changes):
    source = paragraph(raw)
    return {
        "crop": [
            EvidenceSpan(
                source_id=source.source_id,
                raw_sha256=changes.get("raw_sha256", source.raw_sha256),
                start=start,
                end=len(raw) if end is None else end,
            )
        ]
    }


def test_quote_anchor_derives_unicode_offset_and_reuses_v1_validation():
    parsed, derived = validate_quote_reply(unit(), reply([patch()]), coverage())
    assert (parsed.patches[0].start, parsed.patches[0].end) == (5, 8)
    assert derived[paragraph().source_id]["text"] == "café 660 dollars"
    assert derived[paragraph().source_id]["mapping"][1]["raw_start"] == 5


def test_out_of_order_quotes_are_sorted_by_raw_offsets_before_v1_replay():
    p = paragraph("café one; two")
    candidate = unit("café one; two")
    quote_replies = reply(
        [
            patch("two", "2", source_id=p.source_id),
            patch("one", "1", source_id=p.source_id),
        ]
    )
    parsed, derived = validate_quote_reply(candidate, quote_replies, coverage("café one; two"))
    assert [item.start for item in parsed.patches] == [5, 10]
    assert derived[p.source_id]["text"] == "café 1; 2"


@pytest.mark.parametrize("raw,quote", [("prefix", "missing"), ("aaa", "aa"), ("foo foo", "foo")])
def test_missing_or_ambiguous_quotes_are_rejected(raw, quote):
    p = paragraph(raw)
    candidate = unit(raw)
    proposal = reply([patch(quote, "fixed", source_id=p.source_id)])
    with pytest.raises(ValueError, match="exactly once"):
        validate_quote_reply(candidate, proposal, coverage(raw))


def test_coordinate_fields_are_forbidden_and_noop_and_duplicate_quotes_fail():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        reply([patch(start=5, end=8)])
    with pytest.raises(ValueError, match="no-op"):
        validate_quote_reply(unit(), reply([patch(new="GCO")]), coverage())
    with pytest.raises(ValueError, match="overlap"):
        validate_quote_reply(unit(), reply([patch(), patch()]), coverage())


def test_patch_image_source_and_unit_guards_are_preserved():
    proposal = reply([patch()])
    wrong_image = coverage(start=0, end=5)
    with pytest.raises(ValueError, match="image"):
        validate_quote_reply(unit(), proposal, wrong_image)
    wrong_hash = coverage(raw_sha256="0" * 64)
    with pytest.raises(ValueError, match="image"):
        validate_quote_reply(unit(), proposal, wrong_hash)
    with pytest.raises(ValueError, match="unit ID"):
        validate_quote_reply(unit(), proposal.model_copy(update={"unit_id": "other"}), coverage())
    with pytest.raises(ValueError, match="non-target"):
        validate_quote_reply(unit(), reply([patch(source_id="context-only")]), coverage())


def test_uncertainty_quotes_derive_spans_and_block_overlapping_patches():
    source_id = paragraph().source_id
    uncertain_reply = reply(
        uncertain=[{"source_id": source_id, "old": "GCO", "reason": "Image unclear"}],
        status="needs_review",
    )
    parsed, derived = validate_quote_reply(unit(), uncertain_reply, {})
    assert (parsed.uncertain[0].start, parsed.uncertain[0].end) == (5, 8)
    assert derived[source_id]["text"] == paragraph().raw

    whole_paragraph = reply(
        uncertain=[{"source_id": source_id, "old": "", "reason": "Page unreadable"}],
        status="needs_review",
    )
    parsed, _ = validate_quote_reply(unit(), whole_paragraph, {})
    assert (parsed.uncertain[0].start, parsed.uncertain[0].end) == (0, len(paragraph().raw))

    conflict = reply(
        patches=[patch()],
        uncertain=[{"source_id": source_id, "old": "GCO", "reason": "Image unclear"}],
        status="needs_review",
    )
    with pytest.raises(ValueError, match="uncertain"):
        validate_quote_reply(unit(), conflict, coverage())


def test_overlapping_uncertainty_quotes_are_rejected_without_deduplication():
    source_id = paragraph().source_id
    ambiguous_ranges = reply(
        uncertain=[
            {"source_id": source_id, "old": "café GCO", "reason": "A"},
            {"source_id": source_id, "old": "GCO dollars", "reason": "B"},
        ],
        status="needs_review",
    )
    with pytest.raises(ValueError, match="uncertainty spans overlap"):
        validate_quote_reply(unit(), ambiguous_ranges, {})


@pytest.mark.parametrize(
    "status,patches,uncertain",
    [
        ("unchanged", [patch()], []),
        ("proposed", [], []),
        ("needs_review", [], []),
    ],
)
def test_status_consistency_matches_existing_v1_contract(status, patches, uncertain):
    candidate = reply(patches, uncertain, status)
    with pytest.raises(ValueError, match="status"):
        validate_quote_reply(unit(), candidate, coverage())
