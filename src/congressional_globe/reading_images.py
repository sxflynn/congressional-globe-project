"""Source-checked, page-region image coverage for fixed clean-reading candidates."""

from __future__ import annotations

import argparse
import fcntl
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator

from congressional_globe import scan_fetch
from congressional_globe.extraction import load_page_map
from congressional_globe.inventory import resolve_source_path, sha256_file
from congressional_globe.models import BoundingBox, PageRecord, ParagraphRecord
from congressional_globe.reading_contracts import EvidenceSpan, ReadingCandidate, text_hash
from congressional_globe.reading_preparation import _Sources
from congressional_globe.reading_source_check import (
    _selected_pages,
    _verify_files,
    _verify_paragraph,
)
from congressional_globe.scan_models import NonBlank, Sha256

PRIOR_BYTES = 1_114_498
TOTAL_BYTES = 12_000_000
MAX_NEW_IMAGES = 18


class ImageSource(EvidenceSpan):
    box: BoundingBox
    line_ids: list[NonBlank]


class ReadingImagePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    unit_id: NonBlank
    unit_sha256: Sha256
    item_identifier: NonBlank
    scan_leaf: int = Field(ge=0)
    ocr_width: int = Field(gt=0)
    ocr_height: int = Field(gt=0)
    hocr_sha256: Sha256
    page_map_sha256: Sha256
    region: BoundingBox
    max_width: int = Field(default=1600, ge=100, le=2000)
    sources: list[ImageSource] = Field(min_length=1)

    @model_validator(mode="after")
    def bounds(self) -> ReadingImagePlan:
        frame = BoundingBox(left=0, top=0, right=self.ocr_width, bottom=self.ocr_height)
        if not contains(frame, self.region):
            raise ValueError("image region outside source frame")
        if any(not contains(self.region, span.box) for span in self.sources):
            raise ValueError("image clips source geometry")
        return self


def contains(outer: BoundingBox, inner: BoundingBox) -> bool:
    return (
        outer.left <= inner.left < inner.right <= outer.right
        and outer.top <= inner.top < inner.bottom <= outer.bottom
    )


def _box(box: BoundingBox | None) -> BoundingBox:
    if box is None:
        raise ValueError("missing source geometry")
    if box.left >= box.right or box.top >= box.bottom:
        raise ValueError("empty source geometry")
    return box


def _union(boxes: list[BoundingBox]) -> BoundingBox:
    return BoundingBox(
        left=min(box.left for box in boxes),
        top=min(box.top for box in boxes),
        right=max(box.right for box in boxes),
        bottom=max(box.bottom for box in boxes),
    )


def _paragraph_box(paragraph: ParagraphRecord) -> BoundingBox:
    words = [word for line in paragraph.lines for word in line.words if word.text.strip()]
    return _union([_box(paragraph.bbox), *[_box(word.bbox) for word in words]])


def _source_span(page: PageRecord, paragraph: ParagraphRecord) -> ImageSource:
    return ImageSource(
        source_id=f"{page.item_identifier}:{page.scan_leaf}:{paragraph.id}",
        raw_sha256=text_hash(paragraph.text_ocr),
        start=0,
        end=len(paragraph.text_ocr),
        box=_paragraph_box(paragraph),
        line_ids=paragraph.line_ids,
    )


def plan_page(
    unit: ReadingCandidate, page: PageRecord, hocr_hash: str, map_hash: str
) -> ReadingImagePlan:
    targets = _page_targets(unit, page)
    sources = []
    for paragraph in page.paragraphs:
        if paragraph.id in targets:
            _verify_paragraph(page, paragraph, targets.pop(paragraph.id))
            sources.append(_source_span(page, paragraph))
    if targets:
        raise ValueError("target paragraphs absent from original source page")
    return _plan(unit, page, sources, hocr_hash, map_hash)


def _page_targets(unit: ReadingCandidate, page: PageRecord) -> dict:
    if page.item_identifier != unit.target[0].item_identifier:
        raise ValueError("wrong source page item")
    return {p.paragraph_id: p for p in unit.target if p.scan_leaf == page.scan_leaf}


def _plan(unit, page, sources, hocr_hash, map_hash) -> ReadingImagePlan:
    union = _union([span.box for span in sources])
    width, height = page.image_width_px, page.image_height_px
    if width is None or height is None:
        raise ValueError("missing source dimensions")
    region = BoundingBox(
        left=max(0, union.left - 32),
        top=max(0, union.top - 32),
        right=min(width, union.right + 32),
        bottom=min(height, union.bottom + 32),
    )
    return ReadingImagePlan(
        id=f"{unit.id}-leaf-{page.scan_leaf}",
        unit_id=unit.id,
        unit_sha256=text_hash(unit.model_dump_json()),
        item_identifier=page.item_identifier,
        scan_leaf=page.scan_leaf,
        ocr_width=width,
        ocr_height=height,
        hocr_sha256=hocr_hash,
        page_map_sha256=map_hash,
        region=region,
        sources=sources,
    )


