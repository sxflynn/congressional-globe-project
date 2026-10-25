from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from congressional_globe import reading_images as images
from congressional_globe.models import PageRecord
from congressional_globe.reading_contracts import ReadingCandidate
from congressional_globe.reading_preparation import source_paragraph


def fixture():
    item = "congressionalg7391unit"
    raw = []
    for index in range(2):
        raw.append(
            dict(
                id=f"par_000010_00000{index + 1}",
                reading_order=index,
                bbox=dict(left=100, top=100 + index * 100, right=300, bottom=180 + index * 100),
                line_ids=[f"line{index}"],
                text_ocr="word",
                text_normalized="word",
                lines=[
                    dict(
                        id=f"line{index}",
                        text="word",
                        words=[
                            dict(
                                id=f"word{index}",
                                text="word",
                                bbox=dict(
                                    left=90,
                                    top=100 + index * 100,
                                    right=300,
                                    bottom=180 + index * 100,
                                ),
                            )
                        ],
                    )
                ],
            )
        )
    page = PageRecord.model_validate(
        dict(
            id=f"ia:{item}:leaf:10",
            item_identifier=item,
            part_number=1,
            scan_leaf=10,
            hocr_page_id="page_000010",
            printed_page={},
            image_width_px=1000,
            image_height_px=1500,
            text_ocr="word word",
            paragraphs=raw,
        )
    )
    unit = ReadingCandidate(
        id="synthetic",
        part_number=1,
        stratum="ordinary",
        split="primary",
        target=[source_paragraph(page, p) for p in page.paragraphs],
        selection_reason="Synthetic geometry example",
    )
    plan = images.plan_page(unit, page, "a" * 64, "b" * 64)
    return unit, plan


def test_union_covers_every_paragraph_and_word_without_fabricated_source_id():
    unit, plan = fixture()
    assert plan.region.left == 58
    assert len(plan.sources) == 2
    spans = images.evidence_coverage(plan, unit)
    assert {p.source_id for p in unit.target} == {span.source_id for span in spans}
    assert all(span.start == 0 and span.end == 4 for span in spans)


def test_clipped_region_and_wrong_raw_binding_are_rejected():
    unit, plan = fixture()
    data = plan.model_dump()
    data["region"]["left"] = 110
    with pytest.raises(ValueError, match="clips"):
        images.ReadingImagePlan.model_validate(data)
    changed = plan.sources[0].model_copy(update={"raw_sha256": "0" * 64})
    with pytest.raises(ValueError, match="span/hash"):
        images.evidence_coverage(plan.model_copy(update={"sources": [changed]}), unit)
    with pytest.raises(ValueError, match="identity"):
        images.evidence_coverage(plan, unit.model_copy(update={"id": "other"}))


def _fake_download(plan, calls):
    def download(url, path, limit):
        calls.append(limit)
        if path.suffix == ".json":
            path.write_text(
                json.dumps(
                    dict(
                        width=1000,
                        height=1500,
                        id=f"https://iiif.archive.org/iiif/{plan.item_identifier}/{plan.item_identifier}_0010.jp2",
                    )
                )
            )
        else:
            box = plan.region
            width = min(plan.max_width, box.right - box.left)
            height = round((box.bottom - box.top) * width / (box.right - box.left))
            Image.new("RGB", (width, height), "white").save(path, format="JPEG")
        payload = path.read_bytes()
        receipt = images.scan_fetch.DownloadReceipt(
            requested_url=url,
            resolved_url=url,
            retrieved_at_utc="2026-10-24T00:00:00Z",
            elapsed_seconds=0,
            bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            content_type="application/json",
        )
        path.with_suffix(path.suffix + ".receipt.json").write_text(receipt.model_dump_json())
        return receipt

    return download


def test_downloaded_binding_validates_bytes_dimensions_and_saved_plan(tmp_path, monkeypatch):
    _, plan = fixture()
    calls = []
    monkeypatch.setattr(images.scan_fetch, "download", _fake_download(plan, calls))
    budget = images.TransferBudget(tmp_path)
    binding = images.fetch_plan(tmp_path, plan, budget)
    assert len(calls) == 2
    images.validate_binding(binding, plan)
    crop = Path(binding["directory"]) / "crop.jpg"
    crop.write_bytes(b"changed")
    with pytest.raises(ValueError, match=r"integrity|SHA|mismatch"):
        images.validate_binding(binding, plan)


def test_transfer_cap_exhaustion_refuses_network(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "TOTAL_BYTES", images.PRIOR_BYTES)
    budget = images.TransferBudget(tmp_path)
    with pytest.raises(ValueError, match="exhausted"):
        budget.download("https://iiif.archive.org/anything", tmp_path / "missing.jpg", 100)


def test_resume_budget_rejects_false_receipt_byte_counts(tmp_path, monkeypatch):
    _, plan = fixture()
    calls = []
    monkeypatch.setattr(images.scan_fetch, "download", _fake_download(plan, calls))
    images.fetch_plan(tmp_path, plan, images.TransferBudget(tmp_path))
    receipt_path = tmp_path / plan.id / "crop.jpg.receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["bytes"] = 1
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match=r"integrity|mismatch"):
        images.TransferBudget(tmp_path)


def test_resumed_receipts_count_cumulative_bytes_and_zero_new_transfer(tmp_path, monkeypatch):
    _, plan = fixture()
    calls = []
    fake = _fake_download(plan, calls)
    monkeypatch.setattr(images.scan_fetch, "download", fake)
    first = images.TransferBudget(tmp_path)
    images.fetch_plan(tmp_path, plan, first)
    resumed = images.TransferBudget(tmp_path)
    assert resumed.initial_used == first.used
    images.fetch_plan(tmp_path, plan, resumed)
    assert resumed.used - resumed.initial_used == 0
