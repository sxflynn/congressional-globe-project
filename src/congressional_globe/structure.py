"""Conservative page structure and model-routing heuristics."""

from __future__ import annotations

import re
from datetime import date

from congressional_globe.models import PageRecord, ParagraphRecord, WordRecord

_RUNNING_HEADER = re.compile(
    r"(?:THE\s+CONGRESSIONAL\s+GLOBE\.?|INDEX\s+TO\s+(?:THE\s+)?CONGRESSIONAL\s+GLOBE\.?)",
    re.IGNORECASE,
)
_PAGE_NUMBER = re.compile(r"\d{1,5}")
_CHAMBER = re.compile(
    r"(?:IN\s+THE\s+)?(SENATE|HOUSE\s+OF\s+REPRESENTATIVES)"
    r"(?:\s+OF\s+THE\s+UNITED\s+STATES)?[.,:;]?",
    re.IGNORECASE,
)
_DATE = re.compile(
    r"^\s*(?:(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)\s*,?\s*)?"
    r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)"
    r"\s+(\d{1,2})(?:ST|ND|RD|TH)?[,]?\s+(18\d{2})[.,:]?\s*$",
    re.IGNORECASE,
)
_SUSPICIOUS_OCR = re.compile(r"[\\€•▪■□�]")
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def classify_page(page: PageRecord) -> PageRecord:
    """Classify clear running furniture and attach explicit same-page header facts."""
    facts, fact_hints = _page_facts(page)
    paragraphs = [
        _classify_paragraph(page, paragraph, facts, fact_hints) for paragraph in page.paragraphs
    ]
    return page.model_copy(update={"paragraphs": paragraphs})


def needs_model(paragraph: ParagraphRecord) -> bool:
    """Route residual wrap hints and a narrow set of suspicious OCR glyphs."""
    if paragraph.role in {"running_header", "page_number"}:
        return False
    if paragraph.unresolved_wrap_hints:
        return True
    source = paragraph.text_ocr if paragraph.text_normalized is None else paragraph.text_normalized
    return _SUSPICIOUS_OCR.search(source) is not None


def _page_facts(page: PageRecord) -> tuple[dict[str, str], dict[str, str]]:
    facts: dict[str, str] = {}
    hints: dict[str, str] = {}
    if page.image_height_px is None:
        return facts, hints
    for paragraph in page.paragraphs:
        if not _near_top(page, paragraph):
            continue
        _add_date_fact(facts, hints, paragraph)
        _add_chamber_fact(facts, hints, paragraph)
    return facts, hints


def _add_date_fact(
    facts: dict[str, str], hints: dict[str, str], paragraph: ParagraphRecord
) -> None:
    match = _DATE.fullmatch(paragraph.text_ocr)
    if match is None:
        return
    parsed = _parse_date(match)
    if parsed is None:
        hints["date"] = f"Unvalidated date-like header in {paragraph.id}: {match.group(0)}"
        return
    if _weekday_conflicts(match.group(1), parsed):
        hints["date"] = f"Weekday/date mismatch in {paragraph.id}: {match.group(0)}"
        return
    _write_fact(facts, hints, "edition_date", parsed.isoformat(), paragraph, match.group(0))


