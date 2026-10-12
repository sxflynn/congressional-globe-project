"""Provider-neutral contracts for evidence-linked subject tagging proposals."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
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

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SubjectDefinition(BaseModel):
    """One candidate concept in a versioned, controlled vocabulary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_id: NonBlank
    label: NonBlank
    scope: NonBlank
    inclusion: list[str] = Field(default_factory=list)
    exclusion: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)

    @field_validator("aliases", "inclusion", "exclusion")
    @classmethod
    def reject_blank_terms(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("vocabulary terms must not be blank")
        return values


class SubjectVocabulary(BaseModel):
    """Versioned flat vocabulary with unique subject IDs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: NonBlank
    schema_version: NonBlank = "1"
    status: Literal["draft"] = "draft"
    definitions: list[SubjectDefinition] = Field(min_length=1)

    @property
    def digest(self) -> str:
        """Hash canonical vocabulary content, including its declared version."""
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @model_validator(mode="after")
    def validate_references(self) -> SubjectVocabulary:
        ids = [definition.subject_id for definition in self.definitions]
        if len(ids) != len(set(ids)):
            raise ValueError("subject IDs must be unique")
        return self


class EvidenceParagraph(BaseModel):
    """Text snapshot; frozen models do not deep-freeze nested anchor lists."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    paragraph_id: NonBlank
    item_identifier: NonBlank
    part_number: int = Field(ge=1, le=5)
    scan_leaf: int = Field(ge=0)
    printed_page: PrintedPage
    hocr_page_id: NonBlank | None = None
    hocr_line_ids: list[str] = Field(default_factory=list)
    bbox: BoundingBox | None = None
    text_layer: NonBlank
    text: str = Field(min_length=1)
    text_sha256: str | None = None

    @model_validator(mode="after")
    def validate_hash(self) -> EvidenceParagraph:
        actual = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        if self.text_sha256 is not None and self.text_sha256 != actual:
            raise ValueError("text_sha256 does not match paragraph text")
        object.__setattr__(self, "text_sha256", actual)
        return self


class SubjectEvidence(BaseModel):
    """Half-open Unicode span and complete available source anchors."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    paragraph_id: NonBlank
    item_identifier: NonBlank
    part_number: int = Field(ge=1, le=5)
    scan_leaf: int = Field(ge=0)
    printed_page: PrintedPage
    hocr_page_id: NonBlank | None = None
    hocr_line_ids: list[str] = Field(default_factory=list)
    bbox: BoundingBox | None = None
    text_layer: NonBlank
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_span_order(self) -> SubjectEvidence:
        if self.end_char <= self.start_char:
            raise ValueError("evidence span must be non-empty and half-open")
        return self

    def validate_against(self, paragraphs: list[EvidenceParagraph]) -> None:
        paragraph = _matching_paragraph(self, paragraphs)
        _validate_evidence_anchors(self, paragraph)
        _validate_evidence_quote(self, paragraph)


class SubjectReview(BaseModel):
    """Explicit human adjudication, separate from any model's proposal claims."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reviewer_id: NonBlank
    reviewed_at: datetime
    decision: Literal["in_scope", "mention_only", "unknown", "rejected"]
    note: str = Field(min_length=1)


class SubjectProposal(BaseModel):
    """A pending candidate assignment, never an authority or verified fact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: NonBlank
    subject_id: NonBlank
    vocabulary_version: NonBlank
    disposition: Literal["in_scope", "mention_only", "unknown"]
    evidence: list[SubjectEvidence] = Field(min_length=1)
    basis: str = Field(min_length=1)
    uncertainty: str | None = None
    method: Literal["rule", "model"]
    rule_version: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    schema_version: NonBlank = "1"
    review_status: Literal["pending", "reviewed"] = "pending"
    review: SubjectReview | None = None

    @model_validator(mode="after")
    def validate_review(self) -> SubjectProposal:
        if not _review_state_is_valid(self):
            raise ValueError("reviewed proposals require a human review record")
        if not _method_version_is_valid(
            self.method, self.rule_version, self.model_version, self.prompt_version
        ):
            raise ValueError("proposal method requires its configuration version fields")
        return self


class LooseDiscoveryTag(BaseModel):
    """Uncontrolled discovery cue; must not be used as a subject filter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tag: NonBlank
    evidence: list[SubjectEvidence] = Field(min_length=1)
    basis: str = Field(min_length=1)
    method: Literal["rule", "model"]
    rule_version: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    review_status: Literal["pending"] = "pending"

    @model_validator(mode="after")
    def validate_method_version(self) -> LooseDiscoveryTag:
        if self.method == "model" and (not self.model_version or not self.prompt_version):
            raise ValueError("model discovery tags require model and prompt versions")
        if self.method == "rule" and not self.rule_version:
            raise ValueError("rule discovery tags require a rule version")
        return self


def _matching_paragraph(
    evidence: SubjectEvidence, paragraphs: list[EvidenceParagraph]
) -> EvidenceParagraph:
    matches = [item for item in paragraphs if _same_identity(evidence, item)]
    if not matches:
        raise ValueError(f"unknown evidence source paragraph {evidence.paragraph_id!r}")
    if len(matches) != 1:
        raise ValueError("ambiguous source paragraph identity")
    return matches[0]


def _validate_evidence_anchors(evidence: SubjectEvidence, paragraph: EvidenceParagraph) -> None:
    actual = (evidence.printed_page, evidence.hocr_page_id, evidence.hocr_line_ids, evidence.bbox)
    expected = (
        paragraph.printed_page,
        paragraph.hocr_page_id,
        paragraph.hocr_line_ids,
        paragraph.bbox,
    )
    if actual != expected or evidence.text_sha256 != paragraph.text_sha256:
        raise ValueError("evidence source identity or text hash does not match paragraph")


def _validate_evidence_quote(evidence: SubjectEvidence, paragraph: EvidenceParagraph) -> None:
    if evidence.end_char > len(paragraph.text):
        raise ValueError("evidence span exceeds paragraph text")
    if paragraph.text[evidence.start_char : evidence.end_char] != evidence.quote:
        raise ValueError("evidence quote does not match the referenced text span")


def _same_identity(evidence: SubjectEvidence, paragraph: EvidenceParagraph) -> bool:
    return _source_identity(evidence) == _source_identity(paragraph)


def _source_identity(source: SubjectEvidence | EvidenceParagraph) -> tuple[str, int, int, str, str]:
    return (
        source.item_identifier,
        source.part_number,
        source.scan_leaf,
        source.paragraph_id,
        source.text_layer,
    )


def _review_state_is_valid(proposal: SubjectProposal) -> bool:
    return (proposal.review_status == "reviewed") == (proposal.review is not None)


def _method_version_is_valid(
    method: Literal["rule", "model"],
    rule_version: str | None,
    model_version: str | None,
    prompt_version: str | None,
) -> bool:
    if method == "model":
        return bool(model_version and prompt_version)
    return bool(rule_version)


def validate_subject_proposals(
    proposals: list[SubjectProposal],
    vocabulary: SubjectVocabulary,
    paragraphs: list[EvidenceParagraph],
) -> None:
    """Validate proposal identity, vocabulary binding, and every cited text span."""
    _validate_proposal_ids(proposals)
    _validate_proposal_vocabulary(proposals, vocabulary)
    _validate_source_identities(paragraphs)
    for proposal in proposals:
        _validate_proposal_evidence(proposal, paragraphs)


def _validate_proposal_ids(proposals: list[SubjectProposal]) -> None:
    ids = [proposal.proposal_id for proposal in proposals]
    if len(ids) != len(set(ids)):
        raise ValueError("proposal IDs must be unique")


def _validate_proposal_vocabulary(
    proposals: list[SubjectProposal], vocabulary: SubjectVocabulary
) -> None:
    known = {item.subject_id for item in vocabulary.definitions}
    if any(proposal.subject_id not in known for proposal in proposals):
        raise ValueError("proposal subject ID is absent from the selected vocabulary")
    if any(proposal.vocabulary_version != vocabulary.version for proposal in proposals):
        raise ValueError("proposal vocabulary version does not match selected vocabulary")


def _validate_source_identities(paragraphs: list[EvidenceParagraph]) -> None:
    ids = [_source_identity(paragraph) for paragraph in paragraphs]
    if len(ids) != len(set(ids)):
        raise ValueError("source paragraph identities must be unique")


def _validate_proposal_evidence(
    proposal: SubjectProposal, paragraphs: list[EvidenceParagraph]
) -> None:
    for evidence in proposal.evidence:
        evidence.validate_against(paragraphs)


def reviewed_in_scope_subject_ids(
    proposals: list[SubjectProposal],
    vocabulary: SubjectVocabulary,
    paragraphs: list[EvidenceParagraph],
) -> set[str]:
    """Return reviewed in-scope eligibility after validating all proposals.

    Callers must supply review records from a trusted human-review channel;
    this helper does not establish historical truth or authenticate reviewers.
    """
    validate_subject_proposals(proposals, vocabulary, paragraphs)
    known = {item.subject_id for item in vocabulary.definitions}
    return {
        proposal.subject_id
        for proposal in proposals
        if proposal.subject_id in known
        and proposal.review is not None
        and proposal.review_status == "reviewed"
        and proposal.review.decision == "in_scope"
    }
