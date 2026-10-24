from __future__ import annotations

import pytest

from congressional_globe.models import PrintedPage
from congressional_globe.reading_contracts import (
    EvidenceSpan,
    ReadingCandidate,
    ReadingParagraph,
    ReadingPatch,
    ReadingReply,
    replay_paragraph,
    text_hash,
    validate_reply,
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


def unit():
    return ReadingCandidate(
        id="test",
        part_number=1,
        stratum="damage_cue",
        split="primary",
        target=[paragraph()],
        selection_reason="Synthetic test",
    )


def patch(**changes):
    data = dict(
        source_id=paragraph().source_id,
        start=5,
        end=8,
        old="GCO",
        new="660",
        image_ids=["crop"],
        reason="Synthetic source evidence",
    )
    return ReadingPatch.model_validate({**data, **changes})


def coverage(start=0, end=16, **changes):
    p = paragraph()
    return {
        "crop": [
            EvidenceSpan.model_validate(
                dict(
                    source_id=p.source_id,
                    raw_sha256=changes.get("raw_sha256", p.raw_sha256),
                    start=start,
                    end=end,
                )
            )
        ]
    }


def test_unicode_replay_maps_raw_and_clean_without_offset_guessing():
    p = patch(new="six hundred sixty")
    clean, mapping = replay_paragraph(paragraph().raw, [p])
    assert clean == "café six hundred sixty dollars"
    assert mapping[1].raw_start == 5
    assert mapping[1].clean_end == 22
    reply = ReadingReply(unit_id="test", status="proposed", patches=[p], uncertain=[])
    result = validate_reply(unit(), reply, coverage())
    assert result[p.source_id]["status"] == "model_proposal"
    assert result[p.source_id]["sha256"] == text_hash(clean)


@pytest.mark.parametrize("changes", [{"start": 4}, {"end": 100}, {"old": "999"}, {"new": "GCO"}])
def test_bad_patch_offsets_text_and_noop_rejected(changes):
    with pytest.raises(ValueError):
        replay_paragraph(paragraph().raw, [patch(**changes)])


def test_context_patch_and_unbound_or_wrong_image_rejected():
    reply = ReadingReply(unit_id="test", status="proposed", patches=[patch()], uncertain=[])
    for bound in [{}, coverage(start=0, end=5), coverage(raw_sha256="0" * 64)]:
        with pytest.raises(ValueError, match="image"):
            validate_reply(unit(), reply, bound)
    wrong = reply.model_copy(update={"patches": [patch(source_id="a-context-paragraph")]})
    with pytest.raises(ValueError, match="non-target"):
        validate_reply(unit(), wrong, coverage())


def test_uncertainty_keeps_raw_text_and_disallows_overlapping_repair():
    source = paragraph().source_id
    uncertain = dict(source_id=source, start=5, end=8, reason="Source insufficient")
    reply = ReadingReply(unit_id="test", status="needs_review", patches=[], uncertain=[uncertain])
    result = validate_reply(unit(), reply, {})
    assert result[source]["text"] == paragraph().raw
    with pytest.raises(ValueError, match="uncertain"):
        validate_reply(unit(), reply.model_copy(update={"patches": [patch()]}), coverage())


def test_deletions_insertions_and_overlaps_have_explicit_mappings():
    deletion = patch(start=5, end=8, new="")
    insertion = patch(start=8, end=8, old="", new="?")
    clean, mapping = replay_paragraph(paragraph().raw, [deletion, insertion])
    assert clean == "café ? dollars"
    assert mapping[1].clean_start == mapping[1].clean_end
    assert mapping[3].raw_start == mapping[3].raw_end
    with pytest.raises(ValueError, match="overlap"):
        replay_paragraph(paragraph().raw, [patch(), patch()])


@pytest.mark.parametrize(
    "status,patches,uncertain",
    [
        ("unchanged", [patch()], []),
        ("proposed", [], []),
        ("needs_review", [], []),
    ],
)
def test_status_contradictions_rejected(status, patches, uncertain):
    with pytest.raises(ValueError, match="status"):
        ReadingReply(unit_id="test", status=status, patches=patches, uncertain=uncertain)


def test_static_raw_hash_and_part_identity_guard():
    data = paragraph().model_dump()
    for change in [{"static": "changed"}, {"raw_sha256": "0" * 64}, {"part_number": 2}]:
        with pytest.raises(ValueError):
            ReadingParagraph.model_validate({**data, **change})
