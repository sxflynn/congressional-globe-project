from pathlib import Path

import pytest
from test_reading_requests import _paragraph

from congressional_globe import reading_requests as requests
from congressional_globe.reading_contracts import EvidenceSpan, ReadingCandidate
from congressional_globe.reading_controls import make_control
from congressional_globe.reading_quote_expansion import (
    build_expansion,
    quote_system,
    task_id,
    to_quote_record,
)

MODELS = ("qwen3.8:27b-mlx", "gemma4:31b-mlx")
CONTROL_UNIT = "reading-17"


def _unit(identifier: str) -> ReadingCandidate:
    paragraph = _paragraph(f"text {identifier}", f"paragraph-{identifier}")
    return ReadingCandidate(
        id=f"reading-{identifier}",
        part_number=1,
        stratum="ordinary",
        split="primary",
        target=[paragraph],
        selection_reason="Synthetic expansion test",
    )


def _record(tmp_path: Path, identifier: str, model: str) -> dict:
    unit = _unit(identifier)
    path = tmp_path / "image.jpg"
    path.write_bytes(b"synthetic image payload")
    image = requests.ImageInput(
        id=f"image-{identifier}",
        path=path,
        sha256=requests.digest(path.read_bytes()),
        sources=[
            EvidenceSpan(
                source_id=unit.target[0].source_id,
                raw_sha256=unit.target[0].raw_sha256,
                start=0,
                end=len(unit.target[0].raw),
            )
        ],
    )
    return requests.describe_request(
        unit,
        [image],
        model,
        "instruction",
        {"type": "object"},
        requests.RequestOptions(),
    )


def _record_for(records: list[dict], unit_id: str, model: str) -> dict:
    return next(
        record for record in records if record["unit_id"] == unit_id and record["model"] == model
    )


def _completed(primary: list[dict]) -> list[dict]:
    return [
        to_quote_record(record, "Read.", {"type": "object"})
        for record in primary
        if record["unit_id"] in {"reading-00", "reading-01"}
    ]


def _control_records(records: list[dict]) -> list[dict]:
    return [record for record in records if record.get("control_kind")]


def _manifest(tmp_path: Path) -> tuple[list[dict], list[dict]]:
    identifiers = [f"{index:02d}" for index in range(18)]
    primary = [
        _record(tmp_path, identifier, model) for model in MODELS for identifier in identifiers
    ]
    controls = [
        make_control(
            _record_for(primary, CONTROL_UNIT, model),
            "unrelated_image",
            _record_for(primary, "reading-00", model),
        )
        for model in MODELS
    ]
    return primary + controls, primary


def test_quote_record_reproduces_system_suffix_and_marks_launch_not_ready(tmp_path):
    record = _record(tmp_path, "00", MODELS[0])
    schema = {"type": "object"}
    quote = to_quote_record(record, "Read the scan.", schema)
    assert quote["messages_without_image_payloads"][0]["content"] == quote_system(
        "Read the scan.", schema
    )
    assert quote["response_contract"] == "quote-v2"
    assert quote["text_tokens"] is None and quote["image_tokens"] is None
    assert quote["token_fit"] == "unknown" and quote["launch_ready"] is False
    assert quote["request_sha256"] != record["request_sha256"]
    assert requests.materialize_record(quote)


def test_expansion_reuses_four_completed_requests_and_adds_36(tmp_path):
    launch, primary = _manifest(tmp_path)
    completed = _completed(primary)
    report = build_expansion(launch, completed, "Read.", {"type": "object"}, MODELS, CONTROL_UNIT)
    assert report["request_count"] == 36
    assert len(report["reused_requests"]) == 4
    assert len(report["requests"]) == 36
    controls = _control_records(report["requests"])
    assert {record["control_kind"] for record in controls} == {
        "missing_image",
        "unrelated_image",
    }
    assert len(controls) == 4
    ids = {task_id(record) for record in report["requests"] + report["reused_requests"]}
    assert len(ids) == 40


def test_expansion_refuses_unreproducible_reuse(tmp_path):
    launch, primary = _manifest(tmp_path)
    completed = _completed(primary)
    completed[0]["request_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="not reproducible"):
        build_expansion(launch, completed, "Read.", {"type": "object"}, MODELS, CONTROL_UNIT)
