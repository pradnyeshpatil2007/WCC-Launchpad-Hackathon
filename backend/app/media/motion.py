"""Ken Burns motion engine: sub-pixel float crop boxes, smoothstep easing, and organic handheld drift."""

import math
from typing import Tuple
from PIL import Image

from app.domain.timeline_models import MotionPreset, Shot


def smoothstep(t: float) -> float:
    """Standard smoothstep easing: 3*t^2 - 2*t^3."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def ease_in_out_quintic(t: float) -> float:
    """Quintic ease-in-out (smoothstep2: 6*t^5 - 15*t^4 + 10*t^3) for ultra-smooth camera velocity."""
    # Allow small negative or >1 extrapolation for seamless transition momentum
    sign = 1.0 if t >= 0 else -1.0
    abs_t = min(1.2, abs(t))
    if abs_t <= 1.0:
        val = abs_t * abs_t * abs_t * (abs_t * (abs_t * 6.0 - 15.0) + 10.0)
    else:
        # Smooth linear continuation beyond 1.0
        val = 1.0 + (abs_t - 1.0)
    return sign * val if t < 0 else val


def ease_in_out_cubic(t: float) -> float:
    """Cubic ease-in-out for smooth camera acceleration and deceleration."""
    return ease_in_out_quintic(t)


def lerp(a: float, b: float, p: float) -> float:
    """Linear interpolation between scalar values."""
    return a + (b - a) * p


def lerp2(a: Tuple[float, float], b: Tuple[float, float], p: float) -> Tuple[float, float]:
    """Linear interpolation between 2D coordinate tuples."""
    return (a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p)


def get_organic_drift(t_sec: float, seed_val: int) -> Tuple[float, float]:
    """Low-amplitude (<= 1.5px), low-frequency organic handheld drift (sum of two sines)."""
    phase1 = (seed_val * 17.13) % (2 * math.pi)
    phase2 = (seed_val * 31.47) % (2 * math.pi)
    
    # 0.35 Hz and 0.20 Hz low-frequency sine waves
    dx = 1.1 * math.sin(2.0 * math.pi * 0.35 * t_sec + phase1) + 0.4 * math.sin(2.0 * math.pi * 0.18 * t_sec + phase2)
    dy = 0.9 * math.cos(2.0 * math.pi * 0.30 * t_sec + phase2) + 0.4 * math.sin(2.0 * math.pi * 0.15 * t_sec + phase1)
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
    # Clamp focal point safely inside visible frame
    fx = max(0.30, min(0.70, fx))
    fy = max(0.30, min(0.70, fy))

    if is_reframe:
        # Dynamic reframe variations to avoid repetitive framing
        cycle = reframe_index % 3
        if cycle == 1:
            # Medium close-up on focal region pushing gently
            scale0 = 1.16
            scale1 = 1.24
            c0 = (fx, fy)
            c1 = (fx + 0.03, fy - 0.02)
        elif cycle == 2:
            # Pull-back from subject to context
            scale0 = 1.20
            scale1 = 1.06
            c0 = (fx, fy)
            c1 = (0.50, 0.50)
        else:
            # Gentle wide with subtle horizontal drift
            scale0 = 1.02
            scale1 = 1.10
            c0 = (0.46, 0.50)
            c1 = (0.54, 0.50)
        return scale0, scale1, c0, c1

    if preset == MotionPreset.PUSH_IN:
        # Cinematic focus push: starts wide and glides into focal anchor
        scale0 = 1.02
        scale1 = 1.18
        c0 = (0.50, 0.50)
        c1 = (0.50 + (fx - 0.50) * 0.65, 0.50 + (fy - 0.50) * 0.65)

    elif preset == MotionPreset.PULL_OUT:
        # Context reveal: starts framed on detail, pulls back smoothly
        scale0 = 1.20
        scale1 = 1.04
        c0 = (0.50 + (fx - 0.50) * 0.65, 0.50 + (fy - 0.50) * 0.65)
        c1 = (0.50, 0.50)

    elif preset == MotionPreset.PAN_LEFT:
        # Horizontal sweep left across the scene
        scale0 = 1.08
        scale1 = 1.12
        c0 = (min(0.68, fx + 0.12), fy)
        c1 = (max(0.32, fx - 0.10), fy)

    elif preset == MotionPreset.PAN_RIGHT:
        # Horizontal sweep right across the scene
        scale0 = 1.08
        scale1 = 1.12
        c0 = (max(0.32, fx - 0.10), fy)
        c1 = (min(0.68, fx + 0.12), fy)

    elif preset == MotionPreset.TILT_UP:
        # Vertical pedestal/tilt upward (ideal for 9:16 mobile framing)
        scale0 = 1.10
        scale1 = 1.16
        c0 = (fx, min(0.66, fy + 0.14))
        c1 = (fx, max(0.34, fy - 0.10))

    elif preset == MotionPreset.TILT_DOWN:
        # Vertical pedestal/tilt downward
        scale0 = 1.14
        scale1 = 1.08
        c0 = (fx, max(0.34, fy - 0.12))
        c1 = (fx, min(0.66, fy + 0.10))

    elif preset == MotionPreset.DRIFT_LEFT_UP:
        # Dynamic diagonal upward glide
        scale0 = 1.04
        scale1 = 1.16
        c0 = (min(0.65, fx + 0.08), min(0.65, fy + 0.08))
        c1 = (max(0.35, fx - 0.07), max(0.35, fy - 0.07))

    elif preset == MotionPreset.DRIFT_RIGHT_DOWN:
        # Dynamic diagonal downward glide
        scale0 = 1.16
        scale1 = 1.05
        c0 = (max(0.35, fx - 0.07), max(0.35, fy - 0.07))
        c1 = (min(0.65, fx + 0.08), min(0.65, fy + 0.08))

    elif preset == MotionPreset.DIAGONAL_PUSH:
        # Diagonal motion combined with gentle zoom
        scale0 = 1.02
        scale1 = 1.20
        c0 = (0.46, 0.54)
        c1 = (0.50 + (fx - 0.50) * 0.5, 0.50 + (fy - 0.50) * 0.5)

    elif preset == MotionPreset.ARC_PAN:
        # Smooth curved sweeping pan
        scale0 = 1.06
        scale1 = 1.14
        c0 = (max(0.34, fx - 0.10), fy)
        c1 = (min(0.66, fx + 0.10), fy)

    else:
        scale0 = 1.02
        scale1 = 1.12
        c0 = (0.50, 0.50)
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
        # Allow continuous velocity during transition overlap
        norm_t = max(-0.25, min(1.25, rel_time_sec / shot.duration_sec))

    # Organic Quintic Easing
    p = ease_in_out_quintic(norm_t)

    # Arc pan curvature
    if shot.motion_preset == MotionPreset.ARC_PAN:
        arc_offset = math.sin(max(0.0, min(1.0, norm_t)) * math.pi) * 0.025
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
