"""Typed contracts for the local, human-operated review desk."""

from __future__ import annotations

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    model_serializer,
    model_validator,
)

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ReviewEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: NonBlank
    text: str = Field(min_length=1)
    url: HttpUrl | None = None


class ReviewQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: NonBlank
    prompt: NonBlank
    options: list[NonBlank] = Field(default_factory=list)
    required: bool = True
    evidence: list[ReviewEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_options(self) -> ReviewQuestion:
        if len(self.options) != len(set(self.options)):
            raise ValueError("question options must be unique")
        return self


class GlossaryTerm(BaseModel):
    """Plain-language explanation, with literal alternative spellings to annotate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    term: NonBlank
    definition: NonBlank
    aliases: list[NonBlank] = Field(default_factory=list)


class ReviewPacket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: NonBlank
    version: int = Field(ge=1)
    title: NonBlank
    instructions: NonBlank
    blind: bool = False
    questions: list[ReviewQuestion] = Field(min_length=1)
    glossary: list[GlossaryTerm] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def compatible_payload(self, handler):
        payload = handler(self)
        if not self.glossary:
            payload.pop("glossary", None)
        return payload

    @model_validator(mode="after")
    def unique_glossary_terms(self) -> ReviewPacket:
        names = [
            name.casefold() for entry in self.glossary for name in [entry.term, *entry.aliases]
        ]
        if len(names) != len(set(names)):
            raise ValueError("glossary terms and aliases must be unique")
        return self

    @model_validator(mode="after")
    def unique_question_ids(self) -> ReviewPacket:
        ids = [question.id for question in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("question IDs must be unique within a packet")
        return self


class ReviewSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reviewer: NonBlank
    answers: dict[NonBlank, str]
    notes: str | None = None
