"""Hash-bound readable views over unchanged review evidence."""

import hashlib
import html
import json
from pathlib import Path
from typing import Literal

import streamlit as st
from pydantic import BaseModel, ConfigDict, Field

from congressional_globe.review_evidence import (
    SOURCE_PRESENTATION,
    SourcePresentation,
    show_evidence,
)
from congressional_globe.review_glossary import show_text
from congressional_globe.review_models import NonBlank, ReviewEvidence, ReviewPacket
from congressional_globe.review_notes import evidence_note_id, evidence_note_questions
from congressional_globe.review_scans import show_inline_scan
from congressional_globe.scan_models import Sha256

CATALOG = Path(__file__).resolve().parents[2] / "docs/review-readable.json"


class ReadableLine(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    label: str = ""


class ReadableGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    title: NonBlank
    explanation: str = ""
    lines: list[ReadableLine] = Field(min_length=1)


class ReadableEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    label: NonBlank
    explanation: str = ""
    original_body: bool = False
    show_scan: bool = True
    groups: list[ReadableGroup] = Field(default_factory=list)


class ReadableCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal[1]
    evidence: dict[Sha256, ReadableEvidence]


def evidence_digest(item: ReviewEvidence) -> str:
    payload = json.dumps(item.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def readable_view(item: ReviewEvidence) -> ReadableEvidence | None:
    if not CATALOG.exists():
        return None
    catalog = ReadableCatalog.model_validate_json(CATALOG.read_text())
    view = catalog.evidence.get(evidence_digest(item))
    if view is not None:
        _check_lines(item.text, view)
    return view


def _check_lines(text: str, view: ReadableEvidence) -> None:
    if not view.groups:
        return
    presentation = SourcePresentation.model_validate_json(SOURCE_PRESENTATION.read_text())
    spans = presentation.source_spans.get(hashlib.sha256(text.encode()).hexdigest(), [])
    actual = _line_ranges(view)
    expected = [(span.start, span.end) for span in spans]
    if view.original_body or not expected or actual != expected:
        raise ValueError("Readable evidence must preserve every declared source span in order")
    if not _valid_bounds(text, actual):
        raise ValueError("Readable source span is outside its evidence")


def _line_ranges(view: ReadableEvidence) -> list[tuple[int, int]]:
    return [(line.start, line.end) for group in view.groups for line in group.lines]


def _valid_bounds(text: str, ranges: list[tuple[int, int]]) -> bool:
    return all(start < end <= len(text) for start, end in ranges)


def _show_group(group: ReadableGroup, text: str, scope: str, glossary: list[dict]) -> None:
    show_text(group.title, f"{scope}-title", glossary)
    if group.explanation:
        show_text(group.explanation, f"{scope}-explanation", glossary)
    for index, line in enumerate(group.lines):
        _show_line(line, text, f"{scope}-{index}", glossary)


def _show_line(line: ReadableLine, text: str, scope: str, glossary: list[dict]) -> None:
    if line.label:
        show_text(line.label, f"{scope}-label", glossary)
    source = html.escape(text[line.start : line.end])
    st.markdown(
        '<div class="readable-source-row" style="font:1rem/1.6 Georgia,serif;'
        'white-space:pre-wrap;overflow-wrap:anywhere;margin:0 0 .25rem">'
        f'<span class="review-source-text">{source}</span></div>',
        unsafe_allow_html=True,
    )


def _original_details(item: ReviewEvidence, scope: str, glossary: list[dict]) -> None:
    with st.expander("Original evidence and technical details"):
        show_text(str(item.label), f"{scope}-original-label", glossary)
        show_evidence(item.text, f"{scope}-original", glossary)
        if item.url:
            st.link_button("Open cited source", str(item.url))


def show_readable_evidence(item: ReviewEvidence, scope: str, glossary: list[dict]) -> bool:
    try:
        view = readable_view(item)
    except (OSError, ValueError, KeyError):
        return False
    if view is None:
        return False
    _show_view(item, view, scope, glossary)
    return True


def _show_view(
    item: ReviewEvidence, view: ReadableEvidence, scope: str, glossary: list[dict]
) -> None:
    show_text(view.label, f"{scope}-label", glossary)
    if view.explanation:
        show_text(view.explanation, f"{scope}-explanation", glossary)
    if view.original_body:
        show_evidence(item.text, f"{scope}-body", glossary)
    for index, group in enumerate(view.groups):
        _show_group(group, item.text, f"{scope}-group-{index}", glossary)
    _show_scan(item, view.show_scan)
    _original_details(item, scope, glossary)


def readable_answer_labels(packet: ReviewPacket) -> dict[str, str]:
    evidence_note_questions(packet)
    labels = {question.id: question.prompt for question in packet.questions}
    for question in packet.questions:
        labels.update(_note_labels(question.id, question.evidence))
    return labels


def _note_labels(question_id: str, items: list[ReviewEvidence]) -> dict[str, str]:
    labels = {}
    for index, item in enumerate(items):
        try:
            view = readable_view(item)
        except (OSError, ValueError, KeyError):
            view = None
        title = view.label if view else item.label
        labels[evidence_note_id(question_id, index, item)] = f"Your note · {title}"
    return labels


def _show_scan(item: ReviewEvidence, enabled: bool) -> None:
    if enabled and item.url:
        show_inline_scan(str(item.url))
