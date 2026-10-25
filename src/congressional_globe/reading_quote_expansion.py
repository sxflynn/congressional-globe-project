"""Build the bounded quote-v2 expansion manifest offline; never dispatch."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from congressional_globe.reading_controls import make_control
from congressional_globe.reading_requests import (
    ImageInput,
    digest,
    materialize_record,
    wire_bytes,
)

DEFAULT_MODELS = ("qwen3.8:27b-mlx", "gemma4:31b-mlx")
DEFAULT_CONTROL_UNIT = "reading-3077c2e0a49061bbcf29"


def quote_system(prompt: str, schema: dict) -> str:
    """Reproduce the exact quote-v2 system message from prompt and schema bytes."""
    return prompt + "\nReply schema: " + wire_bytes(schema).decode()


def to_quote_record(record: dict, prompt: str, schema: dict) -> dict:
    """Version one offset-v1 record into the same quote-v2 request contract."""
    materialize_record(record)
    result = copy.deepcopy(record)
    result["messages_without_image_payloads"][0]["content"] = quote_system(prompt, schema)
    result.update(
        response_contract="quote-v2",
        text_tokens=None,
        image_tokens=None,
        token_fit="unknown",
        launch_ready=False,
    )
    refresh_request(result)
    return result


def refresh_request(record: dict) -> None:
    """Recompute exact request bytes/hash after a prompt or image change."""
    messages = [dict(message) for message in record["messages_without_image_payloads"]]
    messages[1]["images"] = [
        ImageInput.model_validate(image).payload() for image in record["images"]
    ]
    body = wire_bytes(
        dict(
            model=record["model"],
            messages=messages,
            format=record["format"],
            stream=record["stream"],
            think=record["think"],
            options=record["options"],
        )
    )
    record["request_sha256"] = digest(body)
    record["request_bytes"] = len(body)
    materialize_record(record)


def build_expansion(
    launch: list[dict],
    completed: list[dict],
    prompt: str,
    schema: dict,
    models: tuple[str, ...] = DEFAULT_MODELS,
    control_unit_id: str = DEFAULT_CONTROL_UNIT,
) -> dict:
    """Return 36 new requests plus the exact four reusable completed requests."""
    primary = [record for record in launch if not record.get("control_kind")]
    by_key = {(record["unit_id"], record["model"]): record for record in primary}
    completed_by_key = {(record["unit_id"], record["model"]): record for record in completed}
    reused = _reused(completed_by_key, by_key, models, prompt, schema)
    new = _new_real(by_key, completed_by_key, models, prompt, schema)
    controls = _controls(launch, by_key, models, control_unit_id, prompt, schema)
    requests = sorted(
        new + controls,
        key=lambda record: (record["model"], record["unit_id"], record.get("control_kind", "")),
    )
    _check_request_set(requests, reused, models)
    return {
        "schema_version": "reading-quote-expansion-v1",
        "request_count": len(requests),
        "models": list(models),
        "reused_requests": reused,
        "requests": requests,
        "cumulative_prior_attempts": 12,
        "cumulative_attempts_after_expansion": 48,
    }


def _completed_models(completed_by_key, models):
    return {key for key in completed_by_key if key[1] in models}


def _reused(completed_by_key, by_key, models, prompt, schema):
    keys = sorted(_completed_models(completed_by_key, models))
    if len(keys) != 4:
        raise ValueError("expansion requires exactly four reusable completed quote requests")
    return [_reuse_one(key, completed_by_key, by_key, prompt, schema) for key in keys]


def _reuse_one(key, completed_by_key, by_key, prompt, schema):
    if key not in by_key:
        raise ValueError("completed quote request has no matching source launch record")
    rebuilt = to_quote_record(by_key[key], prompt, schema)
    saved = completed_by_key[key]
    if rebuilt["request_sha256"] != saved["request_sha256"]:
        raise ValueError("completed quote request is not reproducible from captured sources")
    return copy.deepcopy(saved)


def _new_real(by_key, completed_by_key, models, prompt, schema):
    new = []
    for key in sorted(by_key):
        if key[1] not in models or key in completed_by_key:
            continue
        new.append(to_quote_record(by_key[key], prompt, schema))
    return new


def _controls(launch, by_key, models, control_unit_id, prompt, schema):
    controls = []
    for model in models:
        base = to_quote_record(by_key[(control_unit_id, model)], prompt, schema)
        controls.append(make_control(base, "missing_image"))
        unrelated = _unrelated_source(launch, model)
        controls.append(make_control(base, "unrelated_image", unrelated))
    return controls


def _unrelated_source(launch, model):
    control = next(record for record in launch if _is_unrelated_control(record, model))
    image_ids = {image["id"] for image in control["images"]}
    return next(record for record in launch if _is_primary_with_images(record, model, image_ids))


def _is_unrelated_control(record, model):
    return record.get("control_kind") == "unrelated_image" and record["model"] == model


def _is_primary_with_images(record, model, image_ids):
    if record.get("control_kind"):
        return False
    if record["model"] != model:
        return False
    return image_ids.issubset({image["id"] for image in record["images"]})


def _check_request_set(requests, reused, models):
    _check_count(requests, 18 * len(models), "new requests")
    ids = [task_id(record) for record in requests + reused]
    if len(ids) != len(set(ids)):
        raise ValueError("expansion contains duplicate task identities")
    _check_count(_control_records(requests), 2 * len(models), "controls")


def _check_count(records, expected, label):
    if len(records) != expected:
        raise ValueError(f"expected {expected} {label}, got {len(records)}")


def _control_records(records):
    return [record for record in records if record.get("control_kind")]


def task_id(record: dict) -> str:
    """Match the frozen dispatch identity without importing the transport module."""
    control = record.get("control_kind")
    if control:
        return f"{record['model']}::{control}::{record['unit_id']}"
    return f"{record['model']}::{record['unit_id']}"


def build_from_paths(
    launch_path: Path,
    completed_path: Path,
    prompt_path: Path,
    schema_path: Path,
    models: tuple[str, ...] = DEFAULT_MODELS,
    control_unit_id: str = DEFAULT_CONTROL_UNIT,
) -> dict:
    """Load frozen inputs and return the expansion report without writing or dispatching."""
    launch = json.loads(launch_path.read_text())["requests"]
    completed = json.loads(completed_path.read_text())["requests"]
    return build_expansion(
        launch,
        completed,
        prompt_path.read_text(),
        json.loads(schema_path.read_text()),
        models,
        control_unit_id,
    )


def write_report(report: dict, output: Path) -> None:
    content = wire_bytes(report) + b"\n"
    if output.exists() and output.read_bytes() != content:
        raise ValueError("refusing to overwrite a different expansion manifest")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launch", type=Path, required=True)
    parser.add_argument("--completed", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--control-unit", default=DEFAULT_CONTROL_UNIT)
    args = parser.parse_args()
    report = build_from_paths(
        args.launch,
        args.completed,
        args.prompt,
        args.schema,
        DEFAULT_MODELS,
        args.control_unit,
    )
    write_report(report, args.output)


if __name__ == "__main__":
    main()
