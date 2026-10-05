"""Isolated render worker process: compositing shots, transitions, overlays, captions, and FFmpeg x264 CRF 16 pipe."""

import json
import math
import multiprocessing as mp
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageOps

from app.domain.timeline_models import InsetCallout, Shot, Timeline, TransitionType
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

        # Pre-load master images for all shots, normalized to 1.25x motion master (1350x2400)
        master_w = int(timeline.width * 1.25)
        master_h = int(timeline.height * 1.25)
        master_images: Dict[int, Image.Image] = {}
        for shot in timeline.shots:
            img_p = job_dir / shot.image_file
            if img_p.exists():
                try:
                    with Image.open(img_p) as raw_im:
                        raw_im = raw_im.convert("RGB")
                        w, h = raw_im.size
                        aspect = w / h
                        target_aspect = 9.0 / 16.0
                        if aspect > target_aspect:
                            crop_w = int(h * target_aspect)
                            left = (w - crop_w) // 2
                            cropped = raw_im.crop((left, 0, left + crop_w, h))
                        else:
                            crop_h = int(w / target_aspect)
                            top = (h - crop_h) // 2
                            cropped = raw_im.crop((0, top, w, top + crop_h))
                        master_images[shot.shot_index] = cropped.resize((master_w, master_h), Image.LANCZOS)
                except Exception:
                    master_images[shot.shot_index] = Image.new("RGB", (master_w, master_h), (20, 24, 30))
            else:
                master_images[shot.shot_index] = Image.new("RGB", (master_w, master_h), (20, 24, 30))

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

        # Pre-render Inset Callout cards (Picture-in-Picture context stickers)
        prerendered_callouts: List[Tuple[InsetCallout, Image.Image]] = []
        for callout in getattr(timeline, "inset_callouts", []):
            c_path = job_dir / callout.image_file
            if c_path.exists():
                try:
                    with Image.open(c_path) as raw_c:
                        raw_c = raw_c.convert("RGBA")
                        fitted_c = ImageOps.fit(raw_c, (callout.width - 16, callout.height - 16), method=Image.Resampling.LANCZOS)
                    card = Image.new("RGBA", (callout.width, callout.height), (0, 0, 0, 0))
                    draw_c = ImageDraw.Draw(card)
                    draw_c.rounded_rectangle([(0, 0), (callout.width - 1, callout.height - 1)], radius=18, fill=(10, 16, 28, 240), outline=(254, 215, 102, 230), width=3)
                    mask_c = Image.new("L", (callout.width - 16, callout.height - 16), 0)
                    mask_draw = ImageDraw.Draw(mask_c)
                    mask_draw.rounded_rectangle([(0, 0), (callout.width - 17, callout.height - 17)], radius=12, fill=255)
                    card.paste(fitted_c, (8, 8), mask_c)
                    # Pill label
                    pill_text = callout.title[:20]
                    p_w = max(130, len(pill_text) * 12 + 20)
                    draw_c.rounded_rectangle([(callout.width - p_w - 18, 16), (callout.width - 18, 50)], radius=10, fill=(15, 23, 42, 230), outline=(254, 215, 102, 240), width=2)
                    draw_c.text((callout.width - p_w - 6, 22), pill_text, fill=(254, 215, 102, 255))
                    prerendered_callouts.append((callout, card))
                except Exception:
                    pass

        # Launch FFmpeg pipe with stderr directed to file to avoid OS pipe deadlock
        stderr_log_path = output_path.with_suffix(".ffmpeg.log")
        fade_out_start = max(0.0, timeline.duration_sec - 0.25)
        from app.config import get_settings
        settings = get_settings()
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
            "-preset", settings.VIDEO_PRESET,
            "-crf", str(settings.VIDEO_CRF),
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
                    # Blending transition with smooth S-curve
                    raw_p = max(0.0, min(1.0, (cur_time - trans_start) / trans_sec))
                    blend_p = raw_p * raw_p * (3.0 - 2.0 * raw_p)

                    next_master = master_images.get(next_shot.shot_index)
                    # Continuous motion into transition
                    next_rel_t = cur_time - next_shot.start_sec
                    next_frame = render_shot_frame(next_master, next_shot, next_rel_t, (timeline.width, timeline.height))

                    if cur_shot.transition_type == TransitionType.CROSSFADE:
                        base_frame = Image.blend(base_frame, next_frame, blend_p)
                    elif cur_shot.transition_type == TransitionType.ZOOM_DISSOLVE:
                        zoom_scale = 1.0 + (1.0 - blend_p) * 0.04
                        w, h = timeline.width, timeline.height
                        crop_w = int(w / zoom_scale)
                        crop_h = int(h / zoom_scale)
                        left = (w - crop_w) // 2
                        top = (h - crop_h) // 2
                        zoomed_next = next_frame.crop((left, top, left + crop_w, top + crop_h)).resize((w, h), Image.BILINEAR)
                        base_frame = Image.blend(base_frame, zoomed_next, blend_p)
                    elif cur_shot.transition_type == TransitionType.SOFT_PUSH:
                        push_offset = int((1.0 - blend_p) * 40)
                        w, h = timeline.width, timeline.height
                        pushed_next = Image.new("RGB", (w, h), (0, 0, 0))
                        pushed_next.paste(next_frame, (push_offset, 0))
                        base_frame = Image.blend(base_frame, pushed_next, blend_p)
                    elif cur_shot.transition_type == TransitionType.DIP_LIGHT:
                        lift = math.sin(blend_p * math.pi) * 0.12
                        blended = Image.blend(base_frame, next_frame, blend_p)
                        if lift > 0.01:
                            from PIL import ImageEnhance
                            base_frame = ImageEnhance.Brightness(blended).enhance(1.0 + lift)
                        else:
                            base_frame = blended
                    else:
                        base_frame = Image.blend(base_frame, next_frame, blend_p)

            # 2. Composite combined ambient overlays (vignette + caption scrim)
            base_frame.paste(combined_ambient, (0, 0), combined_ambient)

            # 3. Composite emphasis badge
            badge_res = badge_renderer.get_frame_overlay(cur_time)
            if badge_res:
                badge_img, bx, by = badge_res
                base_frame.paste(badge_img, (bx, by), badge_img)

            # 4. Composite active Inset Callout (PiP context card)
            for c_info, c_card in prerendered_callouts:
                if c_info.start_sec <= cur_time <= c_info.end_sec:
                    t_rel = cur_time - c_info.start_sec
                    rem = c_info.end_sec - cur_time
                    card_alpha = min(1.0, max(0.0, min(t_rel / 0.22, rem / 0.25)))
                    if card_alpha < 0.98:
                        faded_c = c_card.copy()
                        faded_c.putalpha(faded_c.getchannel("A").point(lambda p: int(p * card_alpha)))
                        base_frame.paste(faded_c, (c_info.x, c_info.y), faded_c)
                    else:
                        base_frame.paste(c_card, (c_info.x, c_info.y), c_card)
                    break

            # 5. Composite dynamic pop caption page with active highlight
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
