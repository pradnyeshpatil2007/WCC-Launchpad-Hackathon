"""Domain models for audio voice assets and visual assets (Doc 3 §6.2, §6.3)."""

from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field


class WordTiming(BaseModel):
    text: str
    start: float  # seconds relative to scene audio start
    end: float


class SceneAudio(BaseModel):
    scene_index: int
    file: str  # relative path to working WAV
    duration_sec: float  # ffprobe verified duration
    words: List[WordTiming] = Field(default_factory=list)
    timing_mode: Literal["word_boundary", "sentence_proportional"] = "word_boundary"
    voice: str
    rate: str


class VoiceManifest(BaseModel):
    scenes: List[SceneAudio]
    total_sec: float
    rate_bump_percent: int = 0


class AcceptedImage(BaseModel):
    beat_key: str  # e.g., "s00_b00"
    file: str  # relative path to working master image in storage
    width: int
    height: int
    source: Literal["generated", "pexels", "pixabay"]
    source_ref: Dict[str, Any]  # model/id/photographer/url
    focal: Tuple[float, float] = (0.5, 0.5)  # normalized (x, y) saliency centroid
    phash: str
    preview_file: Optional[str] = None


class SceneVisuals(BaseModel):
    scene_index: int
    images: List[AcceptedImage]


class VisualManifest(BaseModel):
    scenes: List[SceneVisuals]
