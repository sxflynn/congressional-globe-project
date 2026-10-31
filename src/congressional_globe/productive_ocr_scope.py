"""Exact hOCR target geometry and explicitly partial visible context, offline only."""

import copy
import io
import re
from functools import lru_cache

from lxml import etree  # ty: ignore[unresolved-import]

from congressional_globe.extraction import _paragraph_record
from congressional_globe.productive_ocr_host import (
    BoundaryScope,
    EvidenceRecord,
    _require_file_hash,
    _verify_evidence_file,
    canonical_json,
    sha256_bytes,
    text_sha256,
    validate_host,
)
from congressional_globe.scan_fetch import ScanBundle

SCOPE_INSTRUCTION = (
    "The original OCR is substantially similar to the printed target paragraph but may "
    "need cleanup. Use it as the starting point; verify repairs against the image rather "
    "than transcribing all nearby print. Restore words missed by OCR, including words "
    "on another line, only when they belong to the assigned target paragraph and are "
    "supported by its image. Do not add a whole neighbouring sentence or paragraph. "
    "Only target_regions identify text to return. The full image includes nearby print. "
    "All regions use the supplied image_frame pixel dimensions, with origin at top-left "
    "and exclusive right/bottom edges. "
    "visible_context_spans are context only: never append or prepend their words to a target. "
    "Each context excerpt identifies only the stated source span; partial parent visibility "
    "does not mean the rest of its paragraph is visible or read. Preserve the assigned "
    "target paragraph boundary; if its extent cannot be determined, withhold its reading."
)


def _source_parts(source_id, image):
    item, leaf, paragraph_id = source_id.split(":")
    if (item, int(leaf)) != (image["source_item_identifier"], image["source_scan_leaf"]):
        raise ValueError("boundary source belongs to another item or page")
    return paragraph_id


def _source_ids(payload):
    image = payload["image"]
    source_ids = [p["source_id"] for p in payload["paragraphs"]]
    source_ids.extend(s["source_id"] for s in image["scope"]["visible_context"])
    return tuple(sorted({_source_parts(source_id, image) for source_id in source_ids}))


@lru_cache(maxsize=4)
def _paragraphs(data: bytes, wanted: tuple[str, ...], page_id: str, leaf: int):
    """Use the existing parser, releasing prior content and stopping at the selected page."""
    records = {}
    tags = ("p", "div", "{http://www.w3.org/1999/xhtml}p", "{http://www.w3.org/1999/xhtml}div")
    parser = etree.iterparse(
        io.BytesIO(data), events=("end",), tag=tags, recover=True, huge_tree=True
    )
    for _event, element in parser:
        _capture_record(records, element, wanted, page_id, leaf)
        if _is_page_end(element, page_id):
            return _complete_records(records, wanted)
        _release(element)
    raise ValueError("source scope paragraph missing from pinned hOCR")


def _capture_record(records, element, wanted, page_id, leaf):
    identity = element.get("id")
    if identity in wanted:
        if identity in records:
            raise ValueError("duplicate source paragraph identity on page")
        records[identity] = _record_on_page(element, page_id, leaf)


def _is_page_end(element, page_id):
    return "ocr_page" in element.get("class", "").split() and element.get("id") == page_id


def _complete_records(records, wanted):
    if set(records) != set(wanted):
        raise ValueError("source scope paragraph missing from selected hOCR page")
    return records


def _record_on_page(element, page_id, leaf):
    page = _source_page(element)
    match = re.search(r"ppageno (\d+)", page.get("title", ""))
    observed = None if match is None else int(match.group(1))
    if (page.get("id"), observed) != (page_id, leaf):
        raise ValueError("source paragraph belongs to a different hOCR page")
    return _paragraph_record(element)


def _source_page(element):
    if "ocr_par" not in element.get("class", "").split():
        raise ValueError("source element is not an OCR paragraph")
    pages = [
        parent
        for parent in element.iterancestors()
        if "ocr_page" in parent.get("class", "").split()
    ]
    if len(pages) != 1:
        raise ValueError("source paragraph page is missing or ambiguous")
    return pages[0]


