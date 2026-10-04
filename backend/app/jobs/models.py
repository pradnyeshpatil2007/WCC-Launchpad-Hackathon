"""SQLAlchemy models for AutoShorts SQLite persistence (Doc 3 §5.1)."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobModel(Base):
    __tablename__ = "jobs"

    id = Column(String(32), primary_key=True)
    prompt = Column(Text, nullable=False)
    title = Column(String(256), nullable=True)
    status = Column(String(32), nullable=False, default="queued")
    current_stage = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_sec = Column(Float, nullable=True)
    scene_count = Column(Integer, nullable=True)
    error_stage = Column(String(32), nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    error_retryable = Column(Boolean, nullable=True)
    schema_version = Column(Integer, default=1, nullable=False)

    __table_args__ = (
        Index("idx_jobs_created_at", created_at.desc()),
        Index("idx_jobs_status", status),
    )


class StageModel(Base):
    __tablename__ = "stages"

    job_id = Column(String(32), nullable=False)
    stage = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default="pending")
    attempts = Column(Integer, default=1, nullable=False)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    output_ref = Column(Text, nullable=True)
    error_code = Column(String(64), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("job_id", "stage", name="pk_stages"),
    )


class EventModel(Base):
    __tablename__ = "events"

    job_id = Column(String(32), nullable=False)
    seq = Column(Integer, nullable=False)
    type = Column(String(64), nullable=False)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("job_id", "seq", name="pk_events"),
        Index("idx_events_job_seq", job_id, seq),
    )
