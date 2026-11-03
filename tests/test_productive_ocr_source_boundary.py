"""Real repeated false-complete replies and synthetic text-only boundary controls."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from congressional_globe.productive_ocr_text_reply import validate_text_reply

ROOT = Path("artifacts/expanded-workflow-audit-20261103-01/V2")


def _case(repeat=1):
    host = json.loads((ROOT / "host.json").read_bytes())
    result = json.loads((ROOT / f"call-{repeat}/result.json").read_bytes())
    return host, json.loads(result["response"]["output_text"])


@pytest.mark.parametrize("repeat", [1, 2, 3])
def test_actual_false_complete_cutoff_replies_are_rejected(repeat):
    host, reply = _case(repeat)
    assert host["payload"]["paragraphs"][0]["raw"]["text"].endswith("busi-")
    assert reply["readings"][0]["coverage"] == "complete"
    with pytest.raises(ValueError, match=r"cut-off word.*incomplete coverage"):
        validate_text_reply(json.dumps(reply), host)


def test_inventing_the_missing_letters_cannot_escape_the_source_guard():
    host, reply = _case(2)
    reply["readings"][0]["corrected_text"] = reply["readings"][0]["corrected_text"].replace(
        "busi-", "business"
    )
    with pytest.raises(ValueError, match="cut-off word"):
        validate_text_reply(json.dumps(reply), host)


def test_incomplete_null_reply_exports_no_guessed_proposal():
    host, reply = _case()
    reply["readings"][0].update(
        coverage="incomplete",
        corrected_text=None,
        reason="The image ends at busi-; the following letters are outside this crop.",
    )
    outcome = validate_text_reply(json.dumps(reply), host)
    assert outcome["proposal_status"] == "unresolved"
    assert outcome["derived_proposals"] == []


def test_whitespace_is_not_an_uncertainty_reason():
    host, reply = _case()
    reply["readings"][0].update(coverage="incomplete", corrected_text=None, reason="   ")
    with pytest.raises(ValueError, match="nonblank"):
        validate_text_reply(json.dumps(reply), host)


@pytest.mark.parametrize(
    "raw,reading",
    [
        ("The Senator from Michi- gan spoke.", "The Senator from Michigan spoke."),
        ("This is non-concurrence.", "This is non-concurrence."),
        ("He has under- taken the work.", "He has undertaken the work."),
        ("The thought ends—", "The thought ends—"),
        ("The thought ends--", "The thought ends--"),
        ("A separate dash -", "A separate dash -"),
        ("Now,", "Now,"),
        ("A complete final word", "A complete final word"),
    ],
)
def test_internal_hyphens_and_nonfragment_endings_remain_complete_eligible(raw, reading):
    host, reply = _synthetic_source(raw)
    reply["readings"][0]["corrected_text"] = reading
    outcome = validate_text_reply(json.dumps(reply), host)
    assert outcome["provider_reply"]["readings"][0]["coverage"] == "complete"
    assert outcome["derived_proposals"][0]["text"] == reading


def test_trailing_whitespace_does_not_hide_an_unresolved_fragment():
    host, reply = _synthetic_source("A visible frag-\n ")
    reply["readings"][0]["corrected_text"] = "A visible fragment."
    with pytest.raises(ValueError, match="cut-off word"):
        validate_text_reply(json.dumps(reply), host)


def _synthetic_source(raw):
    """Text-only controls exercise the validator, never claim image-backed source truth."""
    host, reply = _case()
    host = copy.deepcopy(host)
    target = host["payload"]["paragraphs"][0]
    digest = hashlib.sha256(raw.encode()).hexdigest()
    target["raw"] = {"text": raw, "sha256": digest}
    target["static"].update(text=raw, sha256=digest, edits=[])
    return host, reply
