"""Domain models for timeline, shots, motion presets, caption pages, and overlays."""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class MotionPreset(str, Enum):
    PUSH_IN = "push_in"
    PULL_OUT = "pull_out"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    TILT_UP = "tilt_up"
    TILT_DOWN = "tilt_down"
    DRIFT_LEFT_UP = "drift_left_up"
    DRIFT_RIGHT_DOWN = "drift_right_down"
    DIAGONAL_PUSH = "diagonal_push"
    ARC_PAN = "arc_pan"


class TransitionType(str, Enum):
    CROSSFADE = "crossfade"
    ZOOM_DISSOLVE = "zoom_dissolve"
    SOFT_PUSH = "soft_push"
    DIP_LIGHT = "dip_light"


class Shot(BaseModel):
    shot_index: int
    scene_index: int
    beat_key: str
    image_file: str  # relative path within job storage
    start_sec: float
    end_sec: float
    duration_sec: float
    motion_preset: MotionPreset
    scale0: float = Field(ge=1.0, le=1.35)
    scale1: float = Field(ge=1.0, le=1.35)
    center0: Tuple[float, float]  # (cx, cy) in normalized 0.0-1.0 coords
    center1: Tuple[float, float]  # (cx, cy) in normalized 0.0-1.0 coords
    transition_type: TransitionType = TransitionType.CROSSFADE
    transition_sec: float = 0.42
    is_reframe: bool = False


class CaptionWord(BaseModel):
    text: str
    start_sec: float
    end_sec: float


class CaptionPage(BaseModel):
    page_index: int
    scene_index: int
    words: List[CaptionWord]
    start_sec: float
    end_sec: float
    lines: List[str]


class EmphasisOverlay(BaseModel):
    scene_index: int
    text: str
    start_sec: float
    end_sec: float


class Timeline(BaseModel):
    duration_sec: float
    fps: int = 30
    width: int = 1080
    height: int = 1920
    lead_in_sec: float = 0.4
    tail_sec: float = 0.6
    shots: List[Shot]
    caption_pages: List[CaptionPage]
    emphasis_overlays: List[EmphasisOverlay]
    narration_audio_file: str
    seed: int
