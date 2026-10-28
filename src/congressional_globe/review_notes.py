"""Optional evidence-bound notes without changing immutable review packets."""

import hashlib
import json

from congressional_globe.review_models import ReviewEvidence, ReviewPacket, ReviewQuestion


def evidence_note_id(question_id: str, index: int, item: ReviewEvidence) -> str:
    payload = json.dumps(item.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"evidence-note:{question_id}:{index}:{digest}"


def evidence_note_questions(packet: ReviewPacket) -> dict[str, ReviewQuestion]:
    notes = {
        evidence_note_id(question.id, index, item): ReviewQuestion(
            id=evidence_note_id(question.id, index, item),
            prompt=f"Optional note for {question.id}, item {index + 1}: {item.label}",
            required=False,
        )
        for question in packet.questions
        for index, item in enumerate(question.evidence)
    }
    if set(notes).intersection(question.id for question in packet.questions):
        raise ValueError("question IDs collide with evidence note IDs")
    return notes


def evidence_feedback(packet: ReviewPacket, answers: dict[str, str]) -> list[dict]:
    """Resolve nonblank human notes into source-labelled agent inbox records."""
    feedback = []
    for question in packet.questions:
        feedback.extend(_question_feedback(question, answers))
    return feedback


def _question_feedback(question: ReviewQuestion, answers: dict[str, str]) -> list[dict]:
    feedback = []
    for index, item in enumerate(question.evidence):
        key = evidence_note_id(question.id, index, item)
        comment = answers.get(key, "")
        if comment.strip():
            feedback.append(
                {
                    "note_id": key,
                    "question_id": question.id,
                    "item_number": index + 1,
                    "evidence": item.model_dump(mode="json"),
                    "comment": comment,
                }
            )
    return feedback
