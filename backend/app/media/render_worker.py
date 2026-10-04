"""Isolated render worker process: compositing shots, transitions, overlays, captions, and FFmpeg x264 CRF 16 pipe."""

import json
import math
import multiprocessing as mp
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image

from app.domain.timeline_models import Shot, Timeline, TransitionType
from app.media.captions import PreRenderedCaptionPage, get_caption_font
from app.media.motion import render_shot_frame
from app.media.overlays import (
    EmphasisBadgeRenderer,
    create_bottom_scrim,
    create_global_vignette,
    draw_progress_bar,
)


def run_render_worker(
    timeline_dict: Dict[str, Any],
    job_storage_dir_str: str,
    output_video_path_str: str,
    progress_queue: mp.Queue,
) -> None:
    """Worker entry point executed inside an isolated spawned process."""
    try:
        timeline = Timeline.model_validate(timeline_dict)
        job_dir = Path(job_storage_dir_str)
        output_path = Path(output_video_path_str)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        audio_path = job_dir / timeline.narration_audio_file
        if not audio_path.exists():
            raise FileNotFoundError(f"Narration audio not found: {audio_path}")

        total_frames = int(math.ceil(timeline.duration_sec * timeline.fps))

        # Pre-load master images for all shots
        master_images: Dict[int, Image.Image] = {}
        for shot in timeline.shots:
            img_p = job_dir / shot.image_file
            if img_p.exists():
                try:
                    master_images[shot.shot_index] = Image.open(img_p).convert("RGB")
                except Exception:
                    master_images[shot.shot_index] = Image.new("RGB", (timeline.width, timeline.height), (20, 24, 30))
            else:
                master_images[shot.shot_index] = Image.new("RGB", (timeline.width, timeline.height), (20, 24, 30))

        # Precompute overlays and typography
        vignette_mask = create_global_vignette(timeline.width, timeline.height)
        scrim_mask = create_bottom_scrim(timeline.width, timeline.height)
        combined_ambient = Image.new("RGBA", (timeline.width, timeline.height), (0, 0, 0, 0))
        combined_ambient.paste(vignette_mask, (0, 0), vignette_mask)
        combined_ambient.paste(scrim_mask, (0, 0), scrim_mask)

        font = get_caption_font(size=64)

        # Pre-render caption pages
        prerendered_pages = [
            PreRenderedCaptionPage(p, font=font, width=timeline.width)
            for p in timeline.caption_pages
        ]

        # Pre-render emphasis badges
        badge_renderer = EmphasisBadgeRenderer(timeline.emphasis_overlays, width=timeline.width)

        # Launch FFmpeg pipe with stderr directed to file to avoid OS pipe deadlock
        stderr_log_path = output_path.with_suffix(".ffmpeg.log")
        fade_out_start = max(0.0, timeline.duration_sec - 0.25)
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{timeline.width}x{timeline.height}",
            "-pix_fmt", "rgb24",
            "-r", str(timeline.fps),
            "-i", "-",  # Video from stdin pipe
            "-i", str(audio_path),  # Audio input
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "16",
            "-profile:v", "high",
            "-level", "4.2",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-maxrate", "20M",
            "-bufsize", "40M",
            "-x264-params", "aq-mode=3:deblock=-1,-1",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-af", f"afade=t=in:st=0:d=0.04,afade=t=out:st={fade_out_start:.3f}:d=0.25",
            "-shortest",
            str(output_path),
        ]

        stderr_file = open(stderr_log_path, "wb")
        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=stderr_file,
        )

        last_report_time = 0.0

        for frame_idx in range(total_frames):
            cur_time = frame_idx / float(timeline.fps)

            # 1. Determine active shot(s) and handle transition blending
            active_shot_idx = 0
            for idx, s in enumerate(timeline.shots):
                if s.start_sec <= cur_time <= s.end_sec or idx == len(timeline.shots) - 1:
                    active_shot_idx = idx
                    if s.start_sec <= cur_time <= s.end_sec:
                        break

            cur_shot = timeline.shots[active_shot_idx]
            rel_t = cur_time - cur_shot.start_sec
            master_img = master_images.get(cur_shot.shot_index)
            base_frame = render_shot_frame(master_img, cur_shot, rel_t, (timeline.width, timeline.height))

            # Check if we are in transition zone with next shot
            next_shot_idx = active_shot_idx + 1
            if next_shot_idx < len(timeline.shots):
                next_shot = timeline.shots[next_shot_idx]
                trans_sec = cur_shot.transition_sec
                trans_start = cur_shot.end_sec - trans_sec

                if cur_time >= trans_start:
                    # Blending transition
                    trans_p = max(0.0, min(1.0, (cur_time - trans_start) / trans_sec))
                    next_master = master_images.get(next_shot.shot_index)
                    next_rel_t = cur_time - next_shot.start_sec
                    next_frame = render_shot_frame(next_master, next_shot, next_rel_t, (timeline.width, timeline.height))

                    if cur_shot.transition_type == TransitionType.CROSSFADE:
                        base_frame = Image.blend(base_frame, next_frame, trans_p)
                    elif cur_shot.transition_type == TransitionType.SOFT_PUSH:
                        # Soft push: next frame slides in while blending
                        push_offset = int((1.0 - trans_p) * 60)
                        blended = Image.blend(base_frame, next_frame, trans_p)
                        base_frame = blended
                    elif cur_shot.transition_type == TransitionType.DIP_LIGHT:
                        # Brightness lift at midpoint
                        lift = math.sin(trans_p * math.pi) * 0.15
                        blended = Image.blend(base_frame, next_frame, trans_p)
                        if lift > 0.02:
                            r, g, b = blended.split()
                            r = r.point(lambda p: min(255, int(p * (1.0 + lift))))
                            g = g.point(lambda p: min(255, int(p * (1.0 + lift))))
                            b = b.point(lambda p: min(255, int(p * (1.0 + lift))))
                            base_frame = Image.merge("RGB", (r, g, b))
                        else:
                            base_frame = blended

            # 2. Composite combined ambient overlays (vignette + caption scrim)
            base_frame.paste(combined_ambient, (0, 0), combined_ambient)

            # 3. Composite emphasis badge
            badge_res = badge_renderer.get_frame_overlay(cur_time)
            if badge_res:
                badge_img, bx, by = badge_res
                base_frame.paste(badge_img, (bx, by), badge_img)

            # 4. Composite dynamic pop caption page with active highlight
            for page in prerendered_pages:
                cap_res = page.get_frame_overlay(cur_time)
                if cap_res:
                    cap_img, cx, cy = cap_res
                    base_frame.paste(cap_img, (cx, cy), cap_img)
                    break

            # 5. Draw top progress bar
            draw_progress_bar(base_frame, cur_time / timeline.duration_sec, width=timeline.width)

            # Pipe RGB raw bytes to FFmpeg
            raw_bytes = base_frame.tobytes()
            proc.stdin.write(raw_bytes)

            # Report progress over queue (throttled to ~4 times/sec)
            now = time.time()
            if now - last_report_time >= 0.25 or frame_idx == total_frames - 1:
                last_report_time = now
                progress_queue.put({
                    "status": "rendering",
                    "frame_idx": frame_idx + 1,
                    "total_frames": total_frames,
                    "percent": round(((frame_idx + 1) / total_frames) * 100.0, 1),
                    "current_shot": active_shot_idx + 1,
                    "total_shots": len(timeline.shots),
                })

        proc.stdin.close()
        proc.wait()
        stderr_file.close()

        if proc.returncode != 0:
            stderr_text = stderr_log_path.read_text(encoding="utf-8", errors="replace") if stderr_log_path.exists() else "Unknown"
            raise RuntimeError(f"FFmpeg render worker failed with code {proc.returncode}: {stderr_text[-500:]}")

        stderr_log_path.unlink(missing_ok=True)
        progress_queue.put({"status": "completed", "percent": 100.0})

    except Exception as e:
        progress_queue.put({"status": "error", "error": str(e)})
        raise
