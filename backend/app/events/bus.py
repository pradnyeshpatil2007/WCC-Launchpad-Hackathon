"""In-memory EventBus with SQLite event persistence, replay buffer, and leak guard."""

import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List, Optional, Set
from pydantic import BaseModel

from app.events.public import (
    BasePublicEvent,
    FallbackUsedEvent,
    JobCancelledEvent,
    JobCompletedEvent,
    JobFailedEvent,
    JobSnapshotEvent,
    RetryAttemptEvent,
    SceneVisualReadyEvent,
    SceneVoiceReadyEvent,
    ScriptReadyEvent,
    StageCompletedEvent,
    StageProgressEvent,
    StageStartedEvent,
    SubstepCompletedEvent,
    SubstepProgressEvent,
    SubstepStartedEvent,
)
from app.jobs.repo import JobRepo


EVENT_TYPE_TO_MODEL = {
    "job.snapshot": JobSnapshotEvent,
    "stage.started": StageStartedEvent,
    "stage.progress": StageProgressEvent,
    "stage.completed": StageCompletedEvent,
    "substep.started": SubstepStartedEvent,
    "substep.progress": SubstepProgressEvent,
    "substep.completed": SubstepCompletedEvent,
    "script.ready": ScriptReadyEvent,
    "scene.voice_ready": SceneVoiceReadyEvent,
    "scene.visual_ready": SceneVisualReadyEvent,
    "retry.attempt": RetryAttemptEvent,
    "fallback.used": FallbackUsedEvent,
    "job.completed": JobCompletedEvent,
    "job.failed": JobFailedEvent,
    "job.cancelled": JobCancelledEvent,
}


import re

PATH_REGEX = re.compile(r"[a-zA-Z]:[\\/][^\s'\"]+")


def sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize payload to guarantee no secret tokens or file system paths are exposed."""
    cleaned = {}
    for k, v in payload.items():
        # Strip internal or sensitive keys
        if any(bad in k.lower() for bad in ("key", "secret", "token", "password", "auth", "path", "abs_path")):
            if k not in ("videoUrl", "thumbnailUrl", "previewUrl"):
                continue

        if isinstance(v, str):
            # Convert media paths to relative URLs
            if "video.mp4" in v and (":\\" in v or ":/" in v):
                v = "/api/media/" + v.split("jobs")[-1].replace("\\", "/").strip("/")
            elif "thumbnail.jpg" in v and (":\\" in v or ":/" in v):
                v = "/api/media/" + v.split("jobs")[-1].replace("\\", "/").strip("/")
            else:
                v = PATH_REGEX.sub("[local_path]", v)
            cleaned[k] = v
        elif isinstance(v, dict):
            cleaned[k] = sanitize_payload(v)
        elif isinstance(v, list):
            cleaned[k] = [sanitize_payload(i) if isinstance(i, dict) else i for i in v]
        else:
            cleaned[k] = v
    return cleaned


class EventBus:
    """Publish-subscribe event bus with replay buffer and SQLite event sourcing."""

    def __init__(self, repo: Optional[JobRepo] = None):
        self.repo = repo or JobRepo()
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, job_id: str, event_type: str, payload: Dict[str, Any]) -> int:
        """Validate, persist to DB, and broadcast an event to active subscribers.
        
        Returns:
            The monotonic event ID assigned by the database.
        """
        model_cls = EVENT_TYPE_TO_MODEL.get(event_type)
        if not model_cls:
            raise ValueError(f"Disallowed SSE event type: {event_type}")

        # Sanitize payload
        clean_data = sanitize_payload(payload)
        # Validate against strict Pydantic model
        validated_obj = model_cls.model_validate(clean_data)
        validated_dict = validated_obj.model_dump(exclude_unset=False, exclude_none=True)

        # Persist to SQLite WAL table
        event_id = await self.repo.append_event(job_id=job_id, event_type=event_type, payload=validated_dict)

        # Broadcast to active in-memory subscriber queues
        async with self._lock:
            subs = self._subscribers.get(job_id, set()).copy()

        event_msg = {
            "id": event_id,
            "event": event_type,
            "data": validated_dict,
        }

        for q in subs:
            try:
                q.put_nowait(event_msg)
            except Exception:
                pass

        return event_id

    async def subscribe(
        self,
        job_id: str,
        last_event_id: int = 0,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Subscribe to a job's event stream, replaying missed events first."""
        queue: asyncio.Queue = asyncio.Queue()

        async with self._lock:
            if job_id not in self._subscribers:
                self._subscribers[job_id] = set()
            self._subscribers[job_id].add(queue)

        try:
            # 1. Replay historical events from SQLite if last_event_id provided
            if last_event_id > 0:
                past_events = await self.repo.get_events_after(job_id, last_event_id)
                for ev in past_events:
                    yield {
                        "id": ev["id"],
                        "event": ev["event"],
                        "data": ev["data"],
                    }

            # 2. Stream live events
            while True:
                msg = await queue.get()
                # If message ID was already yielded during replay, skip
                if msg["id"] <= last_event_id:
                    continue
                yield msg

                if msg["event"] in ("job.completed", "job.failed", "job.cancelled"):
                    break

        finally:
            async with self._lock:
                if job_id in self._subscribers and queue in self._subscribers[job_id]:
                    self._subscribers[job_id].remove(queue)
                    if not self._subscribers[job_id]:
                        del self._subscribers[job_id]


_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus
