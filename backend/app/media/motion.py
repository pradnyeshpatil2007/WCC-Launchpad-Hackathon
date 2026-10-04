"""Ken Burns motion engine: sub-pixel float crop boxes, smoothstep easing, and organic handheld drift."""

import math
from typing import Tuple
from PIL import Image

from app.domain.timeline_models import MotionPreset, Shot


def smoothstep(t: float) -> float:
    """Standard smoothstep easing: 3*t^2 - 2*t^3."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def ease_in_out_cubic(t: float) -> float:
    """Cubic ease-in-out for smooth camera acceleration and deceleration."""
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 4.0 * t * t * t
    else:
        return 1.0 - math.pow(-2.0 * t + 2.0, 3) / 2.0


def lerp(a: float, b: float, p: float) -> float:
    """Linear interpolation between scalar values."""
    return a + (b - a) * p


def lerp2(a: Tuple[float, float], b: Tuple[float, float], p: float) -> Tuple[float, float]:
    """Linear interpolation between 2D coordinate tuples."""
    return (a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p)


def get_organic_drift(t_sec: float, seed_val: int) -> Tuple[float, float]:
    """Low-amplitude (<= 2px), low-frequency organic handheld drift (sum of two sines)."""
    phase1 = (seed_val * 17.13) % (2 * math.pi)
    phase2 = (seed_val * 31.47) % (2 * math.pi)
    
    # 0.4 Hz and 0.25 Hz low-frequency sine waves
    dx = 1.4 * math.sin(2.0 * math.pi * 0.4 * t_sec + phase1) + 0.6 * math.sin(2.0 * math.pi * 0.2 * t_sec + phase2)
    dy = 1.2 * math.cos(2.0 * math.pi * 0.35 * t_sec + phase2) + 0.6 * math.sin(2.0 * math.pi * 0.18 * t_sec + phase1)
    return dx, dy


def compute_shot_motion(
    preset: MotionPreset,
    focal_norm: Tuple[float, float],
    is_reframe: bool = False,
    reframe_index: int = 0,
) -> Tuple[float, float, Tuple[float, float], Tuple[float, float]]:
    """Compute scale0, scale1, center0, center1 for a shot based on preset and focal point.
    
    Returns:
        (scale0, scale1, center0_norm, center1_norm)
    """
    fx, fy = focal_norm
    # Clamp focal point away from extreme edges to avoid clipping
    fx = max(0.25, min(0.75, fx))
    fy = max(0.25, min(0.75, fy))

    if is_reframe:
        # Alternating wide (1.0) and punch-in (1.20) for reframe cuts
        if reframe_index % 2 == 1:
            scale0 = 1.15
            scale1 = 1.22
            c0 = (fx, fy)
            c1 = (fx + 0.02, fy - 0.02)
        else:
            scale0 = 1.00
            scale1 = 1.08
            c0 = (0.5, 0.5)
            c1 = (0.5 + (fx - 0.5) * 0.4, 0.5 + (fy - 0.5) * 0.4)
        return scale0, scale1, c0, c1

    if preset == MotionPreset.PUSH_IN:
        scale0 = 1.00
        scale1 = 1.14
        c0 = (0.5, 0.5)
        c1 = (0.5 + (fx - 0.5) * 0.5, 0.5 + (fy - 0.5) * 0.5)

    elif preset == MotionPreset.PULL_OUT:
        scale0 = 1.14
        scale1 = 1.00
        c0 = (0.5 + (fx - 0.5) * 0.5, 0.5 + (fy - 0.5) * 0.5)
        c1 = (0.5, 0.5)

    elif preset == MotionPreset.DRIFT_LEFT_UP:
        scale0 = 1.02
        scale1 = 1.10
        c0 = (0.54, 0.54)
        c1 = (0.47, 0.47)

    elif preset == MotionPreset.DRIFT_RIGHT_DOWN:
        scale0 = 1.10
        scale1 = 1.02
        c0 = (0.47, 0.47)
        c1 = (0.53, 0.53)

    elif preset == MotionPreset.DIAGONAL_PUSH:
        scale0 = 1.00
        scale1 = 1.15
        c0 = (0.48, 0.52)
        c1 = (0.52 + (fx - 0.5) * 0.3, 0.48 + (fy - 0.5) * 0.3)

    elif preset == MotionPreset.ARC_PAN:
        scale0 = 1.05
        scale1 = 1.12
        c0 = (0.47, 0.50)
        c1 = (0.53, 0.50)

    else:
        scale0 = 1.00
        scale1 = 1.08
        c0 = (0.5, 0.5)
        c1 = (fx, fy)

    return scale0, scale1, c0, c1


def render_shot_frame(
    master_image: Image.Image,
    shot: Shot,
    rel_time_sec: float,
    target_size: Tuple[int, int] = (1080, 1920),
) -> Image.Image:
    """Render a single frame of a shot using float crop box and Lanczos resampling."""
    norm_t = 0.0
    if shot.duration_sec > 0:
        norm_t = max(0.0, min(1.0, rel_time_sec / shot.duration_sec))

    # Smoothstep easing
    p = ease_in_out_cubic(norm_t)

    # Arc pan curvature
    if shot.motion_preset == MotionPreset.ARC_PAN:
        # Add perpendicular arc offset
        arc_offset = math.sin(norm_t * math.pi) * 0.02
        c_base = lerp2(shot.center0, shot.center1, p)
        cx_norm = c_base[0]
        cy_norm = c_base[1] - arc_offset
    else:
        cx_norm, cy_norm = lerp2(shot.center0, shot.center1, p)

    scale = lerp(shot.scale0, shot.scale1, p)

    orig_w, orig_h = master_image.size
    target_w, target_h = target_size

    # Source crop dimensions in master pixel coordinates
    crop_w = orig_w / scale
    crop_h = orig_h / scale

    # Organic handheld drift in pixels
    drift_x, drift_y = get_organic_drift(rel_time_sec, shot.shot_index)

    # Center in master pixel coordinates
    center_px_x = cx_norm * orig_w + drift_x
    center_px_y = cy_norm * orig_h + drift_y

    # Calculate float crop box (left, top, right, bottom)
    left = center_px_x - crop_w / 2.0
    top = center_px_y - crop_h / 2.0
    right = left + crop_w
    bottom = top + crop_h

    # Clamp float crop box inside master dimensions
    if left < 0:
        right += (0 - left)
        left = 0.0
    if right > orig_w:
        left -= (right - orig_w)
        right = float(orig_w)
    if top < 0:
        bottom += (0 - top)
        top = 0.0
    if bottom > orig_h:
        top -= (bottom - orig_h)
        bottom = float(orig_h)

    # Ensure box is valid
    left = max(0.0, min(orig_w - 10, left))
    top = max(0.0, min(orig_h - 10, top))
    right = min(float(orig_w), max(left + 10, right))
    bottom = min(float(orig_h), max(top + 10, bottom))

    crop_box = (left, top, right, bottom)

    # Sub-pixel accurate Lanczos resize
    frame = master_image.resize(target_size, Image.LANCZOS, box=crop_box)
    return frame
