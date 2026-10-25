"""Materialize and fingerprint fixed reading requests offline; never dispatch them."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from congressional_globe.reading_contracts import EvidenceSpan, ReadingCandidate
from congressional_globe.reading_images import verify_index
from congressional_globe.reading_preflight import SUPPORTED_MODELS
from congressional_globe.scan_models import Sha256


class ImageInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    path: Path
    sha256: Sha256
    sources: list[EvidenceSpan]

    def payload(self) -> str:
        content = self.path.read_bytes()
        if digest(content) != self.sha256:
            raise ValueError("request image bytes changed")
        return base64.b64encode(content).decode("ascii")


class RequestOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    num_ctx: int = Field(default=16384, gt=0, le=16384)
    num_predict: int = Field(default=4096, gt=0, le=4096)
    temperature: Literal[0] = 0


def wire_bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def paragraph_input(paragraph) -> dict:
    return dict(source_id=paragraph.source_id, raw_sha256=paragraph.raw_sha256, raw=paragraph.raw)


def source_message(unit: ReadingCandidate, images: list[ImageInput]) -> str:
    return wire_bytes(
        dict(
            unit_id=unit.id,
            target=[paragraph_input(p) for p in unit.target],
            context_before=[paragraph_input(p) for p in unit.context_before],
            context_after=[paragraph_input(p) for p in unit.context_after],
            images=[
                dict(id=image.id, sources=[span.model_dump() for span in image.sources])
                for image in images
            ],
            image_order="Attached images follow the images list in order.",
        )
    ).decode()


def request_body(
    unit: ReadingCandidate,
    images: list[ImageInput],
    model: str,
    prompt: str,
    schema: dict,
    options: RequestOptions,
) -> bytes:
    if model not in SUPPORTED_MODELS:
        raise ValueError("unsupported exact reading model")
    _check_images(unit, images)
    return wire_bytes(
        dict(
            model=model,
            messages=[
                dict(
                    role="system", content=prompt + "\nReply schema: " + wire_bytes(schema).decode()
                ),
                dict(
                    role="user",
                    content=source_message(unit, images),
                    images=[i.payload() for i in images],
                ),
            ],
            format="json",
            stream=False,
            think=False,
            options=options.model_dump(),
        )
    )


def _check_image_ids(images):
    ids = [image.id for image in images]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("missing or duplicate image IDs")


def _image_spans(images):
    return [span for image in images for span in image.sources]


def _check_images(unit, images):
    _check_image_ids(images)
    targets = {p.source_id: p for p in unit.target}
    spans = _image_spans(images)
    if {span.source_id for span in spans} != set(targets):
        raise ValueError("request images do not match complete target sources")
    for span in spans:
        _check_span(span, targets[span.source_id])


def _check_span(span, paragraph):
    if (span.raw_sha256, span.start, span.end) != (paragraph.raw_sha256, 0, len(paragraph.raw)):
        raise ValueError("request image source span/hash mismatch")


def image_inputs(index: dict, coverage: dict, unit_id: str) -> list[ImageInput]:
    paths = {
        binding["id"]: Path(binding["directory"]) / "crop.jpg" for binding in index["bindings"]
    }
    hashes = {binding["id"]: binding["image_receipt"]["sha256"] for binding in index["bindings"]}
    for reused in index["reused"]:
        plan = json.loads((Path(reused["plan_directory"]) / "plan.json").read_text())
        bundle = json.loads((Path(reused["directory"]) / "bundle.json").read_text())
        paths[plan["id"]] = Path(reused["directory"]) / bundle["images"][0]["file"]
        hashes[plan["id"]] = reused["image_sha256"]
    return [
        ImageInput(id=image_id, path=paths[image_id], sha256=hashes[image_id], sources=spans)
        for image_id, spans in coverage[unit_id].items()
    ]


def describe_request(unit, images, model, prompt, schema, options) -> dict:
    body = request_body(unit, images, model, prompt, schema, options)
    payload = json.loads(body)
    return dict(
        unit_id=unit.id,
        model=model,
        model_digest=SUPPORTED_MODELS[model],
        endpoint="/api/chat",
        request_sha256=digest(body),
        request_bytes=len(body),
        messages_without_image_payloads=[
            {k: v for k, v in m.items() if k != "images"} for m in payload["messages"]
        ],
        images=[image.model_dump(mode="json") for image in images],
        options=options.model_dump(),
        format=payload["format"],
        think=payload["think"],
        stream=payload["stream"],
        text_tokens=None,
        image_tokens=None,
        token_fit="unknown",
        launch_ready=False,
    )


def build_report(prepared: Path, index_path: Path) -> dict:
    units = [
        ReadingCandidate.model_validate_json(s)
        for s in (prepared / "candidates.jsonl").read_text().splitlines()
    ]
    proof = verify_index(index_path, units)
    index = json.loads(index_path.read_text())
    if index["prepared_sha256"] != digest((prepared / "candidates.jsonl").read_bytes()):
        raise ValueError("image index belongs to different candidate bytes")
    prompt = (prepared / "prompt.txt").read_text()
    schema = json.loads((prepared / "reply.schema.json").read_text())
    requests = _describe_all(units, index, proof, prompt, schema)
    return dict(
        schema_version="reading-requests-v1",
        input_files={
            str(p): digest(p.read_bytes())
            for p in [
                prepared / "candidates.jsonl",
                prepared / "prompt.txt",
                prepared / "reply.schema.json",
                index_path,
            ]
        },
        code_sha256=digest(Path(__file__).read_bytes()),
        requests=requests,
        request_count=len(requests),
        inference_calls=0,
        network_requests=0,
        launch_ready=False,
        blockers=[
            "exact_renderer_tokenizer_processor_parity_unknown",
            "source_expectations_incomplete",
            "revised_review_effort_pending",
            "fresh_runtime_identity_required_before_dispatch",
        ],
    )


def _describe_all(units, index, proof, prompt, schema):
    requests = []
    for unit in filter(lambda unit: unit.split == "primary", units):
        images = image_inputs(index, proof["coverage"], unit.id)
        requests.extend(
            describe_request(unit, images, model, prompt, schema, RequestOptions())
            for model in SUPPORTED_MODELS
        )
    return requests


def materialize_record(record: dict) -> bytes:
    """Reconstruct exact request bytes and reject changed saved fields or images."""
    if SUPPORTED_MODELS.get(record["model"]) != record["model_digest"]:
        raise ValueError("request model digest mismatch")
    messages = [dict(message) for message in record["messages_without_image_payloads"]]
    messages[1]["images"] = [ImageInput.model_validate(i).payload() for i in record["images"]]
    body = wire_bytes(
        dict(
            model=record["model"],
            messages=messages,
            format=record["format"],
            stream=record["stream"],
            think=record["think"],
            options=RequestOptions.model_validate(record["options"]).model_dump(),
        )
    )
    if (digest(body), len(body)) != (record["request_sha256"], record["request_bytes"]):
        raise ValueError("saved request fingerprint mismatch")
    return body


def write_report(report: dict, output: Path) -> None:
    content = wire_bytes(report) + b"\n"
    if output.exists() and output.read_bytes() != content:
        raise ValueError("refusing to overwrite different request manifest")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_report(build_report(args.prepared, args.images), args.output)


if __name__ == "__main__":
    main()
