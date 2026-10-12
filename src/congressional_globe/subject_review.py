"""Import explicit human subject judgments against frozen offline packets."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from congressional_globe.models import BoundingBox, PrintedPage
from congressional_globe.subjects import EvidenceParagraph, SubjectEvidence, SubjectVocabulary

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ReviewManifest(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    review_packets_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    vocabulary_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    vocabulary_version: NonBlank


class ReviewPacketParagraph(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    paragraph_id: NonBlank
    raw_text: str = Field(min_length=1)
    raw_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    hocr_line_ids: list[str] = Field(default_factory=list)
    bbox: BoundingBox | None = None

    @field_validator("raw_text_sha256")
    @classmethod
    def hash_checked(cls, value: str, info) -> str:
        raw_text = info.data.get("raw_text")
        if raw_text is not None and hashlib.sha256(raw_text.encode()).hexdigest() != value:
            raise ValueError("raw_text_sha256 does not match raw_text")
        return value


class ReviewPacket(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    window_id: NonBlank
    item_identifier: NonBlank
    part_number: int = Field(ge=1, le=5)
    scan_leaf: int = Field(ge=0)
    hocr_page_id: NonBlank
    printed_page: PrintedPage
    human_review_status: Literal["pending"]
    human_subject_labels: None
    paragraphs: list[ReviewPacketParagraph] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_paragraph_ids(self) -> ReviewPacket:
        ids = [item.paragraph_id for item in self.paragraphs]
        if len(ids) != len(set(ids)):
            raise ValueError("packet paragraph IDs must be unique within a window")
        return self


class ReviewEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    paragraph_id: NonBlank
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    quote: str = Field(min_length=1)


class OutOfVocabularyTopic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    description: NonBlank
    evidence: list[ReviewEvidence] = Field(min_length=1)


class ReviewedSubject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_id: NonBlank
    decision: Literal["in_scope", "mention_only"]
    evidence: list[ReviewEvidence] = Field(min_length=1)
    note: NonBlank


class WindowDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    window_id: NonBlank
    packet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    vocabulary_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["subjects", "no_subject", "unknown", "out_of_vocabulary"]
    reviewer_id: NonBlank
    reviewed_at: datetime
    note: NonBlank
    subjects: list[ReviewedSubject] = Field(default_factory=list)
    out_of_vocabulary: list[OutOfVocabularyTopic] = Field(default_factory=list)

    @field_validator("reviewed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reviewed_at must include a timezone")
        return value


class ImportedSubject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_id: str
    decision: Literal["in_scope", "mention_only"]
    note: str
    evidence: list[SubjectEvidence]


class ImportedOutOfVocabularyTopic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str
    evidence: list[SubjectEvidence]


class ImportedWindowReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    window_id: str
    packet_sha256: str
    vocabulary_digest: str
    decision: Literal["subjects", "no_subject", "unknown", "out_of_vocabulary"]
    reviewer_id: str
    reviewed_at: datetime
    note: str
    subjects: list[ImportedSubject]
    out_of_vocabulary: list[ImportedOutOfVocabularyTopic]


class SubjectReviewImportReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["validated"] = "validated"
    windows_imported: int = Field(ge=0)
    packet_sha256: str
    vocabulary_digest: str
    reviews_sha256: str
    output_sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _paragraphs(packet: ReviewPacket) -> list[EvidenceParagraph]:
    return [
        EvidenceParagraph(
            paragraph_id=p.paragraph_id,
            item_identifier=packet.item_identifier,
            part_number=packet.part_number,
            scan_leaf=packet.scan_leaf,
            printed_page=packet.printed_page,
            hocr_page_id=packet.hocr_page_id,
            hocr_line_ids=p.hocr_line_ids,
            bbox=p.bbox,
            text_layer="original_ocr",
            text=p.raw_text,
            text_sha256=p.raw_text_sha256,
        )
        for p in packet.paragraphs
    ]


def _evidence(item: ReviewEvidence, paragraphs: list[EvidenceParagraph]) -> SubjectEvidence:
    matches = [p for p in paragraphs if p.paragraph_id == item.paragraph_id]
    if len(matches) != 1:
        raise ValueError(f"evidence paragraph is missing or ambiguous: {item.paragraph_id}")
    paragraph = matches[0]
    if paragraph.text_sha256 is None:
        raise ValueError("packet paragraph is missing its validated text hash")
    evidence = SubjectEvidence(
        paragraph_id=paragraph.paragraph_id,
        item_identifier=paragraph.item_identifier,
        part_number=paragraph.part_number,
        scan_leaf=paragraph.scan_leaf,
        printed_page=paragraph.printed_page,
        hocr_page_id=paragraph.hocr_page_id,
        hocr_line_ids=paragraph.hocr_line_ids,
        bbox=paragraph.bbox,
        text_layer=paragraph.text_layer,
        text_sha256=paragraph.text_sha256,
        start_char=item.start_char,
        end_char=item.end_char,
        quote=item.quote,
    )
    evidence.validate_against(paragraphs)
    return evidence


def _validate_decision(decision: WindowDecision, known_subjects: set[str]) -> None:
    _validate_subject_ids(decision.subjects)
    _validate_outcome(decision)
    _validate_subject_scopes(decision)
    _validate_known_subjects(decision.subjects, known_subjects)


def _validate_subject_ids(subjects: list[ReviewedSubject]) -> None:
    ids = [subject.subject_id for subject in subjects]
    if len(ids) != len(set(ids)):
        raise ValueError("subject decisions must be unique within a window")


def _validate_subject_scopes(decision: WindowDecision) -> None:
    if decision.decision != "subjects" and any(
        subject.decision == "in_scope" for subject in decision.subjects
    ):
        raise ValueError("non-subject window outcomes cannot contain in_scope subject decisions")


def _validate_known_subjects(subjects: list[ReviewedSubject], known_subjects: set[str]) -> None:
    if any(subject.subject_id not in known_subjects for subject in subjects):
        raise ValueError("review subject ID is absent from selected vocabulary")


def _validate_outcome(decision: WindowDecision) -> None:
    if decision.decision == "subjects" and not any(
        item.decision == "in_scope" for item in decision.subjects
    ):
        raise ValueError("subjects decision requires at least one in_scope subject")
    if decision.decision == "out_of_vocabulary" and not decision.out_of_vocabulary:
        raise ValueError("out_of_vocabulary decision requires an evidenced OOV topic")


def _load_frozen_inputs(sample_dir: Path) -> tuple[Path, SubjectVocabulary, str]:
    packet_path = sample_dir / "review_packets.jsonl"
    manifest_path = sample_dir / "manifest.json"
    vocabulary_path = sample_dir / "vocabulary.json"
    manifest = ReviewManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    vocabulary = SubjectVocabulary.model_validate_json(vocabulary_path.read_text(encoding="utf-8"))
    packet_digest = _sha256(packet_path)
    if manifest.review_packets_sha256 != packet_digest:
        raise ValueError("packet digest does not match manifest")
    if manifest.vocabulary_digest != vocabulary.digest:
        raise ValueError("vocabulary digest does not match manifest")
    if manifest.vocabulary_version != vocabulary.version:
        raise ValueError("vocabulary version does not match manifest")
    return packet_path, vocabulary, packet_digest


def _load_packet_map(packet_path: Path) -> dict[str, ReviewPacket]:
    packets = _parse_packets(packet_path)
    packet_by_id = {p.window_id: p for p in packets}
    if len(packet_by_id) != len(packets):
        raise ValueError("packet window IDs must be unique")
    if not packets:
        raise ValueError("review packet set must not be empty")
    return packet_by_id


def _parse_packets(packet_path: Path) -> list[ReviewPacket]:
    packets = []
    for line_number, line in enumerate(packet_path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            packets.append(ReviewPacket.model_validate_json(line))
        except Exception as error:
            raise ValueError(f"invalid review packet at line {line_number}: {error}") from error
    return packets


def _load_decisions(
    decisions_path: Path, packet_by_id: dict[str, ReviewPacket]
) -> dict[str, WindowDecision]:
    decisions = _parse_decisions(decisions_path)
    by_id = {item.window_id: item for item in decisions}
    if len(by_id) != len(decisions):
        raise ValueError("human window decisions must have unique IDs")
    if set(by_id) != set(packet_by_id):
        raise ValueError("human decisions must exhaustively match packet window IDs")
    return by_id


def _parse_decisions(decisions_path: Path) -> list[WindowDecision]:
    decisions: list[WindowDecision] = []
    for line_number, line in enumerate(decisions_path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            decisions.append(WindowDecision.model_validate_json(line))
        except Exception as error:
            raise ValueError(f"invalid human decision at line {line_number}: {error}") from error
    return decisions


def _import_window(
    window_id: str,
    packet: ReviewPacket,
    decision: WindowDecision,
    packet_digest: str,
    vocabulary: SubjectVocabulary,
) -> ImportedWindowReview:
    if decision.packet_sha256 != packet_digest or decision.vocabulary_digest != vocabulary.digest:
        raise ValueError("decision packet or vocabulary digest mismatch")
    known = {item.subject_id for item in vocabulary.definitions}
    _validate_decision(decision, known)
    paragraphs = _paragraphs(packet)
    subjects = _import_subjects(decision, paragraphs)
    oov = [
        ImportedOutOfVocabularyTopic(
            description=topic.description,
            evidence=[_evidence(evidence, paragraphs) for evidence in topic.evidence],
        )
        for topic in decision.out_of_vocabulary
    ]
    return ImportedWindowReview(
        window_id=window_id,
        packet_sha256=packet_digest,
        vocabulary_digest=vocabulary.digest,
        decision=decision.decision,
        reviewer_id=decision.reviewer_id,
        reviewed_at=decision.reviewed_at,
        note=decision.note,
        subjects=subjects,
        out_of_vocabulary=oov,
    )


def _import_subjects(
    decision: WindowDecision, paragraphs: list[EvidenceParagraph]
) -> list[ImportedSubject]:
    return [
        ImportedSubject(
            subject_id=subject.subject_id,
            decision=subject.decision,
            note=subject.note,
            evidence=[_evidence(evidence, paragraphs) for evidence in subject.evidence],
        )
        for subject in decision.subjects
    ]


def import_subject_reviews(
    sample_dir: Path,
    reviews_path: Path,
    output_path: Path,
) -> SubjectReviewImportReport:
    """Import a separate human-authored JSONL file after complete offline validation."""
    packet_path, vocabulary, packet_digest = _load_frozen_inputs(sample_dir)
    packet_by_id = _load_packet_map(packet_path)
    reviews_digest = _sha256(reviews_path)
    by_id = _load_decisions(reviews_path, packet_by_id)
    imported = [
        _import_window(window_id, packet, by_id[window_id], packet_digest, vocabulary)
        for window_id, packet in packet_by_id.items()
    ]
    _require_unchanged_inputs(packet_path, packet_digest, reviews_path, reviews_digest)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(item.model_dump_json() + "\n" for item in imported)
    with output_path.open("x", encoding="utf-8") as stream:
        stream.write(payload)
    return SubjectReviewImportReport(
        windows_imported=len(imported),
        packet_sha256=packet_digest,
        vocabulary_digest=vocabulary.digest,
        reviews_sha256=reviews_digest,
        output_sha256=_sha256(output_path),
    )


def build_subject_review_template(sample_dir: Path, output_path: Path) -> int:
    """Write a separate editable, explicitly pending template for human reviewers."""
    packet_path, vocabulary, packet_digest = _load_frozen_inputs(sample_dir)
    packet_by_id = _load_packet_map(packet_path)
    rows = [
        {
            "window_id": window_id,
            "packet_sha256": packet_digest,
            "vocabulary_digest": vocabulary.digest,
            "decision": "PENDING: subjects | no_subject | unknown | out_of_vocabulary",
            "reviewer_id": "",
            "reviewed_at": "",
            "note": "",
            "subjects": [],
            "out_of_vocabulary": [],
        }
        for window_id in packet_by_id
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as stream:
        stream.write("".join(json.dumps(row) + "\n" for row in rows))
    return len(rows)


def _require_unchanged_inputs(
    packet_path: Path, packet_digest: str, reviews_path: Path, reviews_digest: str
) -> None:
    if _sha256(packet_path) != packet_digest or _sha256(reviews_path) != reviews_digest:
        raise ValueError("packet or reviews changed during import; use frozen input files")
