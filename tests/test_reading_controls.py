import json

import pytest
from test_reading_requests import _input, _paragraph, _record

from congressional_globe.reading_contracts import EvidenceSpan, ReadingReply
from congressional_globe.reading_controls import control_passes, make_control
from congressional_globe.reading_requests import materialize_record


def test_missing_image_control_preserves_exact_target_text(tmp_path):
    record = _record(tmp_path)
    control = make_control(record, "missing_image")
    before = json.loads(record["messages_without_image_payloads"][1]["content"])
    after = json.loads(control["messages_without_image_payloads"][1]["content"])
    assert after["target"] == before["target"]
    assert after["images"] == []
    assert json.loads(materialize_record(control))["messages"][1]["images"] == []
    assert control["request_sha256"] != record["request_sha256"]


def test_unrelated_control_retains_true_foreign_image_source_bindings(tmp_path):
    record = _record(tmp_path)
    unrelated = dict(record, unit_id="another")
    with pytest.raises(ValueError):
        make_control(record, "unrelated_image", unrelated)
    with pytest.raises(ValueError, match="different source"):
        make_control(record, "unrelated_image", record)


def test_controls_require_uncertainty_for_every_target(tmp_path):
    unit, _ = _input(tmp_path)
    uncertain = [
        dict(source_id=p.source_id, start=0, end=len(p.raw), reason="No related image")
        for p in unit.target
    ]
    reply = ReadingReply(unit_id=unit.id, status="needs_review", patches=[], uncertain=uncertain)
    assert control_passes(unit, reply)
    assert not control_passes(
        unit, ReadingReply(unit_id=unit.id, status="unchanged", patches=[], uncertain=[])
    )
    assert not control_passes(
        unit,
        reply.model_copy(update={"uncertain": [reply.uncertain[0].model_copy(update={"end": 1})]}),
    )


def test_unrelated_control_keeps_foreign_sources_without_forging_coverage(tmp_path):
    from congressional_globe.reading_requests import RequestOptions, describe_request

    record = _record(tmp_path)
    unit, image = _input(tmp_path)
    paragraph = _paragraph("Unrelated print", "foreign")
    unit = unit.model_copy(update={"id": "foreign", "target": [paragraph]})
    span = EvidenceSpan(
        source_id=paragraph.source_id,
        raw_sha256=paragraph.raw_sha256,
        start=0,
        end=len(paragraph.raw),
    )
    image = image.model_copy(update={"id": "foreign-image", "sources": [span]})
    unrelated = describe_request(
        unit, [image], record["model"], "instruction", {}, RequestOptions()
    )
    control = make_control(record, "unrelated_image", unrelated)
    content = json.loads(control["messages_without_image_payloads"][1]["content"])
    assert content["target"][0]["source_id"] != content["images"][0]["sources"][0]["source_id"]
    assert control["images"] == unrelated["images"]
    materialize_record(control)