def _release(element):
    element.clear()
    parent = element.getparent()
    while element.getprevious() is not None:
        del parent[0]


def _crop_frame(payload, registry):
    image = payload["image"]
    digest = image["scope"]["crop_bundle_sha256"]
    _verify_base_crop(image, registry, digest)
    _require_file_hash(registry, digest, "source crop bundle")
    bundle = ScanBundle.model_validate_json(registry.files[digest])
    _check_bundle_identity(bundle, image)
    matches = [entry for entry in bundle.images if entry.receipt.sha256 == image["sha256"]]
    if len(matches) != 1:
        raise ValueError("source crop image is missing or ambiguous")
    crop = matches[0]
    x, y, width, height = crop.region
    if (width, height, crop.width, crop.height) != (image["width"], image["height"], width, height):
        raise ValueError("boundary scope requires exact native crop dimensions")
    return dict(
        left=x,
        top=y,
        right=x + width,
        bottom=y + height,
        page_id=bundle.target.hocr_page_id,
        leaf=image["source_scan_leaf"],
    )


def _verify_base_crop(image, registry, bundle_digest):
    digest = image["scope"]["base_registration_sha256"]
    evidence = registry.records.get(digest)
    if evidence is None:
        raise ValueError("original crop registration is absent")
    _verify_evidence_file(registry, digest, evidence, "original crop registration")
    references = evidence.record.get("derivation", {}).get("source_refs", [])
    if bundle_digest not in {entry["sha256"] for entry in references}:
        raise ValueError("crop bundle is not supported by original image registration")
    _check_base_identity(evidence.record, image)


def _check_base_identity(record, image):
    keys = (
        "sha256",
        "source_item_identifier",
        "source_scan_leaf",
        "hocr_sha256",
        "page_map_sha256",
        "width",
        "height",
    )
    if any(record.get(key) != image[key] for key in keys):
        raise ValueError("original registration differs from the scoped image identity")


def _check_bundle_identity(bundle, image):
    target = bundle.target
    actual = (target.item_identifier, target.scan_leaf, target.hocr_sha256, target.page_map_sha256)
    expected = (
        image["source_item_identifier"],
        image["source_scan_leaf"],
        image["hocr_sha256"],
        image["page_map_sha256"],
    )
    if actual != expected:
        raise ValueError("crop bundle source identity differs from registered image")


def _inside(box, frame):
    return (
        frame["left"] <= box["left"] < box["right"] <= frame["right"]
        and frame["top"] <= box["top"] < box["bottom"] <= frame["bottom"]
    )


def _local_box(box, frame):
    if box is None:
        raise ValueError("source geometry is unavailable")
    value = box.model_dump()
    if not _inside(value, frame):
        raise ValueError("selected source span is not fully visible; do not clip or infer it")
    return dict(
        left=value["left"] - frame["left"],
        top=value["top"] - frame["top"],
        right=value["right"] - frame["left"],
        bottom=value["bottom"] - frame["top"],
    )


def _target_boxes(payload, records, frame):
    boxes = {}
    for paragraph in payload["paragraphs"]:
        identity = _source_parts(paragraph["source_id"], payload["image"])
        record = records[identity]
        if record.text_ocr != paragraph["raw"]["text"]:
            raise ValueError("boundary target raw text differs from pinned hOCR")
        boxes[paragraph["alias"]] = _local_box(record.bbox, frame)
    return boxes


