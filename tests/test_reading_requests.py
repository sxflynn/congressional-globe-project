from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from congressional_globe import reading_requests as requests
from congressional_globe.reading_contracts import ReadingCandidate, ReadingParagraph, text_hash


def _paragraph(text, identifier):
    return ReadingParagraph(
        item_identifier="congressionalg7391unit",
        part_number=1,
        scan_leaf=1,
        printed_page={},
        reading_order=0,
        paragraph_id=identifier,
        hocr_page_id="page1",
        line_ids=[],
        bbox=None,
        raw=text,
        raw_sha256=text_hash(text),
        static=text,
        static_sha256=text_hash(text),
        static_patches=[],
    )


def _input(tmp_path):
    unit = ReadingCandidate(
        id="synthetic",
        part_number=1,
        stratum="ordinary",
        split="primary",
        target=[_paragraph("Mr. A. — words", "target")],
        context_before=[_paragraph("Prior words", "before")],
        context_after=[_paragraph("Following words", "after")],
        selection_reason="Synthetic test",
    )
    path = tmp_path / "image.jpg"
    path.write_bytes(b"synthetic image payload")
    image = requests.ImageInput(
        id="image1",
        path=path,
        sha256=requests.digest(path.read_bytes()),
        sources=[
            dict(
                source_id=unit.target[0].source_id,
                raw_sha256=unit.target[0].raw_sha256,
                start=0,
                end=len(unit.target[0].raw),
            )
        ],
    )
    return unit, image


def _record(tmp_path):
    unit, image = _input(tmp_path)
    return requests.describe_request(
        unit,
        [image],
        next(iter(requests.SUPPORTED_MODELS)),
        "instruction",
        {"type": "object"},
        requests.RequestOptions(),
    )


def test_request_roundtrip_preserves_whole_raw_context_and_image_binding(tmp_path):
    record = _record(tmp_path)
    body = requests.materialize_record(record)
    payload = json.loads(body)
    content = json.loads(payload["messages"][1]["content"])
    assert content["target"][0]["raw"] == "Mr. A. — words"
    assert content["context_before"][0]["raw"] == "Prior words"
    assert content["context_after"][0]["raw"] == "Following words"
    assert content["images"][0]["id"] == "image1"
    assert "static" not in content["target"][0]
    assert payload["options"] == dict(num_ctx=16384, num_predict=4096, temperature=0)
    assert record["text_tokens"] is None
    assert record["launch_ready"] is False


@pytest.mark.parametrize(
    "field,value", [("think", True), ("format", "different"), ("model_digest", "a" * 64)]
)
def test_saved_request_rejects_changed_configuration(tmp_path, field, value):
    record = _record(tmp_path)
    record[field] = value
    with pytest.raises(ValueError):
        requests.materialize_record(record)


def test_changed_image_bytes_are_rejected_before_materialization(tmp_path):
    record = _record(tmp_path)
    Path(record["images"][0]["path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="image bytes"):
        requests.materialize_record(record)


def test_incomplete_and_wrong_source_images_are_rejected(tmp_path):
    unit, image = _input(tmp_path)
    with pytest.raises(ValueError, match="missing"):
        requests.request_body(
            unit, [], next(iter(requests.SUPPORTED_MODELS)), "p", {}, requests.RequestOptions()
        )
    wrong = image.model_dump()
    wrong["sources"][0]["raw_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="span/hash"):
        requests.request_body(
            unit,
            [requests.ImageInput.model_validate(wrong)],
            next(iter(requests.SUPPORTED_MODELS)),
            "p",
            {},
            requests.RequestOptions(),
        )


def test_image_order_is_part_of_exact_request_identity(tmp_path):
    unit, image = _input(tmp_path)
    second = image.model_copy(update={"id": "image2"})
    model = next(iter(requests.SUPPORTED_MODELS))
    first = requests.request_body(unit, [image, second], model, "p", {}, requests.RequestOptions())
    other = requests.request_body(unit, [second, image], model, "p", {}, requests.RequestOptions())
    assert requests.digest(first) != requests.digest(other)


def test_request_manifest_refuses_different_replacement(tmp_path):
    path = tmp_path / "manifest.json"
    record = _record(tmp_path)
    requests.write_report(record, path)
    requests.write_report(record, path)
    changed = copy.deepcopy(record)
    changed["request_bytes"] += 1
    with pytest.raises(ValueError, match="overwrite"):
        requests.write_report(changed, path)


def test_saved_image_metadata_cannot_disagree_with_wire_bindings(tmp_path):
    record = _record(tmp_path)
    record["images"][0]["sources"][0]["raw_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="image metadata"):
        requests.materialize_record(record)
