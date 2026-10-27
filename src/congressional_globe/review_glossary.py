"""Escaped, inline native popovers; definition taps never submit a Streamlit form."""

from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path

import streamlit as st
from pydantic import BaseModel, ConfigDict

from congressional_globe.review_models import GlossaryTerm

CATALOG = Path(__file__).resolve().parents[2] / "docs" / "review-glossary.json"


class GlossaryCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    terms: list[GlossaryTerm]


def definitions(custom: list[dict] | None = None) -> dict[str, GlossaryTerm]:
    catalog = GlossaryCatalog.model_validate_json(CATALOG.read_text())
    entries = [*catalog.terms, *(GlossaryTerm.model_validate(term) for term in custom or [])]
    return {name.casefold(): entry for entry in entries for name in [entry.term, *entry.aliases]}


def _button(label: str, entry: GlossaryTerm, identity: str) -> tuple[str, str]:
    target = "gloss-" + hashlib.sha256(identity.encode()).hexdigest()[:20]
    term, definition = html.escape(entry.term), html.escape(entry.definition)
    trigger = (
        f'<button type="button" class="glossary-term" popovertarget="{target}" '
        f'aria-label="Define: {html.escape(label, quote=True)}">{html.escape(label)}</button>'
    )
    popup = (
        f'<div id="{target}" popover="auto" class="glossary-popup" '
        f'role="dialog" aria-label="{term}"><strong>{term}</strong>'
        f'<p>{definition}</p><button type="button" popovertarget="{target}" '
        'popovertargetaction="hide">Close definition</button></div>'
    )
    return trigger, popup


def annotated_html(text: str, entries: dict[str, GlossaryTerm], scope: str) -> str:
    if not entries:
        return html.escape(text)
    alternatives = "|".join(re.escape(term) for term in sorted(entries, key=len, reverse=True))
    pattern = re.compile(r"(?<!\w)(?:" + alternatives + r")(?!\w)", re.IGNORECASE)
    pieces, popups, cursor = [], [], 0
    for match in pattern.finditer(text):
        trigger, popup = _button(
            match.group(), entries[match.group().casefold()], f"{scope}:{match.start()}"
        )
        pieces.extend([html.escape(text[cursor : match.start()]), trigger])
        popups.append(popup)
        cursor = match.end()
    return "".join([*pieces, html.escape(text[cursor:]), *popups])


def show_text(
    text: str, scope: str, custom: list[dict] | None = None, *, source: bool = False
) -> None:
    content = html.escape(text) if source else annotated_html(text, definitions(custom), scope)
    card = " source-card glossary-source" if source else ""
    st.markdown(f'<div class="glossary-copy{card}">{content}</div>', unsafe_allow_html=True)


def show_option_definitions(question: dict, scope: str, custom: list[dict] | None) -> None:
    entries = definitions(custom)
    options = "\n".join(question.get("options", []))
    found = [
        entry
        for name, entry in entries.items()
        if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", options, re.IGNORECASE)
    ]
    terms = list(dict.fromkeys(entry.term for entry in found))
    if terms:
        show_text("Answer terms: " + " · ".join(terms), scope, custom)


def styles() -> None:
    st.markdown(
        """
<style>
.glossary-source {font:1rem/1.7 Georgia,serif}
.glossary-copy {white-space:pre-wrap;overflow-wrap:anywhere;margin-bottom:1rem}
button.glossary-term {font:inherit;color:inherit;background:transparent;border:0;
 padding:0;cursor:pointer;text-decoration:underline dotted;text-underline-offset:.2em;
 border-radius:2px;display:inline}
button.glossary-term:hover {text-decoration-style:solid}
button.glossary-term:focus-visible {outline:2px solid #9b7c4a;outline-offset:3px}
.glossary-popup {box-sizing:border-box;width:min(24rem,calc(100vw - 2rem));
 max-height:70vh;overflow:auto;padding:1.2rem;border:1px solid #9b7c4a;
 border-radius:.5rem;background:#faf6ed;color:#30291f;
 box-shadow:0 8px 32px #0003;white-space:normal;font:1rem/1.55 Georgia,serif}
.glossary-popup::backdrop {background:#0002}
.glossary-popup p {margin:.6rem 0 1rem}
.glossary-popup button {font:inherit;padding:.4rem .7rem;border:1px solid #9b7c4a;
 border-radius:.25rem;background:transparent;color:inherit;cursor:pointer}
@media(prefers-color-scheme:dark){.glossary-popup {background:#1e1b17;color:#f1e7d4}}
</style>
""",
        unsafe_allow_html=True,
    )
