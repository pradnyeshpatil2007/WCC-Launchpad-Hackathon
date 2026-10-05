"""Timeline building: aligns visual beats with spoken word timings, splits shots > 4.5s, assigns motion and transitions."""

import hashlib
import random
from typing import Dict, List, Optional, Tuple

from app.config import get_settings
from app.domain.assets import VisualManifest, VoiceManifest
from app.domain.script import Script
from app.domain.timeline_models import (
    CaptionPage,
    EmphasisOverlay,
    InsetCallout,
    MotionPreset,
    Shot,
    Timeline,
    TransitionType,
)
from app.media.captions import build_caption_pages_from_timings
from app.media.motion import compute_shot_motion


def seed_from_job(job_id: str, index: int) -> int:
    """Generate a deterministic 32-bit integer seed from job_id and index."""
    raw = f"{job_id}_{index}".encode("utf-8")
    return int(hashlib.md5(raw).hexdigest()[:8], 16)


def build_timeline(
    script: Script,
    voice: VoiceManifest,
    visuals: VisualManifest,
    job_id: str,
    gap_duration: float = 0.12,
) -> Timeline:
    """Pure timeline constructor aligning voice, visuals, shot cuts, motion, captions, and overlays."""
    settings = get_settings()
    lead_in = settings.VIDEO_LEAD_IN_SECONDS
    tail = settings.VIDEO_TAIL_SECONDS
    target_w = settings.VIDEO_WIDTH
    target_h = settings.VIDEO_HEIGHT
    fps = settings.VIDEO_FPS

    # Compute global scene start times
    scene_starts: List[float] = []
    current_time = lead_in
    for s_idx, scene_audio in enumerate(voice.scenes):
        scene_starts.append(round(current_time, 3))
        current_time += scene_audio.duration_sec + gap_duration

    # Map scenes to images
    scene_images: Dict[int, List[Any]] = {}
    for sv in visuals.scenes:
        scene_images[sv.scene_index] = list(sv.images)

    # 1. Build initial raw beat windows from word timings
    # Each scene has beats. We divide scene audio duration across beats by word counts or explicit word timings.
    raw_shot_specs: List[Dict[str, Any]] = []

    for s_idx, s_audio in enumerate(voice.scenes):
        s_start = scene_starts[s_idx]
        s_end = s_start + s_audio.duration_sec
        images = scene_images.get(s_idx, [])
        scene_obj = script.scenes[s_idx] if s_idx < len(script.scenes) else None
        num_beats = len(scene_obj.beats) if scene_obj else 2

        # If we have word timings, locate boundaries for each beat
        words = s_audio.words
        total_words = len(words)

        beat_times: List[Tuple[float, float]] = []
        if total_words > 0 and scene_obj:
            # Group words according to beat word counts
            w_idx = 0
            for b_idx, beat in enumerate(scene_obj.beats):
                b_word_count = len(beat.narration.split())
                b_words = words[w_idx : w_idx + b_word_count]
                w_idx += b_word_count

                if b_words:
                    b_start = s_start + b_words[0].start
                    b_end = s_start + b_words[-1].end
                else:
                    # Proportionate estimate
                    b_start = s_start + (b_idx / num_beats) * s_audio.duration_sec
                    b_end = s_start + ((b_idx + 1) / num_beats) * s_audio.duration_sec
                beat_times.append((b_start, b_end))
        else:
            # Proportionate estimate
            for b_idx in range(num_beats):
                b_start = s_start + (b_idx / num_beats) * s_audio.duration_sec
                b_end = s_start + ((b_idx + 1) / num_beats) * s_audio.duration_sec
                beat_times.append((b_start, b_end))

        # Adjust consecutive beat windows to ensure contiguous coverage
        for b_idx in range(len(beat_times)):
            b_start = beat_times[b_idx][0]
            b_end = beat_times[b_idx + 1][0] if b_idx + 1 < len(beat_times) else s_end
            if b_idx == 0 and s_idx == 0:
                b_start = 0.0  # First window covers lead-in

            # Select primary image for this beat
            img_obj = images[b_idx % len(images)] if images else None
            extra_imgs = [img for i, img in enumerate(images) if i >= num_beats]

            raw_shot_specs.append({
                "scene_index": s_idx,
                "beat_index": b_idx,
                "beat_key": f"s{s_idx:02d}_b{b_idx:02d}",
                "start_sec": b_start,
                "end_sec": b_end,
                "image_obj": img_obj,
                "extra_imgs": extra_imgs,
            })

    # Extend last shot to audio end + tail
    if raw_shot_specs:
        raw_shot_specs[-1]["end_sec"] = voice.total_sec + tail

    # 2. Shot subdivision: Any shot duration > 4.5s is subdivided
    # Using extra stock images or reframe cuts
    final_shots: List[Shot] = []
    shot_counter = 0
    prev_preset: Optional[MotionPreset] = None

    all_presets = [
        MotionPreset.PUSH_IN,
        MotionPreset.PAN_LEFT,
        MotionPreset.PULL_OUT,
        MotionPreset.TILT_UP,
        MotionPreset.PAN_RIGHT,
        MotionPreset.DRIFT_LEFT_UP,
        MotionPreset.TILT_DOWN,
        MotionPreset.DRIFT_RIGHT_DOWN,
        MotionPreset.DIAGONAL_PUSH,
        MotionPreset.ARC_PAN,
    ]

    transition_cycle = [
        TransitionType.CROSSFADE,
        TransitionType.ZOOM_DISSOLVE,
        TransitionType.SOFT_PUSH,
        TransitionType.DIP_LIGHT,
        TransitionType.CROSSFADE,
        TransitionType.ZOOM_DISSOLVE,
    ]

    for spec in raw_shot_specs:
        s_idx = spec["scene_index"]
        b_key = spec["beat_key"]
        w_start = spec["start_sec"]
        w_end = spec["end_sec"]
        w_dur = w_end - w_start
        base_img = spec["image_obj"]
        extra_imgs = spec["extra_imgs"]

        if w_dur <= 4.5:
            num_sub_shots = 1
        elif w_dur <= 8.5:
            num_sub_shots = 2
        else:
            num_sub_shots = max(2, int(w_dur / 3.8) + 1)

        sub_dur = w_dur / num_sub_shots

        for sub_i in range(num_sub_shots):
            sub_start = round(w_start + sub_i * sub_dur, 3)
            sub_end = round(w_start + (sub_i + 1) * sub_dur, 3)
            if sub_i == num_sub_shots - 1:
                sub_end = round(w_end, 3)

            # Choose image: if we have extra stock images, use one; otherwise reframe the base image
            is_reframe = False
            cur_img = base_img
            if sub_i > 0:
                if extra_imgs:
                    cur_img = extra_imgs.pop(0)
                else:
                    is_reframe = True

            # Determine focal point
            focal = (0.5, 0.5)
            img_file = "images/placeholder.jpg"
            if cur_img:
                focal = cur_img.focal
                img_file = cur_img.file

            # Select motion preset deterministically with constraints
            rng = random.Random(seed_from_job(job_id, shot_counter))
            available = [p for p in all_presets if p != prev_preset]
            chosen_preset = rng.choice(available)
            prev_preset = chosen_preset

            scale0, scale1, c0, c1 = compute_shot_motion(
                preset=chosen_preset,
                focal_norm=focal,
                is_reframe=is_reframe,
                reframe_index=sub_i,
            )

            trans_type = transition_cycle[shot_counter % len(transition_cycle)]
            # 0.48s for inter-scene transitions, 0.38s for intra-scene cuts
            trans_sec = 0.48 if (sub_i == 0 and s_idx > 0) else 0.38

            final_shots.append(
                Shot(
                    shot_index=shot_counter,
                    scene_index=s_idx,
                    beat_key=b_key,
                    image_file=img_file,
                    start_sec=sub_start,
                    end_sec=sub_end,
                    duration_sec=round(sub_end - sub_start, 3),
                    motion_preset=chosen_preset,
                    scale0=round(scale0, 3),
                    scale1=round(scale1, 3),
                    center0=(round(c0[0], 3), round(c0[1], 3)),
                    center1=(round(c1[0], 3), round(c1[1], 3)),
                    transition_type=trans_type,
                    transition_sec=trans_sec,
                    is_reframe=is_reframe,
                )
            )
            shot_counter += 1

    # 3. Caption pages
    # Collect all words across all scenes
    caption_input: List[Tuple[int, float, List[Any]]] = []
    for s_idx, s_audio in enumerate(voice.scenes):
        s_start = scene_starts[s_idx]
        caption_input.append((s_idx, s_start, s_audio.words))

    caption_pages = build_caption_pages_from_timings(caption_input)

    # 4. Emphasis overlays and Inset Callouts
    emphasis_overlays: List[EmphasisOverlay] = []
    inset_callouts: List[InsetCallout] = []

    for s_idx, scene in enumerate(script.scenes):
        s_start = scene_starts[s_idx]
        s_dur = voice.scenes[s_idx].duration_sec
        ov_start = round(s_start + 0.15, 3)
        ov_dur = min(2.2, max(0.8, s_dur - 0.4))
        ov_end = round(ov_start + ov_dur, 3)

        emphasis_overlays.append(
            EmphasisOverlay(
                scene_index=s_idx,
                text=scene.emphasis_text,
                start_sec=ov_start,
                end_sec=ov_end,
            )
        )

        # Build Inset Callout if scene has extra visual assets and duration allows
        imgs = scene_images.get(s_idx, [])
        if len(imgs) >= 2 and s_dur >= 5.5:
            callout_img = imgs[1]
            c_start = round(s_start + 2.4, 3)
            c_dur = min(2.8, s_dur - 3.0)
            if c_dur >= 1.5:
                c_end = round(c_start + c_dur, 3)
                inset_callouts.append(
                    InsetCallout(
                        callout_id=f"pip_s{s_idx:02d}",
                        scene_index=s_idx,
                        image_file=callout_img.file,
                        title=scene.emphasis_text.upper(),
                        start_sec=c_start,
                        end_sec=c_end,
                        x=140,
                        y=420,
                        width=800,
                        height=460,
                    )
                )

    total_duration = round(voice.total_sec + tail, 3)

    return Timeline(
        duration_sec=total_duration,
        fps=fps,
        width=target_w,
        height=target_h,
        lead_in_sec=lead_in,
        tail_sec=tail,
        shots=final_shots,
        caption_pages=caption_pages,
        emphasis_overlays=emphasis_overlays,
        inset_callouts=inset_callouts,
        narration_audio_file="audio/narration.wav",
        seed=seed_from_job(job_id, 0),
    )