def _visible_line(source_id, line_id, image, records, frame):
    record = records[_source_parts(source_id, image)]
    lines = [line for line in record.lines if line.id == line_id]
    if len(lines) != 1:
        raise ValueError("visible source line missing or ambiguous")
    line = lines[0]
    start = _line_offset(record, line)
    return dict(
        source_id=source_id,
        paragraph_sha256=text_sha256(record.text_ocr),
        line_id=line.id,
        raw_start=start,
        raw_end=start + len(line.text),
        text=line.text,
        text_sha256=text_sha256(line.text),
        crop_region=_local_box(line.bbox, frame),
        parent_visibility=_parent_visibility(record.bbox, frame),
    )


def _line_offset(record, line):
    if not re.search(r"[^\W_]", line.text):
        raise ValueError("visible context lacks stable text for copy exclusion")
    if record.text_ocr.count(line.text) != 1:
        raise ValueError("visible line has ambiguous source text mapping")
    return record.text_ocr.index(line.text)


def _parent_visibility(box, frame):
    if box is None:
        raise ValueError("context parent geometry unavailable")
    return "complete" if _inside(box.model_dump(), frame) else "partial"


def verify_scope(payload, registry):
    from congressional_globe.productive_ocr_routing import TEXT_PROMPT_V4

    image = payload["image"]
    _verify_scope_records(image, registry)
    frame = _crop_frame(payload, registry)
    records = _paragraphs(
        registry.files[image["hocr_sha256"]], _source_ids(payload), frame["page_id"], frame["leaf"]
    )
    boxes = _target_boxes(payload, records, frame)
    bound = {entry["paragraph_alias"]: entry["crop_region"] for entry in image["bindings"]}
    if boxes != bound:
        raise ValueError("target regions differ from exact source paragraph geometry")
    _verify_context(payload, records, frame)
    prompt = registry.files.get(payload["prompt_sha256"], b"")
    if not prompt.startswith(TEXT_PROMPT_V4.encode()) or not prompt.endswith(
        SCOPE_INSTRUCTION.encode()
    ):
        raise ValueError("scoped image requires strict reply and exact target-only instructions")


def _verify_scope_records(image, registry):
    content = canonical_json(image["scope"])
    digest = sha256_bytes(content)
    _require_file_hash(registry, digest, "boundary scope")
    for key in ("binding_manifest_sha256", "registration_evidence_sha256"):
        if registry.records[image[key]].record.get("boundary_scope_sha256") != digest:
            raise ValueError("scope differs from geometry evidence")


def _verify_context(payload, records, frame):
    image = payload["image"]
    spans = image["scope"]["visible_context"]
    _verify_context_budget(payload, spans)
    keys = [(s["source_id"], s["line_id"]) for s in spans]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate visible context span")
    targets = {p["source_id"] for p in payload["paragraphs"] if p["role"] == "target"}
    target_boxes = _assigned_target_boxes(payload)
    for span in spans:
        _verify_one_context(span, image, records, frame, targets, target_boxes)


def _verify_context_budget(payload, spans):
    visible = sum(len(span["text"]) for span in spans)
    if _existing_context_size(payload) + visible > 2000:
        raise ValueError("visible and full context exceed the aggregate context limit")


def _existing_context_size(payload):
    contexts = [p for p in payload["paragraphs"] if p["role"] == "context"]
    raw = sum(len(p["raw"]["text"]) for p in contexts)
    static = sum(len(p["static"]["text"]) for p in contexts)
    return raw + static


def _assigned_target_boxes(payload):
    aliases = {p["alias"] for p in payload["paragraphs"] if p["role"] == "target"}
    return [
        item["crop_region"]
        for item in payload["image"]["bindings"]
        if item["paragraph_alias"] in aliases
    ]


def _verify_one_context(span, image, records, frame, targets, target_boxes):
    if span["source_id"] in targets:
        raise ValueError("a target cannot masquerade as excluded neighbouring context")
    expected = _visible_line(span["source_id"], span["line_id"], image, records, frame)
    if span != expected:
        raise ValueError("visible context text/span/hash/visibility/geometry differs from source")
    if any(_overlap(span["crop_region"], box) for box in target_boxes):
        raise ValueError("context and target geometry overlap; boundary is ambiguous")