def prepare_plans(units: list[ReadingCandidate], source_manifest: Path) -> list[ReadingImagePlan]:
    grouped = _group_units(units)
    sources = _Sources.model_validate_json(source_manifest.read_text())
    plans = []
    for source in sources.parts:
        plans.extend(_item_plans(source, grouped))
    if grouped:
        raise ValueError("source manifest lacks required target pages")
    return plans


def _group_units(units: list[ReadingCandidate]):
    grouped = defaultdict(list)
    for unit in units:
        for leaf in {p.scan_leaf for p in unit.target}:
            grouped[(unit.target[0].item_identifier, leaf)].append(unit)
    return grouped


def _item_plans(source, grouped) -> list[ReadingImagePlan]:
    leaves = {leaf for item, leaf in grouped if item == source.identifier}
    if not leaves:
        return []
    _verify_files(source)
    page_map = load_page_map(resolve_source_path(Path(source.page_map_path), relocated=True))
    plans = []
    for page in _selected_pages(
        resolve_source_path(Path(source.hocr_path), relocated=True), page_map, leaves
    ):
        plans.extend(_plans_for_page(source, page, grouped))
    return plans


def _plans_for_page(source, page, grouped):
    return [
        plan_page(unit, page, source.hocr_sha256, source.page_map_sha256)
        for unit in grouped.pop((source.identifier, page.scan_leaf), [])
    ]


def _write_plan(base: Path, plan: ReadingImagePlan) -> Path:
    directory = base / plan.id
    directory.mkdir(exist_ok=True)
    path = directory / "plan.json"
    payload = plan.model_dump_json(indent=2) + "\n"
    if path.exists() and path.read_text() != payload:
        raise ValueError("existing image plan differs; use a new version")
    path.write_text(payload)
    return directory


def _registered(info: scan_fetch.ImageInfo, plan: ReadingImagePlan) -> None:
    scan_fetch._allowed_url(info.service_id)
    path = unquote(urlsplit(info.service_id).path)
    suffix = f"/{plan.item_identifier}_{plan.scan_leaf:04d}.jp2"
    if f"/{plan.item_identifier}/" not in path or not path.endswith(suffix):
        raise ValueError("wrong image item/scan leaf")
    if (info.width, info.height) != (plan.ocr_width, plan.ocr_height):
        raise ValueError("image/source coordinate frame mismatch")


def _url(info: scan_fetch.ImageInfo, plan: ReadingImagePlan) -> str:
    box = plan.region
    region = f"{box.left},{box.top},{box.right - box.left},{box.bottom - box.top}"
    width = min(plan.max_width, box.right - box.left)
    return f"{info.service_id}/{region}/{width},/0/default.jpg"


class TransferBudget:
    """Prior plus all successfully persisted receipts count against the shared cap."""

    def __init__(self, base: Path):
        self.base = base
        self.used = sum(_saved_bytes(p) for p in base.glob("*/*.receipt.json"))

        self.initial_used = self.used
        if PRIOR_BYTES + self.used > TOTAL_BYTES:
            raise ValueError("saved transfers exceed shared cap")

    def download(self, url: str, path: Path, limit: int):
        cached = path.with_suffix(path.suffix + ".receipt.json").exists()
        remaining = TOTAL_BYTES - PRIOR_BYTES - self.used
        if not cached and remaining <= 0:
            raise ValueError("shared image transfer budget exhausted")
        receipt = scan_fetch.download(url, path, max(1, min(limit, remaining)))
        if not cached:
            self.used += receipt.bytes
        return receipt


def _saved_bytes(path: Path) -> int:
    receipt = scan_fetch.DownloadReceipt.model_validate_json(path.read_text())
    payload = path.with_name(path.name.removesuffix(".receipt.json"))
    scan_fetch._check_download(payload, receipt, receipt.requested_url)
    return receipt.bytes


def fetch_plan(base: Path, plan: ReadingImagePlan, budget: TransferBudget) -> dict:
    directory = _write_plan(base, plan)
    url = f"https://iiif.archive.org/iiif/{plan.item_identifier}${plan.scan_leaf}/info.json"
    info_receipt = budget.download(url, directory / "info.json", 2_000_000)
    info = scan_fetch.ImageInfo.model_validate_json((directory / "info.json").read_text())
    _registered(info, plan)
    image_receipt = budget.download(_url(info, plan), directory / "crop.jpg", 8_000_000)
    binding = dict(
        id=plan.id,
        unit_id=plan.unit_id,
        directory=str(directory),
        plan_sha256=sha256_file(directory / "plan.json"),
        info_receipt=info_receipt.model_dump(mode="json"),
        image_receipt=image_receipt.model_dump(mode="json"),
    )
    validate_binding(binding, plan)
    (directory / "binding.json").write_text(json.dumps(binding, indent=2) + "\n")
    return binding


