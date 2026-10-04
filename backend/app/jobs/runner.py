"""Job runner managing background execution, concurrency semaphores, cancellation, and cleanup."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import shutil
import time
from typing import Dict, List, Optional

from app.config import get_settings
from app.events.bus import EventBus, get_event_bus
from app.graph.pipeline import AutoShortsPipeline
from app.jobs.repo import JobRepo


class JobRunner:
    """Manages background execution of AutoShorts pipelines with strict concurrency control."""

    def __init__(self, repo: Optional[JobRepo] = None, event_bus: Optional[EventBus] = None):
        self.settings = get_settings()
        self.repo = repo or JobRepo()
        self.event_bus = event_bus or get_event_bus()
        self.pipeline = AutoShortsPipeline(event_bus=self.event_bus, repo=self.repo)

        self._job_semaphore = asyncio.Semaphore(self.settings.MAX_CONCURRENT_JOBS)
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._recent_creations: List[float] = []
        self._lock = asyncio.Lock()

    def check_rate_limit(self) -> bool:
        """Enforce JOB_CREATE_RATE_LIMIT_PER_MINUTE sliding window."""
        now = time.time()
        cutoff = now - 60.0
        self._recent_creations = [t for t in self._recent_creations if t > cutoff]
        if len(self._recent_creations) >= self.settings.JOB_CREATE_RATE_LIMIT_PER_MINUTE:
            return False
        self._recent_creations.append(now)
        return True

    async def submit_job(self, prompt: str) -> str:
        """Create job record and launch pipeline in background task.
        
        Returns:
            job_id string.
        """
        from app.core.ids import new_job_id
        job_id = new_job_id()
        await self.repo.create_job(job_id=job_id, prompt=prompt)

        # Launch background task
        task = asyncio.create_task(self._execute_job_task(job_id, prompt))
        async with self._lock:
            self._active_tasks[job_id] = task

        return job_id

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel an actively running job."""
        async with self._lock:
            task = self._active_tasks.get(job_id)

        if task and not task.done():
            task.cancel()
            await self.repo.update_job_status(job_id, status="cancelled")
            await self.event_bus.publish(job_id, "job.cancelled", {})
            return True

        job = await self.repo.get_job(job_id)
        if job and job.status in ("pending", "queued", "running"):
            await self.repo.update_job_status(job_id, status="cancelled")
            await self.event_bus.publish(job_id, "job.cancelled", {})
            return True

        return False

    async def _execute_job_task(self, job_id: str, prompt: str) -> None:
        """Worker loop acquiring job semaphore and running pipeline."""
        try:
            async with self._job_semaphore:
                await self.pipeline.run(job_id, prompt)

        except asyncio.CancelledError:
            await self.repo.update_job_status(job_id, status="cancelled")
            await self.event_bus.publish(job_id, "job.cancelled", {})

        except Exception as e:
            await self.repo.update_job_status(
                job_id,
                status="failed",
                error_code="INTERNAL_ERROR",
                error_message=str(e),
            )
            await self.event_bus.publish(
                job_id,
                "job.failed",
                {
                    "stage": "unknown",
                    "code": "INTERNAL_ERROR",
                    "message": str(e),
                    "retryable": False,
                },
            )

        finally:
            async with self._lock:
                self._active_tasks.pop(job_id, None)

            # Cleanup temporary files
            storage_tmp = self.settings.resolved_media_dir / "jobs" / job_id / "tmp"
            if storage_tmp.exists():
                shutil.rmtree(storage_tmp, ignore_errors=True)


_global_job_runner: Optional[JobRunner] = None


def get_job_runner() -> JobRunner:
    global _global_job_runner
    if _global_job_runner is None:
        _global_job_runner = JobRunner()
    return _global_job_runner
