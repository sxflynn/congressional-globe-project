"""Bounded, audited Internet Archive IIIF region downloads and offline replay."""

from __future__ import annotations

import fcntl
import hashlib
import io
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from PIL import Image
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from congressional_globe.scan_models import ScanTarget


class ImageInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    service_id: str = Field(validation_alias=AliasChoices("@id", "id"))
    width: int = Field(gt=0, le=50000)
    height: int = Field(gt=0, le=50000)


class DownloadReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requested_url: str
    resolved_url: str
    retrieved_at_utc: str
    elapsed_seconds: float = Field(ge=0)
    bytes: int = Field(gt=0)
    sha256: str
    content_type: str


class ScanImage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    region: tuple[int, int, int, int]
    receipt: DownloadReceipt


class ScanBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "scan-bundle-v1"
    target: ScanTarget
    target_sha256: str
    info_receipt: DownloadReceipt
    images: list[ScanImage]
    code_sha256: dict[str, str] = Field(default_factory=dict)
    registration: str = "exact dimensions; native pixel coordinates; no inferred scaling/rotation"


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _code_hashes() -> dict[str, str]:
    base = Path(__file__).parent
    return {
        name: digest((base / name).read_bytes())
        for name in ("scan_models.py", "scan_geometry.py", "scan_fetch.py")
    }


def _allowed_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "iiif.archive.org":
        raise ValueError("Scan requests must use the official HTTPS iiif.archive.org host")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Unexpected image service credentials or port")


class ArchiveRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _allowed_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _write_json(path: Path, value: BaseModel) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(value.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _event(directory: Path, event: str, **details: object) -> None:
    with (directory / "events.jsonl").open("a", encoding="utf-8") as output:
        output.write(json.dumps({"event": event, "at": datetime.now(UTC).isoformat(), **details}))
        output.write("\n")


def download(url: str, path: Path, limit: int) -> DownloadReceipt:
    """One request, no automatic retries; durable successful cache with integrity checks."""
    _allowed_url(url)
    receipt_path = path.with_suffix(path.suffix + ".receipt.json")
    if receipt_path.exists():
        receipt = DownloadReceipt.model_validate_json(receipt_path.read_text())
        _check_download(path, receipt, url)
        _event(path.parent, "cache_hit", file=path.name, bytes=receipt.bytes)
        return receipt
    _event(path.parent, "request_started", url=url, max_bytes=limit)
    try:
        return _download_once(url, path, limit, receipt_path)
    except Exception as error:
        _event(path.parent, "request_failed", url=url, error=str(error))
        raise


def _download_once(url: str, path: Path, limit: int, receipt_path: Path) -> DownloadReceipt:
    started = time.monotonic()
    request = Request(url, headers={"User-Agent": "CongressionalGlobeDigitalHistory/0.1"})
    with build_opener(ArchiveRedirect()).open(request, timeout=45) as response:
        _allowed_url(response.url)
        payload = response.read(limit + 1)
        if not payload or len(payload) > limit:
            raise ValueError("Empty image response or download exceeds byte limit")
        receipt = DownloadReceipt(
            requested_url=url,
            resolved_url=response.url,
            retrieved_at_utc=datetime.now(UTC).isoformat(),
            elapsed_seconds=time.monotonic() - started,
            bytes=len(payload),
            sha256=digest(payload),
            content_type=response.headers.get("content-type", ""),
        )
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_bytes(payload)
    temporary.replace(path)
    _write_json(receipt_path, receipt)
    _event(path.parent, "request_completed", **receipt.model_dump())
    return receipt


def _check_download(path: Path, receipt: DownloadReceipt, url: str) -> None:
    payload = path.read_bytes()
    if receipt.requested_url != url or len(payload) != receipt.bytes:
        raise ValueError("Cached download URL/size mismatch")
    if digest(payload) != receipt.sha256:
        raise ValueError("Cached download SHA-256 mismatch; preserve and inspect it")


def _registered_info(info: ImageInfo, target: ScanTarget) -> None:
    _allowed_url(info.service_id)
    path = unquote(urlsplit(info.service_id).path)
    suffix = f"/{target.item_identifier}_{target.scan_leaf:04d}.jp2"
    if f"/{target.item_identifier}/" not in path or not path.endswith(suffix):
        raise ValueError("Image service does not identify the requested item and scan leaf")
    if (info.width, info.height) != (target.ocr_width, target.ocr_height):
        raise ValueError("Image/hOCR dimensions differ; registration must be investigated")


def _crop_image(directory: Path, info: ImageInfo, target: ScanTarget, index: int) -> ScanImage:
    box = target.regions[index].bbox
    region = (box.left, box.top, box.right - box.left, box.bottom - box.top)
    width = min(target.max_width, region[2])
    url = f"{info.service_id}/" + ",".join(map(str, region)) + f"/{width},/0/default.jpg"
    filename = f"crop-{index + 1:02d}.jpg"
    receipt = download(url, directory / filename, 8_000_000)
    payload = (directory / filename).read_bytes()
    with Image.open(io.BytesIO(payload)) as image:
        image.verify()
    with Image.open(io.BytesIO(payload)) as image:
        actual_width, actual_height = image.size
    expected_height = region[3] * width / region[2]
    if actual_width != width or abs(actual_height - expected_height) > 1:
        raise ValueError("Returned crop dimensions do not match the requested region")
    return ScanImage(
        file=filename, width=actual_width, height=actual_height, region=region, receipt=receipt
    )


def prepare_bundle(directory: Path, target: ScanTarget) -> str:
    if not 1 <= len(target.regions) <= 8:
        raise ValueError("A bounded crop request must contain 1-8 regions")
    directory.mkdir(parents=True, exist_ok=True)
    serialized = target.model_dump_json()
    target_hash = digest(serialized.encode())
    target_path = directory / "target.json"
    if target_path.exists():
        existing = ScanTarget.model_validate_json(target_path.read_text())
        if digest(existing.model_dump_json().encode()) != target_hash:
            raise ValueError("Output directory contains a different frozen target; use a new path")
    else:
        _write_json(target_path, target)
    return target_hash


def fetch_bundle(directory: Path, target: ScanTarget) -> ScanBundle:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".fetch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            return _fetch_bundle(directory, target)
        except Exception as error:
            _event(directory, "bundle_failed", error=str(error))
            raise


def _fetch_bundle(directory: Path, target: ScanTarget) -> ScanBundle:
    target_hash = prepare_bundle(directory, target)
    code_hashes = _code_hashes()
    _event(directory, "bundle_started", target_sha256=target_hash, code_sha256=code_hashes)
    url = f"https://iiif.archive.org/iiif/{target.item_identifier}${target.scan_leaf}/info.json"
    receipt = download(url, directory / "info.json", 2_000_000)
    info = ImageInfo.model_validate_json((directory / "info.json").read_text())
    _registered_info(info, target)
    images = [_crop_image(directory, info, target, index) for index in range(len(target.regions))]
    bundle = ScanBundle(
        target=target,
        target_sha256=target_hash,
        info_receipt=receipt,
        images=images,
        code_sha256=code_hashes,
    )
    _write_json(directory / "bundle.json", bundle)
    _event(directory, "bundle_ready", crops=len(images), target_sha256=target_hash)
    return bundle


def read_bundle(directory: Path) -> ScanBundle:
    """Read an existing bundle without network access; validate frozen inputs and image bytes."""
    bundle = ScanBundle.model_validate_json((directory / "bundle.json").read_text())
    if digest(bundle.target.model_dump_json().encode()) != bundle.target_sha256:
        raise ValueError("Bundle target hash mismatch")
    frozen = ScanTarget.model_validate_json((directory / "target.json").read_text())
    if digest(frozen.model_dump_json().encode()) != bundle.target_sha256:
        raise ValueError("Frozen target.json does not match the bundle target")
    _check_download(directory / "info.json", bundle.info_receipt, bundle.info_receipt.requested_url)
    info = ImageInfo.model_validate_json((directory / "info.json").read_text())
    _registered_info(info, bundle.target)
    if len(bundle.images) != len(bundle.target.regions):
        raise ValueError("Cached crop count does not match the target")
    for index, image in enumerate(bundle.images):
        _verify_cached_image(directory, bundle, info, index, image)
    return bundle


def _verify_cached_image(
    directory: Path, bundle: ScanBundle, info: ImageInfo, index: int, image: ScanImage
) -> None:
    if Path(image.file).name != image.file:
        raise ValueError("Unexpected cached image filename")
    box = bundle.target.regions[index].bbox
    region = (box.left, box.top, box.right - box.left, box.bottom - box.top)
    if image.region != region:
        raise ValueError("Cached image region differs from frozen target geometry")
    width = min(bundle.target.max_width, region[2])
    url = f"{info.service_id}/" + ",".join(map(str, region)) + f"/{width},/0/default.jpg"
    _check_download(directory / image.file, image.receipt, url)
    with Image.open(directory / image.file) as actual:
        dimensions = actual.size
    if dimensions != (image.width, image.height):
        raise ValueError("Cached image dimensions differ from its manifest")
    if image.width != width or abs(image.height - region[3] * width / region[2]) > 1:
        raise ValueError("Cached image dimensions differ from target geometry")
