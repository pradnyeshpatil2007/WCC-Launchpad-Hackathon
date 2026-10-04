"""Strict allow-list Pydantic models for all public SSE events with extra='forbid'."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class BasePublicEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JobSnapshotEvent(BasePublicEvent):
    id: str
    prompt: str
    status: str
    stage: str
    progress: float
    title: Optional[str] = None
    durationSec: Optional[float] = None
    thumbnailUrl: Optional[str] = None
    videoUrl: Optional[str] = None
    sceneCount: Optional[int] = None
    sceneStartTimes: Optional[List[float]] = None
    error: Optional[Dict[str, Any]] = None
    lastEventId: int


class StageStartedEvent(BasePublicEvent):
    stage: str
    message: str


class StageProgressEvent(BasePublicEvent):
    stage: str
    progress: float
    message: Optional[str] = None


class StageCompletedEvent(BasePublicEvent):
    stage: str
    durationMs: int
    message: Optional[str] = None


class SubstepStartedEvent(BasePublicEvent):
    node: str
    message: str


class SubstepProgressEvent(BasePublicEvent):
    node: str
    percent: Optional[float] = None
    fps: Optional[float] = None
    etaSeconds: Optional[int] = None
    currentShot: Optional[int] = None
    totalShots: Optional[int] = None
    sceneIndex: Optional[int] = None
    message: Optional[str] = None


class SubstepCompletedEvent(BasePublicEvent):
    node: str
    durationMs: int


class ScriptReadyEvent(BasePublicEvent):
    title: str
    sceneCount: int
    wordCount: int


class SceneVoiceReadyEvent(BasePublicEvent):
    sceneIndex: int
    durationSec: float


class SceneVisualReadyEvent(BasePublicEvent):
    sceneIndex: int
    source: Literal["generated", "stock"]
    imageCount: int
    previewUrl: Optional[str] = None


class RetryAttemptEvent(BasePublicEvent):
    node: str
    attempt: int
    maxAttempts: int
    message: str


class FallbackUsedEvent(BasePublicEvent):
    node: str
    sceneIndex: Optional[int] = None
    kind: Literal["model", "visual_source"]
    message: str


class JobCompletedEvent(BasePublicEvent):
    videoUrl: str
    thumbnailUrl: str
    durationSec: float
    sceneStartTimes: List[float]


class JobFailedEvent(BasePublicEvent):
    stage: str
    code: str
    message: str
    retryable: bool


class JobCancelledEvent(BasePublicEvent):
    pass
