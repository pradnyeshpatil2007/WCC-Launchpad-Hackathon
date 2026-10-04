"""Assembly Agent (Node 3): orchestrates timeline construction, spawned render worker, progress monitoring, and verification."""

import asyncio
import multiprocessing as mp
from pathlib import Path
import time
from typing import Any, Callable, Dict, Optional, Tuple

from app.config import get_job_storage_dir, get_settings
from app.core.errors import StageError
from app.domain.assets import VisualManifest, VoiceManifest
from app.domain.script import Script
from app.domain.timeline_models import Timeline
from app.media.probe import generate_video_thumbnail, verify_video_quality
from app.media.render_worker import run_render_worker
from app.media.timeline import build_timeline
from app.core.storage import atomic_write_json


class AssemblyAgent:
    def __init__(self):
        self.settings = get_settings()

    async def execute(
        self,
        script: Script,
        voice: VoiceManifest,
        visuals: VisualManifest,
        job_id: str,
        event_cb: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Execute assembly stage: timeline construction, process-isolated rendering, and probing."""
        storage_dir = get_job_storage_dir(job_id)
        stages_dir = storage_dir / "stages"
        stages_dir.mkdir(parents=True, exist_ok=True)

        if event_cb:
            event_cb("substep.started", {"node": "assembly", "message": "Building shot timeline and motion curves"})

        # 1. Build shot timeline
        timeline = build_timeline(
            script=script,
            voice=voice,
            visuals=visuals,
            job_id=job_id,
        )

        timeline_json_path = stages_dir / "timeline.json"
        atomic_write_json(timeline_json_path, timeline.model_dump())

        if event_cb:
            event_cb("substep.completed", {"node": "assembly", "durationMs": 50})
            event_cb("substep.started", {"node": "assembly", "message": "Rendering high-DPI video with x264 CRF 16"})

        output_video_path = storage_dir / "video.mp4"
        thumbnail_path = storage_dir / "thumbnail.jpg"

        # 2. Execute render worker in a spawned background process
        render_success = False
        attempt = 0
        max_attempts = 2

        while attempt < max_attempts and not render_success:
            attempt += 1
            render_success = await self._run_render_process(
                timeline=timeline,
                job_storage_dir=storage_dir,
                output_video_path=output_video_path,
                event_cb=event_cb,
            )

        if not render_success:
            raise StageError(
                code="RENDER_FAILED",
                stage="assembly",
                message="Video rendering failed after worker execution",
                retryable=False,
            )

        # 3. Quality verification using ffprobe
        probe_meta = verify_video_quality(output_video_path)

        # 4. Generate 540x960 thumbnail
        thumb_time = min(2.0, max(0.8, timeline.lead_in_sec + 1.2))
        generate_video_thumbnail(
            video_path=output_video_path,
            output_thumb_path=thumbnail_path,
            timestamp_sec=thumb_time,
        )

        # 5. Build assembly manifest and persist
        assembly_result = {
            "job_id": job_id,
            "video_file": str(output_video_path.relative_to(storage_dir)),
            "thumbnail_file": str(thumbnail_path.relative_to(storage_dir)),
            "duration_sec": probe_meta["duration_sec"],
            "width": probe_meta["width"],
            "height": probe_meta["height"],
            "fps": timeline.fps,
            "file_size_kb": probe_meta["file_size_kb"],
            "total_shots": len(timeline.shots),
            "total_caption_pages": len(timeline.caption_pages),
            "probe": probe_meta,
        }

        atomic_write_json(stages_dir / "assembly.json", assembly_result)

        if event_cb:
            event_cb("substep.completed", {"node": "assembly", "durationMs": 0})
            event_cb("media.video_ready", {
                "videoUrl": f"/api/media/{job_id}/video.mp4",
                "thumbnailUrl": f"/api/media/{job_id}/thumbnail.jpg",
                "durationSec": probe_meta["duration_sec"],
            })

        return assembly_result

    async def _run_render_process(
        self,
        timeline: Timeline,
        job_storage_dir: Path,
        output_video_path: Path,
        event_cb: Optional[Callable[[str, Dict[str, Any]], None]],
    ) -> bool:
        """Spawn isolated render worker process and track progress queue."""
        ctx = mp.get_context("spawn")
        progress_queue = ctx.Queue()

        timeline_data = timeline.model_dump()

        proc = ctx.Process(
            target=run_render_worker,
            args=(
                timeline_data,
                str(job_storage_dir),
                str(output_video_path),
                progress_queue,
            ),
        )

        proc.start()
        start_time = time.time()
        last_progress_event_time = 0.0

        try:
            while proc.is_alive():
                await asyncio.sleep(0.1)

                # Drain queue
                while not progress_queue.empty():
                    msg = progress_queue.get_nowait()
                    status = msg.get("status")

                    if status == "rendering":
                        now = time.time()
                        if now - last_progress_event_time >= 0.25:
                            last_progress_event_time = now
                            percent = msg.get("percent", 0.0)
                            frame_idx = msg.get("frame_idx", 0)
                            total_frames = msg.get("total_frames", 1)

                            elapsed = max(0.1, now - start_time)
                            fps = frame_idx / elapsed
                            remaining_frames = max(0, total_frames - frame_idx)
                            eta_sec = int(remaining_frames / fps) if fps > 0 else 0

                            if event_cb:
                                event_cb(
                                    "substep.progress",
                                    {
                                        "node": "assembly",
                                        "percent": percent,
                                        "fps": round(fps, 1),
                                        "etaSeconds": eta_sec,
                                        "currentShot": msg.get("current_shot", 1),
                                        "totalShots": msg.get("total_shots", 1),
                                    },
                                )

                    elif status == "error":
                        error_msg = msg.get("error", "Unknown worker error")
                        proc.join(timeout=2.0)
                        return False

                    elif status == "completed":
                        pass

            proc.join(timeout=5.0)
            return proc.exitcode == 0 and output_video_path.exists()

        except Exception as e:
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=3.0)
            return False
