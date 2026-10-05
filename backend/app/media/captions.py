"""High-DPI dynamic pop captions renderer with active-word highlight, stroke, shadow, and 2x supersampling."""

import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.config import get_settings
from app.domain.assets import WordTiming
from app.domain.timeline_models import CaptionPage, CaptionWord


# Typography styling constants
FONT_SIZE = 64
STROKE_WIDTH = 5
SUPERSAMPLE = 2  # Render at 2x for crisp anti-aliasing
TEXT_FILL_COLOR = (255, 255, 255, 255)  # Crisp white
TEXT_STROKE_COLOR = (15, 15, 18, 255)   # Rich dark charcoal stroke
HIGHLIGHT_FILL_COLOR = (254, 218, 106, 255)  # Vibrant warm golden yellow
HIGHLIGHT_STROKE_COLOR = (18, 15, 8, 255)
SHADOW_COLOR = (0, 0, 0, 160)
SHADOW_OFFSET = (3 * SUPERSAMPLE, 4 * SUPERSAMPLE)


def get_caption_font(size: int = FONT_SIZE) -> ImageFont.FreeTypeFont:
    """Load bundled OFL font from backend/assets/fonts/."""
    settings = get_settings()
    font_path = settings.resolved_font_dir / "Montserrat-Variable.ttf"
    if not font_path.exists():
        font_path = settings.resolved_font_dir / "Inter-Variable.ttf"
    
    scaled_size = size * SUPERSAMPLE
    try:
        return ImageFont.truetype(str(font_path), scaled_size)
    except Exception:
        return ImageFont.load_default()


def build_caption_pages_from_timings(
    scene_timings: List[Tuple[int, float, List[WordTiming]]],
    min_page_duration: float = 0.45,
) -> List[CaptionPage]:
    """Group spoken word timings into 2-4 word caption pages breaking at punctuation and line lengths."""
    pages: List[CaptionPage] = []
    page_counter = 0

    for s_idx, scene_start_sec, words in scene_timings:
        if not words:
            continue

        curr_words: List[CaptionWord] = []
        
        for w in words:
            abs_start = round(scene_start_sec + w.start, 3)
            abs_end = round(scene_start_sec + w.end, 3)
            curr_words.append(CaptionWord(text=w.text, start_sec=abs_start, end_sec=abs_end))

            ends_with_punct = any(w.text.endswith(p) for p in [".", ",", "!", "?", ";", ":"])
            is_full = len(curr_words) >= 4
            is_good_break = len(curr_words) >= 3 and ends_with_punct

            if is_full or is_good_break:
                p_start = curr_words[0].start_sec
                p_end = max(p_start + min_page_duration, curr_words[-1].end_sec)
                
                # Split words into 1 or 2 lines (max 18 chars per line)
                lines = _format_lines([cw.text for cw in curr_words])
                pages.append(
                    CaptionPage(
                        page_index=page_counter,
                        scene_index=s_idx,
                        words=list(curr_words),
                        start_sec=p_start,
                        end_sec=p_end,
                        lines=lines,
                    )
                )
                page_counter += 1
                curr_words = []

        if curr_words:
            p_start = curr_words[0].start_sec
            p_end = max(p_start + min_page_duration, curr_words[-1].end_sec)
            lines = _format_lines([cw.text for cw in curr_words])
            pages.append(
                CaptionPage(
                    page_index=page_counter,
                    scene_index=s_idx,
                    words=list(curr_words),
                    start_sec=p_start,
                    end_sec=p_end,
                    lines=lines,
                )
            )
            page_counter += 1

    return pages


def _format_lines(word_texts: List[str]) -> List[str]:
    """Format 2-4 words into at most 2 lines, keeping lines <= 18 chars if possible."""
    if len(word_texts) <= 2:
        return [" ".join(word_texts)]
    
    # Try 2 words per line
    mid = (len(word_texts) + 1) // 2
    l1 = " ".join(word_texts[:mid])
    l2 = " ".join(word_texts[mid:])
    return [l1, l2]


