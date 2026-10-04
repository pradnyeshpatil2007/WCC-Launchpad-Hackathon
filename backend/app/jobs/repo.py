"""Async SQLite repository for AutoShorts jobs, stages, and events."""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.jobs.models import Base, EventModel, JobModel, StageModel, utcnow


class JobRepository:
    def __init__(self, db_path: Optional[str] = None):
        settings = get_settings()
        raw_path = Path(db_path).resolve() if db_path else settings.resolved_db_path
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_url = f"sqlite+aiosqlite:///{raw_path.as_posix()}"
        self.engine: AsyncEngine = create_async_engine(
            self.db_url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    async def init_db(self) -> None:
        """Initialize tables and enable WAL mode & foreign keys."""
        async with self.engine.begin() as conn:
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            await conn.exec_driver_sql("PRAGMA foreign_keys=ON;")
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    # --- JOB OPERATIONS ---

    async def create_job(self, job_id: str, prompt: str) -> JobModel:
        async with self.session_factory() as session:
            job = JobModel(
                id=job_id,
                prompt=prompt,
                status="queued",
                created_at=utcnow(),
            )
            session.add(job)
            await session.commit()
            return job

    async def get_job(self, job_id: str) -> Optional[JobModel]:
        async with self.session_factory() as session:
            stmt = select(JobModel).where(JobModel.id == job_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_jobs(self, status: Optional[str] = None, limit: int = 100) -> List[JobModel]:
        async with self.session_factory() as session:
            stmt = select(JobModel).order_by(JobModel.created_at.desc()).limit(limit)
            if status:
                stmt = stmt.where(JobModel.status == status)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_job(self, job_id: str, **kwargs: Any) -> Optional[JobModel]:
        async with self.session_factory() as session:
            stmt = (
                update(JobModel)
                .where(JobModel.id == job_id)
                .values(**kwargs)
                .returning(JobModel)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.scalar_one_or_none()

    async def delete_job(self, job_id: str) -> bool:
        async with self.session_factory() as session:
            # Delete stages and events associated with job
            await session.execute(delete(StageModel).where(StageModel.job_id == job_id))
            await session.execute(delete(EventModel).where(EventModel.job_id == job_id))
            res = await session.execute(delete(JobModel).where(JobModel.id == job_id))
            await session.commit()
            return res.rowcount > 0

    # --- STAGE OPERATIONS ---

    async def set_stage(
        self,
        job_id: str,
        stage: str,
        status: str,
        output_ref: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> StageModel:
        async with self.session_factory() as session:
            stmt = select(StageModel).where(
                StageModel.job_id == job_id, StageModel.stage == stage
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            now = utcnow()
            if existing:
                existing.status = status
                if status == "running":
                    existing.started_at = now
                    existing.attempts += 1
                elif status in ("success", "failed"):
                    existing.ended_at = now
                if output_ref is not None:
                    existing.output_ref = output_ref
                if error_code is not None:
                    existing.error_code = error_code
                await session.commit()
                return existing
            else:
                new_stage = StageModel(
                    job_id=job_id,
                    stage=stage,
                    status=status,
                    attempts=1,
                    started_at=now if status == "running" else None,
                    ended_at=now if status in ("success", "failed") else None,
                    output_ref=output_ref,
                    error_code=error_code,
                )
                session.add(new_stage)
                await session.commit()
                return new_stage

    async def get_stages(self, job_id: str) -> List[StageModel]:
        async with self.session_factory() as session:
            stmt = select(StageModel).where(StageModel.job_id == job_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # --- EVENT OPERATIONS ---

    async def get_max_event_seq(self, job_id: str) -> int:
        async with self.session_factory() as session:
            stmt = (
                select(EventModel.seq)
                .where(EventModel.job_id == job_id)
                .order_by(EventModel.seq.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            max_seq = result.scalar_one_or_none()
            return max_seq or 0

    async def insert_event(
        self, job_id: str, seq: int, event_type: str, payload_json: str
    ) -> EventModel:
        async with self.session_factory() as session:
            event = EventModel(
                job_id=job_id,
                seq=seq,
                type=event_type,
                payload_json=payload_json,
                created_at=utcnow(),
            )
            session.add(event)
            await session.commit()
            return event

    async def get_events(
        self, job_id: str, after_seq: int = 0
    ) -> List[EventModel]:
        async with self.session_factory() as session:
            stmt = (
                select(EventModel)
                .where(EventModel.job_id == job_id, EventModel.seq > after_seq)
                .order_by(EventModel.seq.asc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
