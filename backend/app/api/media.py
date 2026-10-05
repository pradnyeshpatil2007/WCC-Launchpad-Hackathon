"""Media delivery router with HTTP Range (RFC 7233) partial content support for video seeking."""

import os
from pathlib import Path
import re
from typing import Optional, Tuple
from fastapi import APIRouter, HTTPException, Header, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse

from app.config import get_settings


router = APIRouter(prefix="/api/media", tags=["media"])


def parse_range_header(range_header: str, file_size: int) -> Tuple[int, int]:
    """Parse 'Range: bytes=start-end' header and return (start, end) byte indices."""
    match = re.match(r"^bytes=(\d*)-(\d*)$", range_header.strip())
    if not match:
        return 0, file_size - 1

    start_str, end_str = match.groups()
    if start_str and end_str:
        start = int(start_str)
        end = int(end_str)
    elif start_str:
        start = int(start_str)
        end = file_size - 1
    elif end_str:
        start = max(0, file_size - int(end_str))
        end = file_size - 1
    else:
        start = 0
        end = file_size - 1

    start = max(0, min(start, file_size - 1))
    end = max(start, min(end, file_size - 1))
    return start, end


@router.get("/{job_id}/scenes/{scene_index}/preview")
async def get_scene_preview(job_id: str, scene_index: int):
    """Serve scene storyboard preview JPEG with automatic fallback to beat image."""
    settings = get_settings()
    storage_dir = settings.resolved_media_dir / "jobs" / job_id
    preview_file = (storage_dir / "previews" / f"s{scene_index:02d}.jpg").resolve()
    if not preview_file.exists():
        # Fallback to beat image if preview hasn't been written
        preview_file = (storage_dir / "images" / f"s{scene_index:02d}_b00.jpg").resolve()
    if not preview_file.exists() or not preview_file.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene preview not yet available")
    return FileResponse(path=preview_file, media_type="image/jpeg")


@router.get("/{job_id}/{filename:path}")
async def get_media_file(
    job_id: str,
    filename: str,
    range: Optional[str] = Header(None),
):
    """Serve job media files (video.mp4, thumbnail.jpg, previews, audio) with HTTP Range support."""
    settings = get_settings()
    storage_dir = settings.resolved_media_dir / "jobs" / job_id
    file_path = (storage_dir / filename).resolve()

    # Security path traversal guard
    if not str(file_path).startswith(str(storage_dir.resolve())):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    file_size = file_path.stat().st_size
    content_type = "application/octet-stream"

    if filename.endswith(".mp4"):
        content_type = "video/mp4"
    elif filename.endswith((".jpg", ".jpeg")):
        content_type = "image/jpeg"
    elif filename.endswith(".png"):
        content_type = "image/png"
    elif filename.endswith(".wav"):
        content_type = "audio/wav"
    elif filename.endswith(".mp3"):
        content_type = "audio/mpeg"

    # Non-video or no-range requests: standard FileResponse
    if not range or not filename.endswith(".mp4"):
        return FileResponse(
            path=file_path,
            media_type=content_type,
            headers={"Accept-Ranges": "bytes"},
        )

    # HTTP Range 206 Partial Content handling for video seeking
    start, end = parse_range_header(range, file_size)
    chunk_length = end - start + 1

    def iterfile():
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = chunk_length
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_length),
        "Content-Type": content_type,
    }

    return StreamingResponse(
        iterfile(),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        headers=headers,
    )
