"""Configuration and settings loader for AutoShorts."""

from pathlib import Path
import shutil
from typing import List, Optional
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- API KEYS ---
    GEMINI_API_KEY: SecretStr = Field(default=SecretStr(""))
    PEXELS_API_KEY: SecretStr = Field(default=SecretStr(""))
    PIXABAY_API_KEY: SecretStr = Field(default=SecretStr(""))

    # --- LLM GATEWAY ---
    LLM_MODEL_SEQUENCE: str = (
        "gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.6-flash,gemini-3.7-flash,gemini-3.8-flash"
    )
    LLM_REQUEST_TIMEOUT_SECONDS: int = 60
    LLM_MAX_FULL_CYCLES: int = 3
    LLM_TOTAL_DEADLINE_SECONDS: int = 240
    LLM_BACKOFF_BASE_SECONDS: float = 2.0
    LLM_BACKOFF_MAX_SECONDS: float = 20.0
    LLM_TEMPERATURE_RESEARCH: float = 0.7

    # --- IMAGE GENERATION (Pollinations.ai Flux) ---
    IMAGE_GEN_ASPECT_RATIO: str = "9:16"
    IMAGE_GEN_TIMEOUT_SECONDS: int = 90
    IMAGE_GEN_CONCURRENCY: int = 3
    IMAGE_GEN_MAX_ATTEMPTS_PER_BEAT: int = 2

    # --- STOCK FALLBACK ---
    STOCK_PROVIDER_ORDER: str = "pexels,pixabay"
    STOCK_CANDIDATES_PER_QUERY: int = 15
    STOCK_RELEVANCE_JUDGE: bool = True
    MIN_IMAGES_PER_SCENE_HARD: int = 1
    TARGET_IMAGES_PER_SCENE: int = 3

    # --- TTS ---
    TTS_VOICE: str = "en-US-AndrewMultilingualNeural"
    TTS_FALLBACK_VOICE: str = "en-US-AriaNeural"
    TTS_RATE: str = "+0%"
    TTS_CONCURRENCY: int = 3
    TTS_MAX_RATE_BUMP_PERCENT: int = 15

    # --- SCRIPT CONSTRAINTS ---
    SCRIPT_MIN_WORDS: int = 120
    SCRIPT_MAX_WORDS: int = 140
    SCRIPT_MIN_SCENES: int = 5
    SCRIPT_MAX_SCENES: int = 8
    SCRIPT_MAX_REPAIR_ATTEMPTS: int = 3
    MAX_SCRIPT_TIGHTEN_LOOPS: int = 2

    # --- VIDEO OUTPUT ---
    VIDEO_WIDTH: int = 1080
    VIDEO_HEIGHT: int = 1920
    VIDEO_FPS: int = 30
    VIDEO_MAX_SECONDS: float = 60.0
    VIDEO_LEAD_IN_SECONDS: float = 0.4
    VIDEO_TAIL_SECONDS: float = 0.6
    VIDEO_PRESET: str = "slow"
    VIDEO_CRF: int = 16
    VIDEO_AUDIO_BITRATE: str = "192k"
    VIDEO_LOUDNESS_LUFS: float = -16.0

    # --- JOBS ---
    MAX_CONCURRENT_JOBS: int = 2
    MAX_CONCURRENT_RENDERS: int = 1
    JOB_CREATE_RATE_LIMIT_PER_MINUTE: int = 10

    # --- PATHS ---
    LOG_DIR: str = "./logs/api_calls"
    APP_LOG_DIR: str = "./logs/app"
    MEDIA_DIR: str = "./storage"
    DB_PATH: str = "./storage/autoshorts.db"
    FONT_DIR: str = "./backend/assets/fonts"
    LOG_FAIL_CLOSED: bool = True

    # --- SERVER ---
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    @property
    def llm_models(self) -> List[str]:
        return [m.strip() for m in self.LLM_MODEL_SEQUENCE.split(",") if m.strip()]

    @property
    def stock_providers(self) -> List[str]:
        return [p.strip().lower() for p in self.STOCK_PROVIDER_ORDER.split(",") if p.strip()]

    def is_secret_set(self, secret: SecretStr) -> bool:
        val = secret.get_secret_value().strip()
        return bool(val and not val.startswith("PASTE_") and not val.startswith("SET_"))

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent

    @property
    def resolved_log_dir(self) -> Path:
        p = Path(self.LOG_DIR)
        return p if p.is_absolute() else (self.project_root / p).resolve()

    @property
    def resolved_app_log_dir(self) -> Path:
        p = Path(self.APP_LOG_DIR)
        return p if p.is_absolute() else (self.project_root / p).resolve()

    @property
    def resolved_media_dir(self) -> Path:
        p = Path(self.MEDIA_DIR)
        return p if p.is_absolute() else (self.project_root / p).resolve()

    @property
    def resolved_db_path(self) -> Path:
        p = Path(self.DB_PATH)
        return p if p.is_absolute() else (self.project_root / p).resolve()

    @property
    def resolved_font_dir(self) -> Path:
        p = Path(self.FONT_DIR)
        return p if p.is_absolute() else (self.project_root / p).resolve()

    def validate_preflight_paths_and_binaries(self, fail_fast_keys: bool = False) -> List[str]:
        """Validate system requirements: binaries, fonts, directories, and optionally keys."""
        errors: List[str] = []

        if not shutil.which("ffmpeg"):
            errors.append("FFmpeg executable not found on PATH.")
        if not shutil.which("ffprobe"):
            errors.append("ffprobe executable not found on PATH.")

        # Font validation
        font_path = self.resolved_font_dir
        if not font_path.exists():
            errors.append(f"Font directory does not exist: {font_path}")
        else:
            font_files = list(font_path.glob("*.ttf")) + list(font_path.glob("*.otf"))
            if not font_files:
                errors.append(f"No .ttf or .otf font files found in {font_path}")

        # Directory writability check
        for p in [self.resolved_log_dir, self.resolved_app_log_dir, self.resolved_media_dir, self.resolved_db_path.parent]:
            try:
                p.mkdir(parents=True, exist_ok=True)
                test_file = p / ".write_test"
                test_file.write_text("ok", encoding="utf-8")
                test_file.unlink()
            except Exception as e:
                errors.append(f"Directory {p} is not writable: {e}")

        if not self.llm_models:
            errors.append("LLM_MODEL_SEQUENCE must contain at least one model identifier.")

        if fail_fast_keys and not self.is_secret_set(self.GEMINI_API_KEY):
            errors.append("GEMINI_API_KEY is not set or contains placeholder text.")

        return errors


_settings: Optional[Settings] = None


def get_settings(reload: bool = False) -> Settings:
    global _settings
    if _settings is None or reload:
        _settings = Settings()
    return _settings