def validate_binding(binding: dict, plan: ReadingImagePlan) -> None:
    directory = Path(binding["directory"])
    if (binding["id"], binding["unit_id"]) != (plan.id, plan.unit_id):
        raise ValueError("binding identity differs from plan")
    saved = ReadingImagePlan.model_validate_json((directory / "plan.json").read_text())
    if saved != plan:
        raise ValueError("supplied image plan differs from saved plan")
    if sha256_file(directory / "plan.json") != binding["plan_sha256"]:
        raise ValueError("image plan hash mismatch")
    info = scan_fetch.ImageInfo.model_validate_json((directory / "info.json").read_text())
    _registered(info, plan)
    _verify_receipt(
        directory / "info.json",
        binding["info_receipt"],
        f"https://iiif.archive.org/iiif/{plan.item_identifier}${plan.scan_leaf}/info.json",
    )
    _verify_receipt(directory / "crop.jpg", binding["image_receipt"], _url(info, plan))
    _dimensions(directory / "crop.jpg", plan)


def _verify_receipt(path: Path, value: dict, url: str) -> None:
    receipt = scan_fetch.DownloadReceipt.model_validate(value)
    scan_fetch._check_download(path, receipt, url)


def _dimensions(path: Path, plan: ReadingImagePlan) -> None:
    box = plan.region
    width = min(plan.max_width, box.right - box.left)
    height = (box.bottom - box.top) * width / (box.right - box.left)
    with Image.open(path) as image:
        if image.width != width or abs(image.height - height) > 1:
            raise ValueError("image dimensions do not match requested region")


def evidence_coverage(plan: ReadingImagePlan, unit: ReadingCandidate) -> list[EvidenceSpan]:
    if plan.unit_id != unit.id or plan.unit_sha256 != text_hash(unit.model_dump_json()):
        raise ValueError("image/unit identity mismatch")
    targets = {p.source_id: p for p in unit.target}
    for span in plan.sources:
        _verify_span(span, targets)
    return [
        EvidenceSpan.model_validate(span.model_dump(exclude={"box", "line_ids"}))
        for span in plan.sources
    ]


def _verify_span(span: ImageSource, targets: dict) -> None:
    target = targets.get(span.source_id)
    if target is None:
        raise ValueError("image span references a non-target")
    if (span.raw_sha256, span.start, span.end) != (target.raw_sha256, 0, len(target.raw)):
        raise ValueError("image source text span/hash mismatch")
    if not contains(span.box, _box(target.bbox)) or span.line_ids != target.line_ids:
        raise ValueError("image source geometry/lines mismatch")


def run(prepared: Path, source_manifest: Path, output: Path, fetch: bool = False) -> dict:
    units = [
        ReadingCandidate.model_validate_json(line)
        for line in (prepared / "candidates.jsonl").read_text().splitlines()
    ]
    units = [unit for unit in units if unit.split == "primary"]
    plans = prepare_plans(units, source_manifest)
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".batch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run_locked(prepared, output, units, plans, fetch)


def _run_locked(prepared, output, units, plans, fetch):
    reused = _reuse_long(units, plans)
    reused_plan = next(plan for plan in plans if plan.unit_id == reused["unit_id"])
    reused_path = _write_plan(output, reused_plan)
    reused.update(
        plan_directory=str(reused_path), plan_sha256=sha256_file(reused_path / "plan.json")
    )
    remaining = [plan for plan in plans if plan.unit_id != reused["unit_id"]]
    if len(remaining) > MAX_NEW_IMAGES:
        raise ValueError("new image count exceeds declared18-image bound")
    budget = TransferBudget(output)
    bindings = _fetch_remaining(output, remaining, budget, fetch)
    result = dict(
        version=1,
        prepared_sha256=sha256_file(prepared / "candidates.jsonl"),
        provider_calls=0,
        primary_units=len(units),
        plans=len(plans),
        new_images=len(bindings),
        image_set_transfer_bytes=budget.used,
        run_new_transfer_bytes=budget.used - budget.initial_used,
        prior_transfer_bytes=PRIOR_BYTES,
        total_transfer_bytes=PRIOR_BYTES + budget.used,
        bindings=bindings,
        reused=[reused],
        source_expectations="pending",
        geometry_coverage_complete=_check_complete(units, plans, bindings, reused)
        if fetch
        else False,
    )
    (output / ("index.json" if fetch else "plan-index.json")).write_text(
        json.dumps(result, indent=2) + "\n"
    )
    return result


