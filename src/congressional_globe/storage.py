"""Typed SQLite persistence for resumable cleanup runs."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime
from hashlib import sha256
from itertools import islice
from pathlib import Path
from typing import Any

from sqlalchemy import Integer, String, Text, create_engine, select
from sqlalchemy import text as sql_text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class CleanupJob(Base):
    __tablename__ = "cleanup_jobs"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    paragraph_id: Mapped[str] = mapped_column(String(128), index=True)
    identity: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_json: Mapped[str] = mapped_column(Text)
    source_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    backend: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(String(40), default=lambda: _now())


def create_run(
    database_path: Path,
    run_id: str,
    paragraphs_path: Path,
    limit: int | None = None,
    scan_leaf: int | None = None,
    paragraph_ids: set[str] | None = None,
) -> int:
    engine = _engine(database_path)
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        _ensure_empty_run(session, run_id)
        count = _add_jobs(session, run_id, paragraphs_path, limit, scan_leaf, paragraph_ids)
    return count


def claim_next(database_path: Path, run_id: str, backend: str, model: str) -> CleanupJob | None:
    engine = _engine(database_path)
    with Session(engine) as session, session.begin():
        job = session.scalars(_pending_jobs(run_id)).first()
        if job is None:
            return None
        job.status = "claimed"
        job.attempts += 1
        job.backend = backend
        job.model = model
        job.updated_at = _now()
        session.flush()
        session.expunge(job)
        return job


def release_claimed(database_path: Path, run_id: str) -> int:
    engine = _engine(database_path)
    with Session(engine) as session, session.begin():
        jobs = session.scalars(
            select(CleanupJob).where(CleanupJob.run_id == run_id, CleanupJob.status == "claimed")
        ).all()
        for job in jobs:
            job.status = "pending"
            job.updated_at = _now()
        return len(jobs)


def complete_job(
    database_path: Path,
    job_id: str,
    result: dict[str, Any],
    duration_ms: int,
    raw_response: str | None = None,
    usage: dict[str, int] | None = None,
) -> None:
    if result.get("cleanup", {}).get("needs_image_review") is True:
        raise ValueError("jobs requesting image review cannot be completed")
    _update_job(
        database_path,
        job_id,
        "completed",
        json.dumps(result),
        None,
        duration_ms,
        raw_response,
        usage,
    )


def review_job(database_path: Path, job_id: str, error: str, duration_ms: int) -> None:
    _update_job(database_path, job_id, "review", None, error, duration_ms)


def review_job_result(
    database_path: Path,
    job_id: str,
    error: str,
    duration_ms: int,
    raw_response: str,
    usage: dict[str, int],
) -> None:
    _update_job(database_path, job_id, "review", None, error, duration_ms, raw_response, usage)


def retry_job(database_path: Path, job_id: str, error: str, duration_ms: int) -> None:
    _update_job(database_path, job_id, "pending", None, error, duration_ms)


def retry_review_jobs(database_path: Path, run_id: str) -> int:
    engine = _engine(database_path)
    with Session(engine) as session, session.begin():
        jobs = session.scalars(
            select(CleanupJob).where(CleanupJob.run_id == run_id, CleanupJob.status == "review")
        ).all()
        for job in jobs:
            job.status = "pending"
            job.updated_at = _now()
        return len(jobs)


def progress(database_path: Path, run_id: str) -> dict[str, int]:
    engine = _engine(database_path)
    with Session(engine) as session:
        statuses = session.scalars(
            select(CleanupJob.status).where(CleanupJob.run_id == run_id)
        ).all()
    counts = Counter(statuses)
    counts["total"] = sum(counts.values())
    return dict(counts)


def run_summary(database_path: Path, run_id: str) -> dict[str, int | float | None]:
    engine = _engine(database_path)
    with Session(engine) as session:
        statuses = session.scalars(
            select(CleanupJob.status).where(CleanupJob.run_id == run_id)
        ).all()
        durations = session.scalars(
            select(CleanupJob.duration_ms).where(
                CleanupJob.run_id == run_id, CleanupJob.status == "completed"
            )
        ).all()
    counts = Counter(statuses)
    total = sum(counts.values())
    completed = counts["completed"]
    remaining = total - completed
    average_ms = (
        sum(duration for duration in durations if duration is not None) / completed
        if completed
        else None
    )
    return {
        "completed": completed,
        "pending": counts["pending"],
        "claimed": counts["claimed"],
        "review": counts["review"],
        "total": total,
        "remaining": remaining,
        "percent_complete": round((completed / total) * 100, 2) if total else 0,
        "average_completed_seconds": round(average_ms / 1000, 2)
        if average_ms is not None
        else None,
        "estimated_remaining_hours": round((average_ms * remaining) / 3_600_000, 2)
        if average_ms is not None
        else None,
    }


def job_by_id(database_path: Path, run_id: str, paragraph_id: str) -> CleanupJob | None:
    engine = _engine(database_path)
    with Session(engine) as session:
        job = session.scalar(
            select(CleanupJob).where(
                CleanupJob.run_id == run_id, CleanupJob.paragraph_id == paragraph_id
            )
        )
        if job is not None:
            session.expunge(job)
        return job


def completed_jobs(database_path: Path, run_id: str) -> list[CleanupJob]:
    return _jobs(database_path, run_id, "completed")


def jobs_for_run(database_path: Path, run_id: str) -> list[CleanupJob]:
    engine = _engine(database_path)
    with Session(engine) as session:
        jobs = session.scalars(
            select(CleanupJob).where(CleanupJob.run_id == run_id).order_by(CleanupJob.id)
        ).all()
        for job in jobs:
            session.expunge(job)
        return list(jobs)


def _jobs(database_path: Path, run_id: str, status: str) -> list[CleanupJob]:
    engine = _engine(database_path)
    with Session(engine) as session:
        jobs = session.scalars(
            select(CleanupJob).where(CleanupJob.run_id == run_id, CleanupJob.status == status)
        ).all()
        for job in jobs:
            session.expunge(job)
        return list(jobs)


def _engine(database_path: Path):
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"timeout": 30})
    Base.metadata.create_all(engine)
    _migrate_schema(engine)
    return engine


def _migrate_schema(engine: Any) -> None:
    additions = {
        "identity": "VARCHAR(512)",
        "input_hash": "VARCHAR(64)",
        "usage_json": "TEXT",
        "raw_response": "TEXT",
    }
    with closing(engine.connect()) as connection, connection.begin():
        columns = {
            row[1] for row in connection.execute(sql_text("PRAGMA table_info(cleanup_jobs)"))
        }
        for name, kind in additions.items():
            if name not in columns:
                connection.execute(sql_text(f"ALTER TABLE cleanup_jobs ADD COLUMN {name} {kind}"))


def _ensure_empty_run(session: Session, run_id: str) -> None:
    existing = session.scalar(select(CleanupJob.id).where(CleanupJob.run_id == run_id))
    if existing is not None:
        raise ValueError(f"Run already exists: {run_id}")


def _add_jobs(
    session: Session,
    run_id: str,
    paragraphs_path: Path,
    limit: int | None,
    scan_leaf: int | None,
    paragraph_ids: set[str] | None,
) -> int:
    count = 0
    for payload in _limited(_matching_payloads(paragraphs_path, scan_leaf, paragraph_ids), limit):
        session.add(_job_from_payload(run_id, payload))
        count += 1
    return count


def _matching_payloads(
    path: Path, scan_leaf: int | None, paragraph_ids: set[str] | None
) -> Iterator[dict[str, Any]]:
    return (
        payload
        for payload in _payloads(path)
        if _matches_leaf(payload, scan_leaf) and _matches_id(payload, paragraph_ids)
    )


def _payloads(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        for line in source:
            if line.strip():
                yield json.loads(line)


def _matches_leaf(payload: dict[str, Any], scan_leaf: int | None) -> bool:
    return scan_leaf is None or payload["scan_leaf"] == scan_leaf


def _matches_id(payload: dict[str, Any], paragraph_ids: set[str] | None) -> bool:
    return paragraph_ids is None or payload["id"] in paragraph_ids


def _limited(records: Iterator[dict[str, Any]], limit: int | None) -> Iterator[dict[str, Any]]:
    return records if limit is None else islice(records, limit)


def _job_from_payload(run_id: str, payload: dict[str, Any]) -> CleanupJob:
    text = payload.get("text_normalized")
    if text is None:
        text = payload["text_ocr"]
    input_hash = sha256(text.encode()).hexdigest()
    identity = _composite_identity(payload)
    identifier = sha256(f"{run_id}:{identity}:{input_hash}".encode()).hexdigest()
    return CleanupJob(
        id=identifier,
        run_id=run_id,
        paragraph_id=payload["id"],
        identity=identity,
        input_hash=input_hash,
        source_json=json.dumps(payload, separators=(",", ":")),
        source_text=text,
    )


def composite_identity(payload: dict[str, Any]) -> str:
    return _composite_identity(payload)


def _composite_identity(payload: dict[str, Any]) -> str:
    return "\x1f".join(str(payload.get(key, "")) for key in ("item_identifier", "scan_leaf", "id"))


def _pending_jobs(run_id: str):
    return (
        select(CleanupJob)
        .where(CleanupJob.run_id == run_id, CleanupJob.status == "pending")
        .order_by(CleanupJob.paragraph_id)
        .limit(1)
    )


def _update_job(
    database_path: Path,
    job_id: str,
    status: str,
    result_json: str | None,
    error: str | None,
    duration_ms: int,
    raw_response: str | None = None,
    usage: dict[str, int] | None = None,
) -> None:
    engine = _engine(database_path)
    with Session(engine) as session, session.begin():
        job = session.get(CleanupJob, job_id)
        if job is None:
            raise ValueError(f"Unknown cleanup job: {job_id}")
        job.status = status
        job.result_json = result_json
        job.error = error
        job.duration_ms = duration_ms
        if raw_response is not None:
            job.raw_response = raw_response
        if usage is not None:
            job.usage_json = json.dumps(usage, separators=(",", ":"))
        job.updated_at = _now()


def _now() -> str:
    return datetime.now(UTC).isoformat()
