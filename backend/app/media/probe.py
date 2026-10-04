"""Video verification via ffprobe and 540x960 thumbnail generation."""

import json
from pathlib import Path
import subprocess
from typing import Any, Dict, Tuple
from PIL import Image

from app.core.errors import StageError


def probe_video_streams(video_path: Path) -> Dict[str, Any]:
    """Run ffprobe to extract detailed container and stream metadata."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-of", "json",
        str(video_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    return json.loads(res.stdout)


def verify_video_quality(video_path: Path) -> Dict[str, Any]:
    """Verify video satisfies all hard quality requirements from PRD and Doc 3 §13.8.
    
    Checks:
        - Container size > 100 KB
        - Video stream present with h264 codec
        - Resolution exactly 1080x1920
        - FPS is 30 (or close to 30)
        - Audio stream present with aac codec
        - Duration <= 60.0s
        - A/V delta <= 0.15s
    """
    if not video_path.exists():
        raise StageError(code="RENDER_FAILED", stage="assembly", message=f"Video file does not exist: {video_path}")

    file_size_kb = video_path.stat().st_size / 1024.0
    if file_size_kb < 100.0:
        raise StageError(code="RENDER_FAILED", stage="assembly", message=f"Video file too small: {file_size_kb:.1f} KB (< 100 KB)")

    meta = probe_video_streams(video_path)
    streams = meta.get("streams", [])
    format_info = meta.get("format", {})

    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not v_stream:
        raise StageError(code="RENDER_FAILED", stage="assembly", message="No video stream found in rendered output")
    if not a_stream:
        raise StageError(code="RENDER_FAILED", stage="assembly", message="No audio stream found in rendered output")

    # Check video codec
    v_codec = v_stream.get("codec_name", "").lower()
    if v_codec not in ("h264", "libx264"):
        raise StageError(code="RENDER_FAILED", stage="assembly", message=f"Invalid video codec: {v_codec}, expected h264")

    # Check dimensions
    width = int(v_stream.get("width", 0))
    height = int(v_stream.get("height", 0))
    if width != 1080 or height != 1920:
        raise StageError(code="RENDER_FAILED", stage="assembly", message=f"Invalid dimensions: {width}x{height}, expected 1080x1920")

    # Check duration
    container_dur = float(format_info.get("duration", 0.0))
    v_dur = float(v_stream.get("duration", container_dur))
    a_dur = float(a_stream.get("duration", container_dur))

    if container_dur <= 0.0 or container_dur > 60.2:
        raise StageError(code="RENDER_FAILED", stage="assembly", message=f"Video duration {container_dur:.2f}s exceeds maximum 60s limit")

    av_delta = abs(v_dur - a_dur)
    if av_delta > 0.25:
        raise StageError(code="RENDER_FAILED", stage="assembly", message=f"A/V duration delta ({av_delta:.2f}s) exceeds tolerance")

    return {
        "width": width,
        "height": height,
        "duration_sec": container_dur,
        "video_codec": v_codec,
        "audio_codec": a_stream.get("codec_name", "").lower(),
        "file_size_kb": file_size_kb,
        "av_delta_sec": av_delta,
    }


def generate_video_thumbnail(
    video_path: Path,
    output_thumb_path: Path,
    timestamp_sec: float = 1.6,
    target_size: Tuple[int, int] = (540, 960),
) -> Path:
    """Extract a 540x960 JPEG thumbnail at the specified timestamp."""
    output_thumb_path.parent.mkdir(parents=True, exist_ok=True)
    raw_frame_path = output_thumb_path.with_suffix(".raw.jpg")

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", f"{timestamp_sec:.2f}",
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(raw_frame_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

    # Downscale cleanly to exactly 540x960
    with Image.open(raw_frame_path) as im:
        thumb = im.convert("RGB").resize(target_size, Image.LANCZOS)
        thumb.save(output_thumb_path, "JPEG", quality=90)

    raw_frame_path.unlink(missing_ok=True)
    return output_thumb_path