def _fetch_remaining(output, plans, budget, fetch):
    bindings = []
    for plan in plans:
        _write_plan(output, plan)
        if fetch:
            bindings.append(fetch_plan(output, plan, budget))
    return bindings


def _check_complete(units, plans, bindings, reused):
    available = {binding["id"] for binding in bindings}
    targets = {unit.id: {p.source_id for p in unit.target} for unit in units}
    covered = defaultdict(set)
    for plan in plans:
        _add_coverage(plan, available, reused, units, covered)
    return dict(covered) == targets


def _add_coverage(plan, available, reused, units, covered):
    if plan.id not in available and plan.unit_id != reused["unit_id"]:
        return
    unit = next(unit for unit in units if unit.id == plan.unit_id)
    covered[unit.id].update(span.source_id for span in evidence_coverage(plan, unit))


def _reuse_long(units, plans) -> dict:
    directory = Path("artifacts/scans/reading-source-20261024-01/long")
    bundle = scan_fetch.read_bundle(directory)
    identity = (
        f"{bundle.target.item_identifier}:{bundle.target.scan_leaf}:{bundle.target.paragraph_id}"
    )
    matches = [unit for unit in units if _single_target(unit, identity)]
    if len(matches) != 1:
        raise ValueError("prior long crop does not match exactly one whole target unit")
    _validate_reuse(bundle, matches[0], plans)
    return dict(
        unit_id=matches[0].id,
        directory=str(directory),
        bundle_sha256=sha256_file(directory / "bundle.json"),
        image_sha256=bundle.images[0].receipt.sha256,
    )


def _validate_reuse(bundle, unit, plans):
    selected = next(plan for plan in plans if plan.unit_id == unit.id)
    expected = (unit.target[0].raw_sha256, selected.hocr_sha256, selected.page_map_sha256)
    actual = (bundle.target.raw_sha256, bundle.target.hocr_sha256, bundle.target.page_map_sha256)
    if actual != expected:
        raise ValueError("prior crop source hash mismatch")
    _check_reused_region(bundle, next(plan for plan in plans if plan.unit_id == unit.id))


def _single_target(unit, identity):
    return len(unit.target) == 1 and unit.target[0].source_id == identity


def _check_reused_region(bundle, plan):
    box = bundle.target.regions[0].bbox
    if any(not contains(box, span.box) for span in plan.sources):
        raise ValueError("existing crop clips target word/paragraph geometry")


def verify_index(index_path: Path, units: list[ReadingCandidate]) -> dict:
    index = json.loads(index_path.read_text())
    primaries = {unit.id: unit for unit in units if unit.split == "primary"}
    coverage = defaultdict(dict)
    for binding in index["bindings"]:
        _verified_binding(binding, primaries, coverage)
    for reused in index["reused"]:
        _verified_reuse(reused, primaries, coverage)
    _require_complete(primaries, coverage)
    return dict(
        index_sha256=sha256_file(index_path),
        primary_units=len(primaries),
        images=sum(len(images) for images in coverage.values()),
        geometry_coverage_complete=True,
        provider_calls=0,
        coverage={
            unit: {image: [span.model_dump() for span in spans] for image, spans in images.items()}
            for unit, images in coverage.items()
        },
    )


def _verified_binding(binding, units, coverage):
    plan = ReadingImagePlan.model_validate_json(
        (Path(binding["directory"]) / "plan.json").read_text()
    )
    validate_binding(binding, plan)
    unit = units[plan.unit_id]
    coverage[unit.id][plan.id] = evidence_coverage(plan, unit)


def _verified_reuse(reused, units, coverage):
    directory = Path(reused["directory"])
    if sha256_file(directory / "bundle.json") != reused["bundle_sha256"]:
        raise ValueError("reused source bundle changed")
    bundle = scan_fetch.read_bundle(directory)
    plan_path = Path(reused["plan_directory"]) / "plan.json"
    if sha256_file(plan_path) != reused["plan_sha256"]:
        raise ValueError("reused image plan changed")
    plan = ReadingImagePlan.model_validate_json(plan_path.read_text())
    _validate_reuse(bundle, units[reused["unit_id"]], [plan])
    coverage[plan.unit_id][plan.id] = evidence_coverage(plan, units[plan.unit_id])


def _require_complete(units, coverage):
    for identity, unit in units.items():
        if _covered_ids(coverage[identity]) != _target_ids(unit):
            raise ValueError("source image coverage incomplete")


def _covered_ids(images) -> set[str]:
    return {span.source_id for spans in images.values() for span in spans}


def _target_ids(unit) -> set[str]:
    return {paragraph.source_id for paragraph in unit.target}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    report = run(args.prepared, args.source_manifest, args.output, args.fetch)
    print(
        json.dumps({k: v for k, v in report.items() if k not in {"bindings", "reused"}}, indent=2)
    )


if __name__ == "__main__":
    main()
