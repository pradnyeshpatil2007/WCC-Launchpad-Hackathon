"""Visual overlays: global vignette, caption legibility scrim, scene emphasis badges, and top progress bar."""

import math
from typing import Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.config import get_settings
from app.domain.timeline_models import EmphasisOverlay


def create_global_vignette(width: int = 1080, height: int = 1920) -> Image.Image:
    """Precompute a smooth cinematic vignette mask (darkening at outer edges and corners)."""
    # Generate at half res and upsample for buttery smooth gradient
    hw, hh = width // 2, height // 2
    vignette = Image.new("L", (hw, hh), 0)
    draw = ImageDraw.Draw(vignette)

    cx, cy = hw / 2.0, hh / 2.0
    max_radius = math.hypot(cx, cy)

    # Concentric radial fade
    for r in range(int(max_radius), 0, -8):
        norm_r = r / max_radius
        if norm_r > 0.45:
            # Alpha increases quadratically towards corners up to ~110 (out of 255)
            alpha = int(110 * math.pow((norm_r - 0.45) / 0.55, 1.8))
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=alpha)

    # Blur heavily for seamless gradient
    blurred = vignette.filter(ImageFilter.GaussianBlur(radius=28))
    full_mask = blurred.resize((width, height), Image.BILINEAR)

    # Black color image with vignette alpha
    res = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    res.putalpha(full_mask)
    return res


def create_bottom_scrim(width: int = 1080, height: int = 1920) -> Image.Image:
    """Precompute a soft gradient scrim behind the caption region (y: 1050 to 1420)."""
    scrim = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(scrim)

    scrim_start_y = 1040
    scrim_peak_y = 1240
    scrim_end_y = 1420

    for y in range(scrim_start_y, scrim_end_y):
        if y < scrim_peak_y:
            t = (y - scrim_start_y) / (scrim_peak_y - scrim_start_y)
            alpha = int(95 * (t * t))
        else:
            t = (scrim_end_y - y) / (scrim_end_y - scrim_peak_y)
            alpha = int(95 * (t * t))
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))

    return scrim


class EmphasisBadgeRenderer:
    """Pre-renders stylish glassmorphic emphasis badge overlays for each scene."""

    def __init__(self, overlays: list[EmphasisOverlay], width: int = 1080):
        self.overlays = overlays
        self.width = width
        self.badges: Dict[int, Image.Image] = {}
        self._prerender_all()

    def _prerender_all(self):
        settings = get_settings()
        font_path = settings.resolved_font_dir / "Montserrat-Variable.ttf"
        if not font_path.exists():
            font_path = settings.resolved_font_dir / "Inter-Variable.ttf"
        
        font = ImageFont.truetype(str(font_path), 40)

        for ov in self.overlays:
            text = ov.text.upper()
            dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
            text_len = dummy_draw.textlength(text, font=font)
            
            pad_x = 42
            pad_y = 18
            badge_w = int(text_len + pad_x * 2)
            badge_h = 76

            badge = Image.new("RGBA", (badge_w, badge_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(badge)

            # Translucent dark pill background with subtle blur feel
            draw.rounded_rectangle(
                [(0, 0), (badge_w - 1, badge_h - 1)],
                radius=38,
                fill=(18, 20, 26, 210),
                outline=(255, 255, 255, 70),
                width=2,
            )

            # Golden accent dot on left
            dot_r = 5
            dot_cx = pad_x - 14
            dot_cy = badge_h // 2
            draw.ellipse(
                [(dot_cx - dot_r, dot_cy - dot_r), (dot_cx + dot_r, dot_cy + dot_r)],
                fill=(254, 218, 106, 255),
            )

            # Clean white text
            tx = pad_x + 4
            ty = (badge_h - 40) // 2 - 2
            draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 255))

            self.badges[ov.scene_index] = badge

    def get_frame_overlay(self, current_time: float) -> Optional[Tuple[Image.Image, int, int]]:
        """Returns (badge_image, paste_x, paste_y) with entrance pop and exit fade."""
        for ov in self.overlays:
            if ov.start_sec <= current_time <= ov.end_sec:
                badge = self.badges.get(ov.scene_index)
                if not badge:
                    continue

                duration = ov.end_sec - ov.start_sec
                elapsed = current_time - ov.start_sec
                remaining = ov.end_sec - current_time

                alpha = 1.0
                scale = 1.0

                # Entrance pop (200ms): scale from 0.85 to 1.0, fade in
                if elapsed < 0.20:
                    t = elapsed / 0.20
                    scale = 0.85 + 0.15 * math.sin(t * math.pi / 2)
                    alpha = t

                # Exit fade (180ms)
                if remaining < 0.18:
                    alpha = min(alpha, remaining / 0.18)

                img_to_paste = badge
                if scale < 0.99:
                    nw = int(badge.width * scale)
                    nh = int(badge.height * scale)
                    img_to_paste = badge.resize((nw, nh), Image.BILINEAR)

                if alpha < 0.98:
                    faded = img_to_paste.copy()
                    r, g, b, a = faded.split()
                    a = a.point(lambda p: int(p * alpha))
                    faded.putalpha(a)
                    img_to_paste = faded

                paste_x = (self.width - img_to_paste.width) // 2
                paste_y = 410 - (img_to_paste.height // 2)
                return img_to_paste, paste_x, paste_y

        return None


def draw_progress_bar(frame: Image.Image, progress: float, width: int = 1080) -> None:
    """Draw a sleek 4px golden progress bar inside the top safe zone (y = 28)."""
    p = max(0.0, min(1.0, progress))
    bar_w = int(width * p)
    if bar_w <= 0:
        return

    draw = ImageDraw.Draw(frame)
    # Background track (translucent white)
    draw.rectangle([(0, 28), (width, 32)], fill=(255, 255, 255, 30))
    # Active fill (bright amber gold)
    draw.rectangle([(0, 28), (bar_w, 32)], fill=(254, 218, 106, 230))
