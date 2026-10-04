"""Live verification tests for FastAPI endpoints, SSE streaming, Range media delivery, and cancellation."""

import asyncio
import json
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.events.bus import get_event_bus
from app.jobs.repo import JobRepo
from app.main import app


@pytest.fixture
def test_repo():
    return JobRepo()


@pytest.fixture
def test_event_bus():
    return get_event_bus()


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify health probe endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "version": "1.0.0"}


@pytest.mark.asyncio
async def test_create_and_get_job():
    """Verify job creation and state retrieval without secret leakage."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create job
        create_resp = await ac.post("/api/jobs", json={"prompt": "Why is the sky blue on Earth?"})
        assert create_resp.status_code == 201
        data = create_resp.json()
        assert "id" in data
        assert data["status"] in ("queued", "pending")
        assert data["progress"] == 0.0

        job_id = data["id"]

        # Get job snapshot
        get_resp = await ac.get(f"/api/jobs/{job_id}")
        assert get_resp.status_code == 200
        snapshot = get_resp.json()
        assert snapshot["id"] == job_id
        assert snapshot["prompt"] == "Why is the sky blue on Earth?"
        assert "stages" in snapshot

        # Ensure no forbidden fields
        resp_text = get_resp.text
        for forbidden in ("api_key", "secret", "AQ.", "4VPJ", "5774"):
            assert forbidden not in resp_text


@pytest.mark.asyncio
async def test_sse_streaming_and_replay(test_event_bus, test_repo):
    """Verify SSE streaming, first snapshot event, live broadcast, and Last-Event-ID replay."""
    job_id = "test_sse_replay_job"
    await test_repo.create_job(job_id=job_id, prompt="How do stars produce light?")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:

        # Publish a test stage event to DB
        ev1_id = await test_event_bus.publish(
            job_id,
            "stage.started",
            {"stage": "research", "message": "Researching topic"},
        )

        ev2_id = await test_event_bus.publish(
            job_id,
            "stage.progress",
            {"stage": "research", "progress": 0.5, "message": "Writing draft"},
        )

        # Connect to SSE stream requesting replay after ev1_id
        async with ac.stream("GET", f"/api/jobs/{job_id}/events", headers={"Last-Event-ID": str(ev1_id)}) as sse_stream:
            lines = []
            async for line in sse_stream.aiter_lines():
                if line.strip():
                    lines.append(line.strip())
                if len(lines) >= 6:
                    break

            text = "\n".join(lines)
            # Verify first event is job.snapshot
            assert "event: job.snapshot" in text
            # Verify replayed event 2 is received
            assert "event: stage.progress" in text
            assert "Writing draft" in text


@pytest.mark.asyncio
async def test_media_http_range_support():
    """Verify HTTP Range partial content delivery (206) for video seeking."""
    job_id = "test_assembly_live"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Request first 1000 bytes with Range header
        headers = {"Range": "bytes=0-999"}
        resp = await ac.get(f"/api/media/{job_id}/video.mp4", headers=headers)

        assert resp.status_code == 206
        assert "Content-Range" in resp.headers
        assert resp.headers["Content-Range"].startswith("bytes 0-999/")
        assert resp.headers["Content-Length"] == "1000"
        assert resp.headers["Accept-Ranges"] == "bytes"
        assert len(resp.content) == 1000


@pytest.mark.asyncio
async def test_job_cancellation():
    """Verify job cancellation endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create_resp = await ac.post("/api/jobs", json={"prompt": "Test cancellation prompt"})
        job_id = create_resp.json()["id"]

        cancel_resp = await ac.post(f"/api/jobs/{job_id}/cancel")
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["ok"] is True

        get_resp = await ac.get(f"/api/jobs/{job_id}")
        assert get_resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_list_and_delete_job():
    """Verify listing library jobs and deleting jobs."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create_resp = await ac.post("/api/jobs", json={"prompt": "Job to be deleted"})
        job_id = create_resp.json()["id"]

        # List jobs
        list_resp = await ac.get("/api/jobs")
        assert list_resp.status_code == 200
        jobs = list_resp.json()["jobs"]
        assert any(j["id"] == job_id for j in jobs)

        # Delete job
        del_resp = await ac.delete(f"/api/jobs/{job_id}")
        assert del_resp.status_code == 204

        # Confirm 404 after deletion
        get_resp = await ac.get(f"/api/jobs/{job_id}")
        assert get_resp.status_code == 404
