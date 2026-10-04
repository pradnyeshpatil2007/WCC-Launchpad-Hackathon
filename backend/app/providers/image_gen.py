"""Image generation provider using Pollinations.ai Flux API (Amended per user directive)."""

import urllib.parse
from typing import Optional
from app.config import get_settings
from app.core.http_client import LoggedHttpClient


def harden_prompt(raw_prompt: str, softened: bool = False) -> str:
    """Harden the image generation prompt with negative keywords and style tokens."""
    if softened:
        base = f"{raw_prompt}, simple clear photographic composition, vertical 9:16 portrait orientation"
    else:
        base = f"{raw_prompt}, 9:16 vertical portrait, highly detailed, cinematic lighting, photorealistic, professional photography"

    # Enforce no text/logos rule
    hardened = f"{base}, no text, no letters, no logos, no watermark, no split screens, no borders"
    return hardened


class PollinationsImageGen:
    """Free Flux image generation via Pollinations.ai API."""

    def __init__(self, http_client: Optional[LoggedHttpClient] = None):
        self.settings = get_settings()
        self.http_client = http_client or LoggedHttpClient(
            timeout=float(self.settings.IMAGE_GEN_TIMEOUT_SECONDS)
        )

    async def generate_image(
        self,
        prompt: str,
        job_id: str = "_system",
        beat_key: str = "b00",
        attempt: int = 1,
    ) -> Optional[bytes]:
        """Generate a 9:16 portrait image (1080x1920) via Pollinations Flux GET request."""
        clean_prompt = harden_prompt(prompt, softened=(attempt > 1))
        encoded_prompt = urllib.parse.quote(clean_prompt)
        url = (
            f"https://gen.pollinations.ai/image/{encoded_prompt}"
            f"?width=1080&height=1920&model=flux&nologo=true"
        )

        try:
            resp = await self.http_client.request(
                method="GET",
                url=url,
                kind="image_gen",
                provider="pollinations",
                label=f"flux_{beat_key}",
                job_id=job_id,
                attempt=attempt,
                timeout=float(self.settings.IMAGE_GEN_TIMEOUT_SECONDS),
            )
            if resp.status_code == 200 and len(resp.content) > 1000:
                return resp.content
            return None
        except Exception:
            return None
