"""Image validation, saliency focal-point detection, smart cover crop, and perceptual hashing."""

import io
import math
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
from PIL import Image, ImageFilter, ImageOps
import imagehash


class ImageEvaluationResult:
    def __init__(
        self,
        accepted: bool,
        image: Optional[Image.Image] = None,
        focal: Tuple[float, float] = (0.5, 0.5),
        phash_str: str = "",
        reason: Optional[str] = None,
    ):
        self.accepted = accepted
        self.image = image
        self.focal = focal
        self.phash = phash_str
        self.reason = reason


def compute_saliency_focal_point(im: Image.Image) -> Tuple[float, float]:
    """Calculate the saliency centroid (normalized x, y) using gradient energy on a blurred downsample."""
    try:
        # Resize to small grayscale thumbnail for fast computation
        thumb = im.convert("L").resize((160, 284), Image.BILINEAR)
        blurred = thumb.filter(ImageFilter.GaussianBlur(radius=2))
        arr = np.asarray(blurred, dtype=np.float32)

        # Sobel gradients
        gx = np.abs(np.diff(arr, axis=1)[:, :-1])
        gy = np.abs(np.diff(arr, axis=0)[:-1, :])
        min_h = min(gx.shape[0], gy.shape[0])
        min_w = min(gx.shape[1], gy.shape[1])
        energy = gx[:min_h, :min_w] + gy[:min_h, :min_w]

        total_energy = np.sum(energy)
        if total_energy < 1e-4:
            return (0.5, 0.5)

        y_indices, x_indices = np.indices(energy.shape)
        centroid_x = float(np.sum(x_indices * energy) / total_energy) / energy.shape[1]
        centroid_y = float(np.sum(y_indices * energy) / total_energy) / energy.shape[0]

        # Clamp safely within [0.15, 0.85]
        cx = max(0.15, min(0.85, centroid_x))
        cy = max(0.15, min(0.85, centroid_y))
        return (round(cx, 3), round(cy, 3))
    except Exception:
        return (0.5, 0.5)


def smart_cover_crop_9_16(im: Image.Image, focal: Tuple[float, float]) -> Image.Image:
    """Intelligently crop the image to 9:16 aspect ratio anchored around the focal point."""
    w, h = im.size
    target_aspect = 9.0 / 16.0  # 0.5625
    current_aspect = w / h

    if abs(current_aspect - target_aspect) < 0.01:
        return im

    if current_aspect > target_aspect:
        # Image is wider than 9:16 -> crop width
        new_w = int(h * target_aspect)
        cx = int(focal[0] * w)
        left = max(0, min(cx - new_w // 2, w - new_w))
        right = left + new_w
        return im.crop((left, 0, right, h))
    else:
        # Image is taller than 9:16 -> crop height
        new_h = int(w / target_aspect)
        cy = int(focal[1] * h)
        top = max(0, min(cy - new_h // 2, h - new_h))
        bottom = top + new_h
        return im.crop((0, top, w, bottom))


def evaluate_and_process_image(
    raw_bytes: bytes,
    source: str,
    existing_phashes: list[str],
) -> ImageEvaluationResult:
    """Evaluate image against acceptance gates, compute focal point, crop to 9:16, and check de-dup."""
    # 1. Clean decode and orientation
    try:
        test_im = Image.open(io.BytesIO(raw_bytes))
        test_im.verify()
        im = Image.open(io.BytesIO(raw_bytes))
        im = ImageOps.exif_transpose(im)
        if im.mode != "RGB":
            im = im.convert("RGB")
    except Exception as e:
        return ImageEvaluationResult(False, reason=f"Image decode failed: {e}")

    orig_w, orig_h = im.size
    if orig_w < 400 or orig_h < 400:
        return ImageEvaluationResult(False, reason=f"Resolution too small: {orig_w}x{orig_h}")

    # 2. Check flat/blank frames (luminance standard deviation)
    gray_arr = np.asarray(im.convert("L").resize((64, 114), Image.BILINEAR), dtype=np.float32)
    std_dev = float(np.std(gray_arr))
    if std_dev < 12.0:
        return ImageEvaluationResult(False, reason=f"Image luminance variance too flat ({std_dev:.1f} < 12.0)")

    # 3. Area retention check when cropped to 9:16
    target_aspect = 9.0 / 16.0
    current_aspect = orig_w / orig_h
    if current_aspect > target_aspect:
        retained_ratio = (orig_h * target_aspect) / orig_w
    else:
        retained_ratio = (orig_w / target_aspect) / orig_h

    if retained_ratio < 0.50:
        return ImageEvaluationResult(False, reason=f"9:16 crop retains only {retained_ratio:.1%} of area (< 50%)")

    # 4. Focal point and Smart Crop
    focal = compute_saliency_focal_point(im)
    cropped = smart_cover_crop_9_16(im, focal)
    cw, ch = cropped.size

    # Check minimum crop resolution (allow AI generated 576x1024 / 720x1280 to pass)
    min_w = 480 if source in ("generated", "pollinations") else 640
    min_h = 850 if source in ("generated", "pollinations") else 1130
    if cw < min_w or ch < min_h:
        return ImageEvaluationResult(False, reason=f"Cropped resolution too low: {cw}x{ch} (min {min_w}x{min_h})")

    # 5. Upscale limit check
    max_upscale = 2.0 if source in ("generated", "pollinations") else (1.5 if source == "pixabay" else 1.8)
    scale_w = 1080.0 / cw
    scale_h = 1920.0 / ch
    scale_req = max(scale_w, scale_h)
    if scale_req > max_upscale:
        return ImageEvaluationResult(False, reason=f"Requires {scale_req:.2f}x upscale, exceeding {max_upscale}x limit")

    # Normalize image dimensions to prevent memory exhaustion and ensure high-DPI quality
    if cw < 1080 or ch < 1920:
        final_im = cropped.resize((1080, 1920), Image.LANCZOS)
        final_im = final_im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=3))
    elif cw > 1350 or ch > 2400:
        # Downscale massive camera RAW photos (e.g. 6768x12032 from stock) to master 1.25x motion size
        final_im = cropped.resize((1350, 2400), Image.LANCZOS)
    else:
        final_im = cropped

    # 6. Perceptual Hash de-duplication
    current_hash = imagehash.phash(final_im)
    current_hash_str = str(current_hash)

    for prev_h_str in existing_phashes:
        try:
            prev_h = imagehash.hex_to_hash(prev_h_str)
            distance = current_hash - prev_h
            if distance < 8:
                return ImageEvaluationResult(False, reason=f"Perceptual duplicate detected (Hamming distance {distance} < 8)")
        except Exception:
            pass

    return ImageEvaluationResult(
        accepted=True,
        image=final_im,
        focal=focal,
        phash_str=current_hash_str,
    )


def generate_preview(im: Image.Image, output_path: Path) -> Path:
    """Generate and save a 270x480 JPEG preview image."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    preview = im.resize((270, 480), Image.LANCZOS)
    preview.save(output_path, "JPEG", quality=85, optimize=True)
    return output_path