def _parse_date(match: re.Match[str]) -> date | None:
    try:
        return date(int(match.group(4)), _month_number(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _month_number(month: str) -> int:
    months = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }
    return months[month.lower()]


def _weekday_conflicts(weekday: str | None, value: date) -> bool:
    return weekday is not None and _WEEKDAYS[value.weekday()] != weekday.lower()


def _add_chamber_fact(
    facts: dict[str, str], hints: dict[str, str], paragraph: ParagraphRecord
) -> None:
    text = paragraph.text_ocr.strip()
    match = _CHAMBER.fullmatch(text)
    if match is None:
        return
    chamber = "senate" if match.group(1).lower() == "senate" else "house_of_representatives"
    _write_fact(facts, hints, "chamber", chamber, paragraph, match.group(0))


def _write_fact(
    facts: dict[str, str],
    hints: dict[str, str],
    key: str,
    value: str,
    paragraph: ParagraphRecord,
    source_text: str,
) -> None:
    if key in hints:
        return
    if key in facts and facts[key] != value:
        for suffix in ("", "_source_paragraph_id", "_source_text"):
            facts.pop(f"{key}{suffix}", None)
        hints[key] = f"Conflicting explicit {key} headers on this page"
        return
    facts[key] = value
    facts[f"{key}_source_paragraph_id"] = paragraph.id
    facts[f"{key}_source_text"] = source_text


def _classify_paragraph(
    page: PageRecord,
    paragraph: ParagraphRecord,
    facts: dict[str, str],
    page_hints: dict[str, str],
) -> ParagraphRecord:
    role, source = _paragraph_role(page, paragraph)
    context = dict(paragraph.context)
    _clear_derived_facts(context)
    context.update(facts)
    for kind, hint in page_hints.items():
        _add_review_hint(context, f"{kind}: {hint}")
    low_confidence = _low_confidence_hint(paragraph) if role == "body" else None
    if low_confidence:
        _add_review_hint(context, low_confidence)
    return paragraph.model_copy(update={"role": role, "role_source": source, "context": context})


def _clear_derived_facts(context: dict[str, str]) -> None:
    for key in (
        "edition_date",
        "edition_date_source_paragraph_id",
        "edition_date_source_text",
        "chamber",
        "chamber_source_paragraph_id",
        "chamber_source_text",
    ):
        context.pop(key, None)


def _paragraph_role(page: PageRecord, paragraph: ParagraphRecord) -> tuple[str, str | None]:
    if not _valid_bbox(page, paragraph) or not _near_edge(page, paragraph):
        return "body", None
    text = paragraph.text_ocr.strip()
    if _is_running_header(text):
        return "running_header", "exact_header_pattern_and_edge_geometry"
    if _matches_printed_page(page, text):
        return "page_number", "printed_page_match_and_edge_geometry"
    return "body", None


def _is_running_header(text: str) -> bool:
    return _RUNNING_HEADER.fullmatch(text) is not None


def _valid_bbox(page: PageRecord, paragraph: ParagraphRecord) -> bool:
    bbox = paragraph.bbox
    if bbox is None or page.image_height_px is None or page.image_width_px is None:
        return False
    return (
        bbox.right > bbox.left
        and bbox.bottom > bbox.top
        and bbox.right <= page.image_width_px
        and bbox.bottom <= page.image_height_px
    )


def _near_edge(page: PageRecord, paragraph: ParagraphRecord) -> bool:
    bbox = paragraph.bbox
    height = page.image_height_px
    if bbox is None or height is None:
        return False
    return bbox.top <= height * 0.08 or bbox.bottom >= height * 0.92


def _near_top(page: PageRecord, paragraph: ParagraphRecord) -> bool:
    bbox = paragraph.bbox
    height = page.image_height_px
    return (
        _valid_bbox(page, paragraph)
        and bbox is not None
        and height is not None
        and bbox.top <= height * 0.16
    )


def _matches_printed_page(page: PageRecord, text: str) -> bool:
    if _PAGE_NUMBER.fullmatch(text) is None:
        return False
    return text in {page.printed_page.detected, page.printed_page.inferred}


def _low_confidence_hint(paragraph: ParagraphRecord) -> str | None:
    low_count = sum(_is_low_confidence(word) for line in paragraph.lines for word in line.words)
    if low_count >= 3:
        return f"low OCR word confidence in {paragraph.id}; verify against scan"
    return None


def _is_low_confidence(word: WordRecord) -> bool:
    return word.confidence is not None and word.confidence < 20


def _add_review_hint(context: dict[str, str], hint: str) -> None:
    previous = context.get("review_hint")
    context["review_hint"] = f"{previous}; {hint}" if previous else hint
