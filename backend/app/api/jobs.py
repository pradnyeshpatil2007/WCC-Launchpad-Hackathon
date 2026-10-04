"""REST and SSE endpoints for job creation, querying, streaming, cancellation, and library listing."""

import asyncio
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.events.bus import EventBus, get_event_bus
from app.jobs.repo import JobRepo
from app.jobs.runner import JobRunner, get_job_runner


router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class CreateJobRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=500)


def build_job_snapshot(job: Any, last_event_id: int) -> Dict[str, Any]:
    """Convert DB job record into a canonical RunState-compatible snapshot."""
    if isinstance(job, dict):
        j_id = job["id"]
        j_prompt = job["prompt"]
        j_status = job["status"]
        j_stage = job.get("current_stage") or "pending"
        j_progress = float(job.get("progress", 0.0) or 0.0)
        j_title = job.get("title")
        j_dur = job.get("duration_sec")
        j_thumb = job.get("thumbnail_url")
        j_video = job.get("video_url")
        j_code = job.get("error_code")
        j_msg = job.get("error_message")
    else:
        j_id = job.id
        j_prompt = job.prompt
        j_status = job.status
        j_stage = job.current_stage or "pending"
        j_progress = float(getattr(job, "progress", 0.0) or 0.0)
        j_title = job.title
        j_dur = job.duration_sec
        j_thumb = job.thumbnail_url
        j_video = job.video_url
        j_code = job.error_code
        j_msg = job.error_message

    return {
        "id": j_id,
        "prompt": j_prompt,
        "status": j_status,
        "stage": j_stage,
        "progress": j_progress,
        "title": j_title,
        "durationSec": j_dur,
        "thumbnailUrl": j_thumb,
        "videoUrl": j_video,
        "sceneCount": None,
        "sceneStartTimes": None,
        "error": {
            "stage": j_stage,
            "code": j_code or "ERROR",
            "message": j_msg or "Job failed",
            "retryable": False,
        } if j_code else None,
        "lastEventId": last_event_id,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_job(req: CreateJobRequest):
    """Create a new AutoShorts video generation job."""
    runner = get_job_runner()
    if not runner.check_rate_limit():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Too many requests. Please slow down.", "retryable": True}},
        )

    job_id = await runner.submit_job(req.prompt.strip())
    job = await runner.repo.get_job(job_id)

    return {
        "id": job_id,
        "jobId": job_id,
        "prompt": job.prompt if job else req.prompt.strip(),
        "status": job.status if job else "queued",
        "stage": "pending",
        "progress": 0.0,
        "lastEventId": 0,
    }


@router.get("")
async def list_jobs(limit: int = 50, offset: int = 0):
    """List historical and active jobs for library view."""
    repo = JobRepo()
    jobs = await repo.list_jobs(limit=limit)
    return {
        "jobs": [
            {
                "id": j.id,
                "prompt": j.prompt,
                "status": j.status,
                "stage": j.current_stage or "pending",
                "progress": float(getattr(j, "progress", 0.0) or 0.0),
                "title": j.title,
                "durationSec": j.duration_sec,
                "thumbnailUrl": j.thumbnail_url,
                "videoUrl": j.video_url,
                "createdAt": j.created_at.isoformat() if j.created_at else None,
                "completedAt": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in jobs
        ]
    }


@router.get("/{job_id}")
async def get_job(job_id: str):
    """Retrieve current state and stage data for a specific job."""
    repo = JobRepo()
    job = await repo.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": f"Job {job_id} does not exist", "retryable": False}},
        )

    stages = await repo.get_stages(job_id)
    events = await repo.get_events(job_id)
    last_event_id = events[-1].seq if events else 0

    snapshot = build_job_snapshot(job, last_event_id)
    snapshot["stages"] = [
        {
            "stage": s.stage,
            "status": s.status,
            "attempts": s.attempts,
            "startedAt": s.started_at.isoformat() if s.started_at else None,
            "endedAt": s.ended_at.isoformat() if s.ended_at else None,
            "outputRef": s.output_ref,
            "errorCode": s.error_code,
        }
        for s in stages
    ]
    return snapshot


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel an active or pending job."""
    runner = get_job_runner()
    cancelled = await runner.cancel_job(job_id)
    return {"ok": cancelled}


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: str):
    """Delete a job, its DB records, and on-disk media."""
    repo = JobRepo()
    job = await repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    settings = get_settings()
    job_dir = settings.resolved_media_dir / "jobs" / job_id
    if job_dir.exists():
        import shutil
        shutil.rmtree(job_dir, ignore_errors=True)

    await repo.delete_job(job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{job_id}/events")
async def stream_job_events(
    job_id: str,
    request: Request,
    last_event_id_header: Optional[str] = Header(None, alias="Last-Event-ID"),
    lastEventId_query: Optional[int] = Query(None, alias="lastEventId"),
):
    """Server-Sent Events (SSE) live stream delivering sanitized real-time pipeline events."""
    repo = JobRepo()
    job = await repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Determine last event ID from header or query param
    start_event_id = 0
    if last_event_id_header and last_event_id_header.isdigit():
        start_event_id = int(last_event_id_header)
    elif lastEventId_query is not None:
        start_event_id = lastEventId_query

    event_bus = get_event_bus()

    async def event_generator():
        # First event is ALWAYS job.snapshot per Frontend Spec §9.2
        past_events = await repo.get_events(job_id)
        current_last_id = past_events[-1].seq if past_events else 0
        snapshot_data = build_job_snapshot(job, current_last_id)

        snapshot_sse = f"event: job.snapshot\ndata: {json.dumps(snapshot_data)}\n\n"
        yield snapshot_sse

        # If already completed or failed, close after snapshot
        status_val = job.status if hasattr(job, "status") else job.get("status")
        if status_val in ("completed", "failed", "cancelled"):
            return

        # Subscribe to live events and historical replay
        subscription = event_bus.subscribe(job_id, last_event_id=start_event_id)
        last_ping = asyncio.get_event_loop().time()

        try:
            while True:
                # Check client disconnect
                if await request.is_disconnected():
                    break

                try:
                    # Wait up to 15s for next event or send heartbeat
                    msg = await asyncio.wait_for(subscription.__anext__(), timeout=15.0)
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    # Heartbeat comment to keep connection alive
                    yield ": ping\n\n"
                    continue

                ev_str = f"id: {msg['id']}\nevent: {msg['event']}\ndata: {json.dumps(msg['data'])}\n\n"
                yield ev_str

                if msg["event"] in ("job.completed", "job.failed", "job.cancelled"):
                    break

        except (asyncio.CancelledError, GeneratorExit, StopAsyncIteration):
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
