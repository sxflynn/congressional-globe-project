"""Glossary help in review explanations, with historical quotations left plain."""

from __future__ import annotations

import hashlib
import html
from pathlib import Path
from typing import Annotated, Literal

import streamlit as st
from pydantic import BaseModel, ConfigDict, Field

from congressional_globe.review_glossary import annotated_html, definitions
from congressional_globe.review_models import GlossaryTerm

SOURCE_PRESENTATION = Path(__file__).resolve().parents[2] / "docs" / "review-source-spans.json"
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class SourceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class SourcePresentation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1]
    source_spans: dict[Digest, list[SourceSpan]]


def _checked_end(span: SourceSpan, cursor: int, length: int) -> int:
    if span.start < cursor or span.end <= span.start or span.end > length:
        raise ValueError("source presentation spans must be ordered, disjoint and within the text")
    return span.end


def _plain_html(text: str) -> str:
    return '<span class="review-source-text">' + html.escape(text) + "</span>"


def _render_parts(
    text: str, spans: list[SourceSpan], entries: dict[str, GlossaryTerm], scope: str
) -> str:
    pieces, cursor = [], 0
    for index, span in enumerate(spans):
        end = _checked_end(span, cursor, len(text))
        pieces.append(annotated_html(text[cursor : span.start], entries, f"{scope}-note-{index}"))
        pieces.append(_plain_html(text[span.start : end]))
        cursor = end
    pieces.append(annotated_html(text[cursor:], entries, f"{scope}-tail"))
    return "".join(pieces)


def evidence_html(text: str, scope: str, custom: list[dict] | None = None) -> str:
    presentation = SourcePresentation.model_validate_json(SOURCE_PRESENTATION.read_text())
    digest = hashlib.sha256(text.encode()).hexdigest()
    spans = presentation.source_spans.get(digest)
    if spans is None:
        return _plain_html(text)
    return _render_parts(text, spans, definitions(custom), scope)


def show_evidence(text: str, scope: str, custom: list[dict] | None = None) -> None:
    content = evidence_html(text, scope, custom).replace("\n", "<br>")
    st.markdown(
        f'<div class="glossary-copy source-card glossary-source">{content}</div>',
        unsafe_allow_html=True,
    )
