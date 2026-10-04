"""Domain models and validation for educational video scripts (Doc 3 §6.1)."""

import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


def count_words(text: str) -> int:
    """Canonical word counter for AutoShorts.
    Used by domain validator, prompt builder, and test assertions.
    """
    if not text:
        return 0
    words = re.findall(r"[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*", text)
    return len(words)


FORBIDDEN_NARRATION_PATTERNS = [
    (re.compile(r"\[.*?\]"), "bracketed stage directions"),
    (re.compile(r"\(.*?\)"), "parenthetical notes"),
    (re.compile(r"https?://\S+"), "URLs"),
    (re.compile(r"#\w+"), "hashtags"),
    (re.compile(r"^[A-Za-z0-9\s]+:\s*"), "speaker labels"),
    (re.compile(r"[*_~`]"), "markdown formatting"),
]


class VisualBeat(BaseModel):
    narration: str = Field(min_length=12, max_length=240)
    image_prompt: str = Field(min_length=60, max_length=500)
    stock_queries: List[str] = Field(min_length=3, max_length=6)

    @field_validator("narration")
    @classmethod
    def validate_beat_narration(cls, v: str) -> str:
        v = v.strip()
        for pat, desc in FORBIDDEN_NARRATION_PATTERNS:
            if pat.search(v):
                raise ValueError(f"Narration contains forbidden {desc}: '{v}'")

        w_count = count_words(v)
        if not (4 <= w_count <= 25):
            raise ValueError(f"Visual beat narration must be 4-25 words, got {w_count}: '{v}'")
        return v

    @field_validator("stock_queries")
    @classmethod
    def validate_stock_queries(cls, v: List[str]) -> List[str]:
        cleaned = []
        for q in v:
            q_clean = q.strip().lower()
            q_clean = re.sub(r"[^\w\s]", "", q_clean)
            words = q_clean.split()
            if not (1 <= len(words) <= 4):
                raise ValueError(f"Stock query '{q}' must be 1-4 words, got {len(words)}")
            if q_clean not in cleaned:
                cleaned.append(q_clean)

        if len(cleaned) < 3:
            raise ValueError(f"Must have at least 3 distinct stock queries, got {len(cleaned)}")
        return cleaned


class Scene(BaseModel):
    emphasis_text: str = Field(min_length=2, max_length=28)
    beats: List[VisualBeat] = Field(min_length=2, max_length=3)

    @property
    def narration(self) -> str:
        return " ".join(b.narration.strip() for b in self.beats)

    @property
    def word_count(self) -> int:
        return count_words(self.narration)

    @field_validator("emphasis_text")
    @classmethod
    def validate_emphasis(cls, v: str) -> str:
        v = v.strip()
        words = count_words(v)
        if words > 4:
            raise ValueError(f"Emphasis text must be 1-4 words, got {words}: '{v}'")
        return v


class Script(BaseModel):
    title: str = Field(min_length=6, max_length=60)
    scenes: List[Scene] = Field(min_length=5, max_length=8)

    @property
    def total_narration(self) -> str:
        return " ".join(s.narration for s in self.scenes)

    @property
    def total_words(self) -> int:
        return count_words(self.total_narration)

    @model_validator(mode="after")
    def validate_budget(self) -> "Script":
        total = self.total_words
        if not (120 <= total <= 140):
            delta = 120 - total if total < 120 else total - 140
            direction = "increase" if total < 120 else "reduce"
            raise ValueError(
                f"Total spoken script word count must be between 120 and 140 words. "
                f"Current total is {total} words. Please {direction} by {abs(delta)} words."
            )
        return self
