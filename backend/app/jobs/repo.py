"""Async SQLite repository for AutoShorts jobs, stages, and events."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
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
        self._initialized: bool = False
        self._init_lock: Optional[asyncio.Lock] = None
        self._seq_locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self) -> asyncio.Lock:
        if self._init_lock is None:
            self._init_lock = asyncio.Lock()
        return self._init_lock

    def _get_seq_lock(self, job_id: str) -> asyncio.Lock:
        if job_id not in self._seq_locks:
            self._seq_locks[job_id] = asyncio.Lock()
        return self._seq_locks[job_id]

    async def ensure_db(self) -> None:
        if not self._initialized:
            async with self._get_lock():
                if not self._initialized:
                    await self.init_db()

    async def init_db(self) -> None:
        """Initialize tables and enable WAL mode & foreign keys."""
        async with self.engine.begin() as conn:
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            await conn.exec_driver_sql("PRAGMA foreign_keys=ON;")
            await conn.run_sync(Base.metadata.create_all)
        self._initialized = True

    async def close(self) -> None:
        await self.engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        await self.ensure_db()
        async with self.session_factory() as s:
            yield s

    # --- JOB OPERATIONS ---

    async def create_job(self, job_id: str, prompt: str) -> JobModel:
        async with self.session() as s:
            job = JobModel(
                id=job_id,
                prompt=prompt,
                status="queued",
                created_at=utcnow(),
            )
            s.add(job)
            await s.commit()
            return job

    async def get_job(self, job_id: str) -> Optional[JobModel]:
        async with self.session() as s:
            stmt = select(JobModel).where(JobModel.id == job_id)
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def list_jobs(self, status: Optional[str] = None, limit: int = 100) -> List[JobModel]:
        async with self.session() as s:
            stmt = select(JobModel).order_by(JobModel.created_at.desc()).limit(limit)
            if status:
                stmt = stmt.where(JobModel.status == status)
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def update_job(self, job_id: str, **kwargs: Any) -> Optional[JobModel]:
        async with self.session() as s:
            stmt = (
                update(JobModel)
                .where(JobModel.id == job_id)
                .values(**kwargs)
                .returning(JobModel)
            )
            result = await s.execute(stmt)
            await s.commit()
            return result.scalar_one_or_none()

    async def update_job_status(self, job_id: str, **kwargs: Any) -> Optional[JobModel]:
        return await self.update_job(job_id, **kwargs)

    async def delete_job(self, job_id: str) -> bool:
        async with self.session() as s:
            # Delete stages and events associated with job
            await s.execute(delete(StageModel).where(StageModel.job_id == job_id))
            await s.execute(delete(EventModel).where(EventModel.job_id == job_id))
            res = await s.execute(delete(JobModel).where(JobModel.id == job_id))
            await s.commit()
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
        async with self.session() as s:
            stmt = select(StageModel).where(
                StageModel.job_id == job_id, StageModel.stage == stage
            )
            result = await s.execute(stmt)
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
                await s.commit()
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
                s.add(new_stage)
                await s.commit()
                return new_stage

    async def get_stages(self, job_id: str) -> List[StageModel]:
        async with self.session() as s:
            stmt = select(StageModel).where(StageModel.job_id == job_id)
            result = await s.execute(stmt)
            return list(result.scalars().all())

    # --- EVENT OPERATIONS ---

    async def get_max_event_seq(self, job_id: str) -> int:
        async with self.session() as s:
            stmt = (
                select(EventModel.seq)
                .where(EventModel.job_id == job_id)
                .order_by(EventModel.seq.desc())
                .limit(1)
            )
            result = await s.execute(stmt)
            max_seq = result.scalar_one_or_none()
            return max_seq or 0

    async def insert_event(
        self, job_id: str, seq: int, event_type: str, payload_json: str
    ) -> EventModel:
        async with self.session() as s:
            event = EventModel(
                job_id=job_id,
                seq=seq,
                type=event_type,
                payload_json=payload_json,
                created_at=utcnow(),
            )
            s.add(event)
            await s.commit()
            return event

    async def append_event(self, job_id: str, event_type: str, payload: Dict[str, Any]) -> int:
        async with self._get_seq_lock(job_id):
            async with self.session() as s:
                stmt = (
                    select(EventModel.seq)
                    .where(EventModel.job_id == job_id)
                    .order_by(EventModel.seq.desc())
                    .limit(1)
                )
                result = await s.execute(stmt)
                max_seq = result.scalar_one_or_none() or 0
                seq = max_seq + 1

                event = EventModel(
                    job_id=job_id,
                    seq=seq,
                    type=event_type,
                    payload_json=json.dumps(payload),
                    created_at=utcnow(),
                )
                s.add(event)
                await s.commit()
                return seq

    async def get_events(
        self, job_id: str, after_seq: int = 0
    ) -> List[EventModel]:
        async with self.session() as s:
            stmt = (
                select(EventModel)
                .where(EventModel.job_id == job_id, EventModel.seq > after_seq)
                .order_by(EventModel.seq.asc())
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def get_events_after(self, job_id: str, after_seq: int = 0) -> List[Dict[str, Any]]:
        async with self.session() as s:
            stmt = (
                select(EventModel)
                .where(EventModel.job_id == job_id, EventModel.seq > after_seq)
                .order_by(EventModel.seq.asc())
            )
            result = await s.execute(stmt)
            events = list(result.scalars().all())
            return [
                {
                    "id": ev.seq,
                    "event": ev.type,
                    "data": json.loads(ev.payload_json),
                    "created_at": ev.created_at.isoformat() if ev.created_at else None,
                }
                for ev in events
            ]


JobRepo = JobRepository
