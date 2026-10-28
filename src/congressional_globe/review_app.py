"""Local Streamlit interface for durable human review packets."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Any

import streamlit as st

from congressional_globe.review_evidence import show_evidence
from congressional_globe.review_glossary import (
    annotated_html,
    definitions,
    show_option_definitions,
    show_text,
    styles,
)
from congressional_globe.review_models import ReviewEvidence, ReviewPacket
from congressional_globe.review_notes import evidence_note_id, evidence_note_questions
from congressional_globe.review_scans import show_inline_scan
from congressional_globe.review_store import ReviewStore


def _database_path() -> Path:
    configured = os.environ.get("GLOBE_REVIEW_DATABASE")
    return Path(configured) if configured else Path("artifacts/human-review/reviews.sqlite")


def _value(record: Any, key: str, default: Any = None) -> Any:
    return record.get(key, default) if isinstance(record, dict) else getattr(record, key, default)


def _answer_history(
    store: ReviewStore, packet_id: str, version: int, reviewer: str
) -> dict[str, str]:
    records = [
        row
        for row in store.submissions()
        if row["packet_id"] == packet_id
        and row["version"] == version
        and row["reviewer"] == reviewer
    ]
    return max(records, key=lambda row: row["revision"])["answers"] if records else {}


def _safe_url(value: Any) -> str | None:
    url = str(value or "")
    return url if url.startswith(("https://", "http://")) else None


def _packet_label(packet: Any) -> str:
    packet_id = str(_value(packet, "id"))
    prefix = "DEMO · " if packet_id.upper().startswith("DEMO") else ""
    return f"{prefix}{packet_id} · v{_value(packet, 'version')} · {_value(packet, 'title')}"


def _widget_prefix(packet_id: str, version: int, reviewer: str, revision_id: str) -> str:
    source = f"{packet_id}:{version}:{reviewer}:{revision_id}"
    return hashlib.sha256(source.encode()).hexdigest()[:12]


def _evidence(question: Any, scope: str, glossary: list[dict], baseline: dict) -> tuple[dict, bool]:
    notes, save = {}, False
    for index, item in enumerate(_value(question, "evidence", [])):
        show_text(str(_value(item, "label", "Evidence")), f"{scope}-label-{index}", glossary)
        show_evidence(str(_value(item, "text", "")), f"{scope}-evidence-{index}", glossary)
        url = _safe_url(_value(item, "url"))
        if url:
            show_inline_scan(url)
        note_id = evidence_note_id(
            str(_value(question, "id")), index, ReviewEvidence.model_validate(item)
        )
        notes[note_id] = _evidence_note(note_id, scope, index, glossary, baseline)
        clicked = st.form_submit_button("Save draft here", key=f"save-{scope}-{index}")
        save = clicked or save
    return notes, save


def _evidence_note(
    note_id: str, scope: str, index: int, glossary: list[dict], baseline: dict
) -> str:
    show_text(
        "Optional note for this example. Save draft here keeps all current answers; "
        "Submit review sends the finished review.",
        f"{scope}-note-help-{index}",
        glossary,
    )
    return st.text_area(
        f"Your note on item {index + 1} above (optional)",
        value=baseline.get(note_id, ""),
        key=f"answer-{scope}-{note_id}",
    )


def _answer_widget(
    question: Any, baseline: dict, key_prefix: str, glossary: list[dict]
) -> tuple[dict, bool]:
    question_id = str(_value(question, "id"))
    label = str(_value(question, "prompt"))
    required = bool(_value(question, "required", True))
    scope = f"{key_prefix}-{question_id}"
    show_text(label + (" *" if required else ""), scope, glossary)
    notes, save = _evidence(question, scope, glossary, baseline)
    show_option_definitions(question, f"{scope}-options", glossary)
    notes[question_id] = _main_answer(question, baseline.get(question_id, ""), key_prefix)
    return notes, save


def _main_answer(question: Any, current: str, key_prefix: str) -> str:
    question_id = str(_value(question, "id"))
    options = _value(question, "options", []) or []
    key = f"answer-{key_prefix}-{question_id}"
    if options:
        choices = ["", *list(options)]
        index = choices.index(current) if current in choices else 0
        return st.selectbox("Choose an answer", choices, index=index, key=key, filter_mode=None)
    return st.text_area("Your answer", value=current, key=key)


def _save_result(
    store: ReviewStore,
    packet: Any,
    reviewer: str,
    answers: dict[str, str],
    submit: bool,
    revision: bool = False,
) -> None:
    packet_id, version = _value(packet, "id"), _value(packet, "version")
    if not reviewer.strip():
        st.error("Enter your name or reviewer ID before saving or submitting.")
        return
    try:
        if not submit:
            store.save_draft(packet_id, version, reviewer, answers)
            st.success("Draft saved. You can return to it later.")
            return
        result = store.submit(packet_id, version, reviewer, answers)
        st.success(_submission_message(result))
        if revision:
            st.session_state.pop("revision_target", None)
    except (ValueError, KeyError, RuntimeError, sqlite3.Error) as exc:
        st.error(str(exc))


def _submission_message(result: dict[str, Any]) -> str:
    state = "Applied" if result["applied"] else "Submitted — awaiting agent"
    return f"{state}. Receipt: {result['submission_id']} · revision {result['revision']}"


def _show_packet(
    packet: Any,
    store: ReviewStore,
    prior: dict[str, str] | None = None,
    revision: bool = False,
    revision_id: str = "",
    reviewer_default: str = "",
) -> None:
    packet_id, version = _value(packet, "id"), _value(packet, "version")
    glossary = _value(packet, "glossary", [])
    _packet_heading(str(_value(packet, "title")), f"{packet_id}-{version}-title", glossary)
    show_text(
        f"{packet_id} · version {version}" + (" · revision" if revision else ""),
        f"{packet_id}-{version}-version",
        glossary,
    )
    show_text(str(_value(packet, "instructions")), f"{packet_id}-{version}-instructions", glossary)
    st.caption("Tap a dotted-underlined term for its definition. Close it to keep reading.")
    reviewer = _reviewer(packet_id, version, store, revision_id, revision, reviewer_default)
    if reviewer is None:
        return
    baseline = _baseline(store, packet_id, version, reviewer, prior)
    key_prefix = _widget_prefix(packet_id, version, reviewer, revision_id)
    questions = _value(packet, "questions", [])
    answers, save, submit = _review_form(packet, questions, baseline, key_prefix, revision)
    if save or submit:
        _save_result(store, packet, reviewer, answers, submit, revision)


def _packet_heading(text: str, scope: str, glossary: list[dict]) -> None:
    content = annotated_html(text, definitions(glossary), scope)
    st.markdown(
        '<div role="heading" aria-level="3" class="glossary-copy" '
        'style="font-size:1.4rem;font-weight:600;line-height:1.35">'
        f"{content}</div>",
        unsafe_allow_html=True,
    )


def _reviewer(
    packet_id: str,
    version: int,
    store: ReviewStore,
    revision_id: str,
    revision: bool,
    reviewer_default: str,
) -> str | None:
    reviewer_key = f"revision-reviewer-{revision_id}" if revision else "reviewer"
    reviewer_value = st.text_input(
        "Your name or reviewer ID",
        value=st.session_state.get(reviewer_key, "") or reviewer_default,
        key=reviewer_key,
        disabled=revision,
    )
    reviewer = reviewer_default.strip() if revision else reviewer_value.strip()
    try:
        if reviewer.strip():
            store.get_draft(packet_id, version, reviewer)
    except (ValueError, KeyError) as exc:
        st.error(f"This packet version is no longer available for editing: {exc}")
        return None
    return reviewer


def _baseline(
    store: ReviewStore,
    packet_id: str,
    version: int,
    reviewer: str,
    prior: dict[str, str] | None,
) -> dict[str, str]:
    draft = store.get_draft(packet_id, version, reviewer) if reviewer.strip() else None
    saved = _value(draft, "answers", {}) or {}
    if saved:
        return {**(prior or {}), **saved}
    return prior or _answer_history(store, packet_id, version, reviewer)


def _review_form(
    packet: Any,
    questions: list[Any],
    baseline: dict[str, str],
    key_prefix: str,
    revision: bool,
) -> tuple[dict[str, str], bool, bool]:
    packet_id, version = _value(packet, "id"), _value(packet, "version")
    with st.form(f"review-{packet_id}-{version}-{key_prefix}"):
        answers, nearby_save = {}, False
        for question in questions:
            values, clicked = _answer_widget(
                question, baseline, key_prefix, _value(packet, "glossary", [])
            )
            answers.update(values)
            nearby_save = clicked or nearby_save
        save_label = "Save revision draft" if revision else "Save draft"
        submit_label = "Submit revision" if revision else "Submit review"
        save = st.form_submit_button(save_label)
        submit = st.form_submit_button(submit_label)
    return answers, save or nearby_save, submit


def _show_submission(submission: Any, packet: dict) -> None:
    state = "Applied" if _value(submission, "applied", False) else "Submitted — awaiting agent"
    receipt = _value(submission, "submission_id", "")
    st.caption(f"{state} · receipt {receipt} · revision {_value(submission, 'revision', '?')}")
    st.write(f"Reviewer: {_value(submission, 'reviewer', 'Unknown')}")
    _show_answers(submission, packet)
    reference = _value(submission, "applied_reference")
    if reference:
        st.info(f"Applied: {reference}")


def _show_answers(submission: Any, packet: dict) -> None:
    payload = dict(packet)
    payload.pop("packet_sha256", None)
    notes = evidence_note_questions(ReviewPacket.model_validate(payload))
    for question_id, answer in (_value(submission, "answers", {}) or {}).items():
        if not answer.strip():
            continue
        label = notes[question_id].prompt if question_id in notes else question_id
        show_text(label, f"answer-label-{question_id}")
        st.text(answer)


def _legacy_history() -> None:
    st.markdown("### Completed paper reviews")
    st.caption("Read-only records from before this desk. They are not new web submissions.")
    with st.expander("HR-005-v1 · Wade speaker attribution"):
        st.write("The human confirmed the specific attribution to Mr. Wade in this context.")
        _legacy_downloads("HR-005-v1")
    with st.expander("HR-008-v1 · Three topic-tag examples"):
        st.write(
            "Voting rights and public employee compensation were accepted in these examples; "
            "the military inference was rejected. Cross-page speaker context should be retained."
        )
        _legacy_downloads("HR-008-v1")


def _legacy_downloads(review_id: str) -> None:
    archive = Path(__file__).resolve().parents[2] / "docs" / "archive" / "human-review" / review_id
    for filename in ("original.md", "receipt.json"):
        path = archive / filename
        if path.is_file():
            st.download_button(
                f"Download {filename}",
                path.read_bytes(),
                file_name=f"{review_id}-{filename}",
                key=f"download-{review_id}-{filename}",
            )


def _revision_view(store: ReviewStore, target: dict[str, Any]) -> None:
    _show_revision_target(store, target)
    if st.button("Cancel revision"):
        st.session_state.pop("revision_target", None)
        st.rerun()


def _show_revision_target(store: ReviewStore, target: dict[str, Any]) -> None:
    packet = store.get_packet(target["packet_id"], target["version"])
    if packet is None:
        st.error("The packet for this submission is no longer available.")
        return
    if not _is_latest_packet(store, target):
        st.error("This review belongs to an older packet version and cannot be revised.")
        return
    _show_packet(
        packet,
        store,
        target["answers"],
        revision=True,
        revision_id=target["submission_id"],
        reviewer_default=target["reviewer"],
    )


def _is_latest_packet(store: ReviewStore, target: dict[str, Any]) -> bool:
    latest = store.get_packet(target["packet_id"])
    return latest is not None and latest["version"] == target["version"]


def _submission_views(store: ReviewStore, submissions: list[dict[str, Any]], section: str) -> None:
    visible = _visible_submissions(submissions, section)
    if _render_submissions(store, visible):
        return
    if section == "History":
        _legacy_history()
    elif not visible:
        st.info("No submitted reviews in this view.")


def _render_submissions(store: ReviewStore, visible: list[dict[str, Any]]) -> bool:
    return any(_submission_card(store, row) for row in visible)


def _visible_submissions(submissions: list[dict[str, Any]], section: str) -> list[dict[str, Any]]:
    return [
        row
        for row in submissions
        if (row["applied"] or row.get("superseded", False)) == (section == "History")
    ]


def _submission_card(store: ReviewStore, row: dict[str, Any]) -> bool:
    suffix = " · superseded" if row.get("superseded", False) else ""
    title = f"{row['packet_id']} · v{row['version']} · revision {row['revision']}{suffix}"
    with st.expander(title):
        _show_submission(row, store.get_packet(row["packet_id"], row["version"]) or {})
        revise = st.button("Revise this response", key=f"revise-{row['submission_id']}")
    if revise:
        st.session_state["revision_target"] = row
        _revision_view(store, row)
    return revise


def _pending_view(
    store: ReviewStore, packets: list[dict[str, Any]], submissions: list[dict[str, Any]]
) -> None:
    submitted = {(row["packet_id"], row["version"]) for row in submissions}
    available = [packet for packet in packets if (packet["id"], packet["version"]) not in submitted]
    if not available:
        st.info("No pending reviews.")
        return
    packet = st.selectbox("Review set", available, format_func=_packet_label)
    _show_packet(packet, store)


def _store_data() -> tuple[ReviewStore, list[dict[str, Any]], list[dict[str, Any]]] | None:
    try:
        store = ReviewStore(_database_path())
        return store, store.packets(), store.submissions()
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        st.error(f"The review desk could not open its database: {exc}")
        return None


def _masthead() -> None:
    st.markdown(
        """
        <style>
        /* The local review desk needs no floating Streamlit deployment toolbar. */
        [data-testid="stHeader"]{display:none}
        [data-testid="stMainBlockContainer"]{padding-top:2rem}
        .globe-masthead{padding:1.2rem .25rem 1rem;margin:0 0 1.5rem;
          text-align:center;border-top:4px double currentColor;
          border-bottom:4px double currentColor}
        .globe-masthead h1{font-family:Georgia,'Times New Roman',serif;
          font-size:clamp(2rem,7vw,3.3rem);font-weight:700;line-height:1.1;
          letter-spacing:-.025em;margin:.35rem 0;padding:0}
        .globe-masthead .globe-brand{font-family:Georgia,'Times New Roman',serif;
          font-size:1rem;font-variant:small-caps;letter-spacing:.12em;margin:.4rem 0}
        .globe-masthead .globe-edition{font-size:.75rem;letter-spacing:.05em;
          opacity:.75;margin:.7rem 0 0}
        .globe-scan{margin:.5rem 0 1rem}
        .globe-scan summary{cursor:pointer;padding:.75rem .25rem;min-height:44px}
        .source-card{border-left:3px solid #9b7c4a;padding:.8rem 1rem;
          background:rgba(124,99,58,.055);color:inherit}
        .source-card pre{white-space:pre-wrap;overflow-wrap:anywhere;
          font:1rem/1.7 Georgia,'Times New Roman',serif;margin:0}
        @media(prefers-color-scheme:dark){.source-card{
          border-color:#b59662;background:rgba(213,188,139,.06)}}
        </style>
        <header class="globe-masthead" aria-label="Congressional Globe Digital History Project">
          <h1>The Congressional Globe</h1>
          <p class="globe-brand">Digital History Project</p>
          <p class="globe-edition">39th Congress &middot; First Session &middot; Primary Sources</p>
        </header>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Congressional Globe · Human review", layout="centered")
    _masthead()
    styles()
    st.subheader("Human review desk")
    data = _store_data()
    if data is None:
        return
    store, packets, submissions = data
    section = st.radio(
        "View",
        ["Pending", "Submitted", "History"],
        horizontal=True,
    )
    target = st.session_state.get("revision_target")
    if target:
        _revision_view(store, target)
    elif section == "Pending":
        _pending_view(store, packets, submissions)
    else:
        _submission_views(store, submissions, section)


if __name__ == "__main__":
    main()
