"""Image generation provider using Pollinations.ai API with multi-model failover."""

import urllib.parse
from typing import Optional
from app.config import get_settings
from app.core.http_client import LoggedHttpClient


def harden_prompt(raw_prompt: str, softened: bool = False) -> str:
    """Harden the image generation prompt with style tokens and vertical framing."""
    if softened:
        base = f"{raw_prompt}, simple clear photographic composition, vertical 9:16 portrait orientation"
    else:
        base = f"{raw_prompt}, 9:16 vertical portrait, highly detailed, cinematic lighting, photorealistic, professional photography"

    # Enforce quality tokens
    hardened = f"{base}, high resolution, 8k quality, centered framing"
    return hardened


class PollinationsImageGen:
    """Free image generation via Pollinations.ai API with multi-model sequential failover."""

    def __init__(self, http_client: Optional[LoggedHttpClient] = None):
        self.settings = get_settings()
        self.http_client = http_client or LoggedHttpClient(
            timeout=float(self.settings.IMAGE_GEN_TIMEOUT_SECONDS)
        )
        # Sequential models to try: sana (NVIDIA/MIT), default open-source, turbo (SDXL Turbo)
        self.models_to_try = ["sana", "", "turbo"]

    async def generate_image(
        self,
        prompt: str,
        job_id: str = "_system",
        beat_key: str = "b00",
        attempt: int = 1,
    ) -> Optional[bytes]:
        """Generate a 9:16 portrait image via Pollinations API with model failover."""
        clean_prompt = harden_prompt(prompt, softened=(attempt > 1))
        encoded_prompt = urllib.parse.quote(clean_prompt)

        for model_idx, model_name in enumerate(self.models_to_try):
            model_param = f"&model={model_name}" if model_name else ""
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=720&height=1280{model_param}"
            model_label = model_name or "default"

            try:
                resp = await self.http_client.request(
                    method="GET",
                    url=url,
                    kind="image_gen",
                    provider="pollinations",
                    label=f"ai_{model_label}_{beat_key}",
                    job_id=job_id,
                    attempt=attempt + model_idx,
                    timeout=float(self.settings.IMAGE_GEN_TIMEOUT_SECONDS),
                )
                if resp.status_code == 200 and len(resp.content) > 5000:
                    return resp.content
            except Exception:
                continue

        return None
