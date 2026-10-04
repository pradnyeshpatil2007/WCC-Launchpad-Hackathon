"""Startup preflight checks for LLM models, Pexels, Pixabay, and Edge-TTS (Doc 3 §4.3).

Logs all preflight calls under logs/api_calls/_system/ using LoggedHttpClient and LoggedEdgeTTS.
Never exposes secret values.
"""

import asyncio
from typing import Any, Dict, List
import httpx

from app.config import get_settings
from app.core.http_client import LoggedHttpClient
from app.providers.tts import LoggedEdgeTTS


class PreflightReport:
    def __init__(self):
        self.models_status: Dict[str, bool] = {}
        self.pexels_ok: bool = False
        self.pixabay_ok: bool = False
        self.edge_tts_ok: bool = False
        self.errors: List[str] = []

    @property
    def is_healthy(self) -> bool:
        # At least one model available, at least one stock provider or image gen, and TTS ok
        any_model = any(self.models_status.values())
        return any_model and self.edge_tts_ok

    @property
    def is_degraded(self) -> bool:
        any_model = any(self.models_status.values())
        all_models = all(self.models_status.values()) if self.models_status else False
        return (not all_models or not self.pexels_ok or not self.pixabay_ok) and self.is_healthy

    def to_health_dict(self) -> Dict[str, Any]:
        """Sanitized health output with booleans only (no secrets or provider detail)."""
        status = "ok"
        if not self.is_healthy:
            status = "down"
        elif self.is_degraded:
            status = "degraded"

        return {
            "status": status,
            "checks": {
                "llm_available": any(self.models_status.values()),
                "pexels_available": self.pexels_ok,
                "pixabay_available": self.pixabay_ok,
                "tts_available": self.edge_tts_ok,
            },
        }


async def run_preflight() -> PreflightReport:
    """Execute all startup preflight checks with live audit logging under _system."""
    settings = get_settings()
    report = PreflightReport()
    http_client = LoggedHttpClient(timeout=15.0)

    # 1. Probe Gemini models
    gemini_key = settings.GEMINI_API_KEY.get_secret_value()
    for model in settings.llm_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        headers = {"x-goog-api-key": gemini_key}
        try:
            resp = await http_client.request(
                method="GET",
                url=url,
                kind="llm_probe",
                provider="gemini",
                label=f"preflight_{model}",
                job_id="_system",
                model=model,
                headers=headers,
            )
            if resp.status_code == 200:
                report.models_status[model] = True
            else:
                report.models_status[model] = False
                report.errors.append(f"Model {model} returned HTTP {resp.status_code}")
        except Exception as e:
            report.models_status[model] = False
            report.errors.append(f"Model {model} probe failed: {e}")

    # 2. Probe Pexels
    pexels_key = settings.PEXELS_API_KEY.get_secret_value()
    if settings.is_secret_set(settings.PEXELS_API_KEY):
        try:
            resp = await http_client.request(
                method="GET",
                url="https://api.pexels.com/v1/search?query=nature&per_page=1",
                kind="stock_probe",
                provider="pexels",
                label="preflight_pexels",
                job_id="_system",
                headers={"Authorization": pexels_key},
            )
            report.pexels_ok = resp.status_code == 200
            if not report.pexels_ok:
                report.errors.append(f"Pexels probe returned HTTP {resp.status_code}")
        except Exception as e:
            report.pexels_ok = False
            report.errors.append(f"Pexels probe failed: {e}")
    else:
        report.pexels_ok = False
        report.errors.append("Pexels API key not configured")

    # 3. Probe Pixabay
    pixabay_key = settings.PIXABAY_API_KEY.get_secret_value()
    if settings.is_secret_set(settings.PIXABAY_API_KEY):
        try:
            resp = await http_client.request(
                method="GET",
                url=f"https://pixabay.com/api/?key={pixabay_key}&q=nature&per_page=3",
                kind="stock_probe",
                provider="pixabay",
                label="preflight_pixabay",
                job_id="_system",
            )
            report.pixabay_ok = resp.status_code == 200
            if not report.pixabay_ok:
                report.errors.append(f"Pixabay probe returned HTTP {resp.status_code}")
        except Exception as e:
            report.pixabay_ok = False
            report.errors.append(f"Pixabay probe failed: {e}")
    else:
        report.pixabay_ok = False
        report.errors.append("Pixabay API key not configured")

    # 4. Probe Edge-TTS
    tts = LoggedEdgeTTS(job_id="_system")
    try:
        audio, events, mode = await tts.synthesize(
            text="Startup preflight verification.",
            label="preflight_tts",
        )
        report.edge_tts_ok = bool(len(audio) > 0)
    except Exception as e:
        report.edge_tts_ok = False
        report.errors.append(f"Edge-TTS probe failed: {e}")

    await http_client.close()
    return report
