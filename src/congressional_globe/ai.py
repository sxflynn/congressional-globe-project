"""OpenAI Batch request preparation and explicitly confirmed submission."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from openai import OpenAI

from congressional_globe.models import CleanupResult, strict_json_schema

SYSTEM_PROMPT = (
    "You are preserving historical OCR, not rewriting prose. Return only conservative, explicit "
    "patch operations that you are confident are correct. Correct only clear mechanical OCR and "
    "line-wrap artifacts. In "
    "particular, join an alphabetic word split by a line-end hyphen and whitespace when the "
    "joined form is an unambiguous ordinary word: for example, 'him- self' becomes 'himself', "
    "'under- stand' becomes 'understand', and 'explana- tion' becomes 'explanation'. Treat the "
    "whole split token as one span: expected must be the complete source substring being "
    "replaced, including the hyphen and the following spaces, and replacement must be exactly "
    "the joined word. Worked example: for the source 'the meas- ure passed', emit exactly one "
    "edit whose expected is 'meas- ure' and whose replacement is 'measure'; do not emit expected "
    "'meas-' with replacement 'measure', which would leave a dangling fragment. Apply every "
    "clear line-wrap join present in the text, not only the first one. Preserve "
    "legitimate compound-word hyphens (for example 'fellow-citizen') and historical spelling. "
    "Every edit is applied independently to the unmodified user text, so edits must be sorted by "
    "start_char, must not overlap, and expected must "
    "exactly reproduce the source substring, including spaces and hyphens. Each distinct source "
    "span may appear in at most one edit: never emit the same expected span twice. Prefer an "
    "expected span long enough to occur only once in the text. Return an empty edits list when "
    "nothing "
    "needs correction; never emit an edit whose replacement equals expected, and never insert "
    "placeholder or whitespace-only edits to preserve positions. Do not "
    "modernize spelling, add content, omit text, or infer corrections when the OCR is ambiguous. "
    "Mark uncertain material for image review by setting needs_image_review to true and naming "
    "the material in review_reason; otherwise set needs_image_review to false and review_reason "
    "to null. When you are not confident, leave the text unchanged."
)


def prepare_batch(paragraph_path: Path, destination: Path, model: str) -> int:
    schema = strict_json_schema(CleanupResult)
    count = 0
    with (
        paragraph_path.open(encoding="utf-8") as source,
        destination.open("w", encoding="utf-8") as target,
    ):
        for line in source:
            if line.strip():
                payload = json.loads(line)
                _write_request(target, payload, schema, model)
                count += 1
    return count


def submit_batch(request_path: Path, state_directory: Path, confirm_submit: bool) -> Path:
    if not confirm_submit:
        raise ValueError("Refusing API submission without --confirm-submit")
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is required to submit a batch")
    client = OpenAI()
    with request_path.open("rb") as source:
        uploaded = client.files.create(file=source, purpose="batch")
    batch = client.batches.create(
        input_file_id=uploaded.id,
        endpoint="/v1/responses",
        completion_window="24h",
        metadata={"pipeline": "congressional-globe-corpus", "request_file": request_path.name},
    )
    state_directory.mkdir(parents=True, exist_ok=True)
    manifest = state_directory / f"{batch.id}.json"
    manifest.write_text(
        json.dumps({"batch_id": batch.id, "input_file_id": uploaded.id}, indent=2) + "\n"
    )
    return manifest


def reconcile_batch(
    batch_output_path: Path,
    paragraph_path: Path,
    destination: Path,
    review_destination: Path,
) -> dict[str, int]:
    """Validate Batch output and write a separate derived-text layer."""
    paragraphs = _paragraphs_by_id(paragraph_path)
    counts = {"accepted": 0, "review": 0}
    with (
        batch_output_path.open(encoding="utf-8") as source,
        destination.open("w", encoding="utf-8") as target,
        review_destination.open("w", encoding="utf-8") as review,
    ):
        for line in source:
            if line.strip():
                _reconcile_line(json.loads(line), paragraphs, target, review, counts)
    return counts


def _write_request(
    target: Any, paragraph: dict[str, Any], schema: dict[str, Any], model: str
) -> None:
    request = {
        "custom_id": paragraph["id"],
        "method": "POST",
        "url": "/v1/responses",
        "body": {
            "model": model,
            "input": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": paragraph["text_ocr"]},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "cleanup_result",
                    "strict": True,
                    "schema": schema,
                }
            },
        },
    }
    target.write(json.dumps(request, separators=(",", ":")) + "\n")


def _paragraphs_by_id(path: Path) -> dict[str, dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        return {record["id"]: record for line in source if (record := _json_line(line))}


def _json_line(line: str) -> dict[str, Any] | None:
    return json.loads(line) if line.strip() else None


def _reconcile_line(
    result: dict[str, Any],
    paragraphs: dict[str, dict[str, Any]],
    target: Any,
    review: Any,
    counts: dict[str, int],
) -> None:
    from congressional_globe.normalization import apply_edits

    paragraph = paragraphs.get(result.get("custom_id", ""))
    try:
        normalized = _normalized_record(result, paragraph, apply_edits)
    except (KeyError, TypeError, ValueError) as error:
        _write_review(review, result, str(error))
        counts["review"] += 1
    else:
        target.write(json.dumps(normalized, separators=(",", ":")) + "\n")
        counts["accepted"] += 1


def _normalized_record(
    result: dict[str, Any], paragraph: dict[str, Any] | None, apply_edits: Any
) -> dict[str, Any]:
    if paragraph is None:
        raise ValueError("Batch output custom_id does not exist in the supplied paragraph file")
    cleanup = CleanupResult.model_validate_json(_response_text(result))
    normalized = apply_edits(paragraph["text_ocr"], cleanup.edits)
    return {
        **paragraph,
        "text_normalized": normalized,
        "ai_cleanup": cleanup.model_dump(mode="json"),
        "ai_batch_custom_id": result["custom_id"],
    }


def _response_text(result: dict[str, Any]) -> str:
    body = result.get("response", {}).get("body", {})
    if _has_api_error(result, body):
        raise ValueError("Batch response contains an API error")
    return _output_text(body)


def _has_api_error(result: dict[str, Any], body: dict[str, Any]) -> bool:
    return bool(result.get("error") or body.get("error"))


def _output_text(body: dict[str, Any]) -> str:
    texts = (
        content["text"]
        for item in body.get("output", [])
        for content in item.get("content", [])
        if content.get("type") == "output_text" and isinstance(content.get("text"), str)
    )
    try:
        return next(texts)
    except StopIteration as error:
        raise ValueError("Batch response has no Responses API output_text payload") from error


def _write_review(target: Any, result: dict[str, Any], reason: str) -> None:
    target.write(
        json.dumps(
            {"custom_id": result.get("custom_id"), "reason": reason, "batch_result": result},
            separators=(",", ":"),
        )
        + "\n"
    )
