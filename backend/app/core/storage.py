"""Filesystem storage and atomic write utilities (Doc 3 §5.2)."""

import json
import os
from pathlib import Path
from typing import Any
from app.config import get_settings


def atomic_write_bytes(target_path: Path, data: bytes) -> None:
    """Atomically write binary data to a file using temp file and rename."""
    target_path = Path(target_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")

    with tmp_path.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp_path, target_path)


def atomic_write_json(target_path: Path, data: Any, indent: int = 2) -> None:
    """Atomically write serializable JSON to a file."""
    json_bytes = json.dumps(data, indent=indent, default=str).encode("utf-8")
    atomic_write_bytes(target_path, json_bytes)


def get_job_storage_dir(job_id: str) -> Path:
    """Return and create the storage layout for a job."""
    settings = get_settings()
    base = settings.resolved_media_dir / "jobs" / job_id
    for sub in ["stages", "audio", "images", "previews", "output", "tmp"]:
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base