class PreRenderedCaptionPage:
    """Caches pre-rendered RGBA layers for each word highlight state on a page."""

    def __init__(self, page: CaptionPage, font: ImageFont.FreeTypeFont, width: int = 1080):
        self.page = page
        self.font = font
        self.width = width
        # State: -1 = no highlight (all white), 0..N = word N highlighted
        self.variant_images: Dict[int, Image.Image] = {}
        self._prerender_variants()

    def _prerender_variants(self):
        """Render 2x supersampled variants for each highlighted word."""
        canvas_w = self.width * SUPERSAMPLE
        canvas_h = 320 * SUPERSAMPLE  # generous height for 2 lines of captions

        for active_word_idx in range(-1, len(self.page.words)):
            img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # We lay out lines centered
            lines = self.page.lines
            line_height = int(FONT_SIZE * 1.35 * SUPERSAMPLE)
            total_text_h = len(lines) * line_height
            start_y = (canvas_h - total_text_h) // 2

            # Map words to their line positions
            w_idx = 0
            for line_idx, line_str in enumerate(lines):
                line_words = line_str.split()
                # Compute total line width
                total_line_w = 0
                word_boxes = []
                space_w = draw.textlength(" ", font=self.font)

                for lw in line_words:
                    w_w = draw.textlength(lw, font=self.font)
                    word_boxes.append((lw, w_w, w_idx))
                    w_idx += 1
                
                line_text_w = sum(wb[1] for wb in word_boxes) + space_w * (len(word_boxes) - 1)
                cur_x = (canvas_w - line_text_w) / 2.0
                cur_y = start_y + line_idx * line_height

                for word_text, word_w, word_global_idx in word_boxes:
                    is_active = (word_global_idx == active_word_idx)
                    fill_col = HIGHLIGHT_FILL_COLOR if is_active else TEXT_FILL_COLOR
                    stroke_col = HIGHLIGHT_STROKE_COLOR if is_active else TEXT_STROKE_COLOR
                    stroke_w = (STROKE_WIDTH + 1) * SUPERSAMPLE if is_active else STROKE_WIDTH * SUPERSAMPLE

                    # Draw drop shadow
                    sx, sy = cur_x + SHADOW_OFFSET[0], cur_y + SHADOW_OFFSET[1]
                    draw.text(
                        (sx, sy),
                        word_text,
                        font=self.font,
                        fill=SHADOW_COLOR,
                        stroke_width=stroke_w,
                        stroke_fill=SHADOW_COLOR,
                    )

                    # Draw text with stroke
                    draw.text(
                        (cur_x, cur_y),
                        word_text,
                        font=self.font,
                        fill=fill_col,
                        stroke_width=stroke_w,
                        stroke_fill=stroke_col,
                    )

                    cur_x += word_w + space_w

            # Downsample to 1x with high-quality Lanczos for anti-aliasing
            target_1x_size = (self.width, int(canvas_h / SUPERSAMPLE))
            downsampled = img.resize(target_1x_size, Image.LANCZOS)
            self.variant_images[active_word_idx] = downsampled

    def get_frame_overlay(self, current_time: float) -> Optional[Tuple[Image.Image, int, int]]:
        """Returns (overlay_image, paste_x, paste_y) with entrance/exit animation and active word."""
        if current_time < self.page.start_sec or current_time > self.page.end_sec:
            return None

        # Determine which word is currently active
        active_idx = -1
        for idx, cw in enumerate(self.page.words):
            if cw.start_sec <= current_time <= cw.end_sec:
                active_idx = idx
                break
        if active_idx == -1 and self.page.words and current_time >= self.page.words[0].start_sec:
            # Latch to latest spoken word on this page
            active_idx = len(self.page.words) - 1

        variant_img = self.variant_images.get(active_idx, self.variant_images.get(-1))
        if variant_img is None:
            return None

        # Entrance rise animation (160ms)
        elapsed = current_time - self.page.start_sec
        y_offset = 0
        alpha_mult = 1.0

        if elapsed < 0.16:
            p = elapsed / 0.16
            # Ease out cubic rise of 14px
            rise_p = 1.0 - math.pow(1.0 - p, 3)
            y_offset = int((1.0 - rise_p) * 14)
            alpha_mult = p

        # Exit fade (100ms)
        remaining = self.page.end_sec - current_time
        if remaining < 0.10:
            alpha_mult = min(alpha_mult, remaining / 0.10)

        # Baseline position: centered around y = 1230
        paste_y = 1230 - (variant_img.height // 2) + y_offset
        paste_x = 0

        if alpha_mult < 0.98:
            # Apply alpha fade using precomputed LUT
            faded = variant_img.copy()
            r, g, b, a = faded.split()
            lut = [int(i * alpha_mult) for i in range(256)]
            a = a.point(lut)
            faded.putalpha(a)
            return faded, paste_x, paste_y

        return variant_img, paste_x, paste_y