def _overlap(left, right):
    return max(left["left"], right["left"]) < min(left["right"], right["right"]) and max(
        left["top"], right["top"]
    ) < min(left["bottom"], right["bottom"])


def _register(registry, value):
    content = canonical_json(value)
    identity = sha256_bytes(content)
    registry.files[identity] = content
    return identity


def _rebind_geometry(payload, registry, boxes):
    image = payload["image"]
    for key in ("binding_manifest_sha256", "registration_evidence_sha256"):
        old = registry.records[image[key]]
        record = copy.deepcopy(old.record)
        record["paragraph_boxes"] = boxes
        record["boundary_scope_sha256"] = _register(registry, image["scope"])
        record["derivation"] = dict(
            method=(
                "Exact pinned hOCR paragraph bounds and native crop translation; "
                "original pixels/legibility evidence unchanged."
            ),
            crop_bundle_sha256=image["scope"]["crop_bundle_sha256"],
        )
        digest = _register(registry, record)
        registry.records[digest] = EvidenceRecord(record, registry.files[digest])
        image[key] = digest
    for entry in image["bindings"]:
        entry["crop_region"] = boxes[entry["paragraph_alias"]]


def prepare_source_scope(host, registry, bundle_bytes: bytes, context_lines):
    """Derive a new offline input; never overwrite the registered crop or old records."""
    host = copy.deepcopy(validate_host(host, registry))
    payload = host["payload"]
    image = payload["image"]
    if "scope" in image:
        raise ValueError("derive source scope from an original host, not another derived scope")
    image["scope"] = dict(
        contract="ocr-visible-boundary-scope-v1",
        crop_bundle_sha256=sha256_bytes(bundle_bytes),
        base_registration_sha256=image["registration_evidence_sha256"],
        visible_context=[],
    )
    registry.files[sha256_bytes(bundle_bytes)] = bundle_bytes
    frame = _crop_frame(payload, registry)
    source_ids = [p["source_id"] for p in payload["paragraphs"]] + [s for s, _line in context_lines]
    wanted = tuple(sorted({_source_parts(s, image) for s in source_ids}))
    records = _paragraphs(
        registry.files[image["hocr_sha256"]], wanted, frame["page_id"], frame["leaf"]
    )
    spans = [_visible_line(s, line, image, records, frame) for s, line in context_lines]
    image["scope"] = BoundaryScope.model_validate(
        {**image["scope"], "visible_context": spans}
    ).model_dump(mode="json")
    _rebind_geometry(payload, registry, _target_boxes(payload, records, frame))
    _bind_prompt_code(host, registry)
    return validate_host(host, registry)


def _bind_prompt_code(host, registry):
    from congressional_globe.productive_ocr_runner import code_identity

    payload = host["payload"]
    prompt = registry.files[payload["prompt_sha256"]].decode()
    payload["prompt_sha256"] = sha256_bytes((prompt + "\n\n" + SCOPE_INSTRUCTION).encode())
    registry.files[payload["prompt_sha256"]] = (prompt + "\n\n" + SCOPE_INSTRUCTION).encode()
    payload["code_sha256"] = _register(registry, code_identity())
    host["packet_sha256"] = sha256_bytes(canonical_json(payload))


def reject_context_copy(text, target, scope):
    raw = _words(target["raw"]["text"])
    static = _words(target["static"]["text"])
    proposed = _words(text)
    for context in scope.get("visible_context", []):
        phrase = _words(context["text"])
        if _phrase_count(proposed, phrase) > max(
            _phrase_count(raw, phrase), _phrase_count(static, phrase)
        ):
            raise ValueError(
                "visible neighbouring source text copied into target; withhold ambiguous scope"
            )


def _words(text):
    return " " + " ".join(re.findall(r"[^\W_]+", text.casefold())) + " "


def _phrase_count(text, phrase):
    return len(re.findall(r"(?=" + re.escape(phrase) + r")", text))
