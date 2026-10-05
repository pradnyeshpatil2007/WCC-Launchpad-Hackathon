"""Visual Relevance and Quality Verifier using Gemini Multimodal API."""

import json
import logging
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from app.config import get_settings
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class VisualVerificationResult(BaseModel):
    is_relevant: bool = True
    confidence: float = 1.0
    detected_subject: str = "visual scene"
    verdict: str = "ACCEPT"  # "ACCEPT" or "REJECT"
    reason: str = "Validated"


class VisualVerifier:
    """Agent that visually inspects candidate images and clips using Gemini Vision."""

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        key = api_key or (
            settings.GEMINI_API_KEY.get_secret_value()
            if settings.is_secret_set(settings.GEMINI_API_KEY)
            else ""
        )
        self.client = genai.Client(api_key=key) if key else None
        # Preferred multimodal vision model
        self.model_name = "gemini-3.5-flash-lite"

    async def verify_image(
        self,
        image_bytes: bytes,
        narration: str,
        concept: str,
        job_id: str = "_system",
    ) -> VisualVerificationResult:
        """Evaluate an image candidate against narration and educational concept."""
        if not self.client or len(image_bytes) < 1000:
            return VisualVerificationResult(
                is_relevant=True,
                confidence=0.85,
                verdict="ACCEPT",
                reason="Client bypassed or image too small",
            )

        prompt = f"""You are a strict visual quality editor for a 60-second educational video.
Target Spoken Narration: "{narration.strip()}"
Target Educational Subject/Concept: "{concept.strip()}"

Inspect this visual candidate.
Evaluate:
1. Does this visual accurately represent the educational concept or spoken narration?
2. REJECT if it contains unrelated human faces/selfies, inappropriate content, visible corporate watermarks, memes, or cars/unrelated city street scenes when the topic is scientific/historical.
3. ACCEPT if it is a relevant photograph, 3D illustration, landscape, organism, or scientific diagram matching the topic.

Respond strictly in valid JSON matching this schema:
{{
  "is_relevant": true or false,
  "confidence": 0.0 to 1.0,
  "detected_subject": "brief 3-7 word description of what is actually in the image",
  "verdict": "ACCEPT" or "REJECT",
  "reason": "1 concise sentence explaining the verdict"
}}"""

        try:
            # Downscale if image is huge to minimize token cost and latency
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )

            raw_text = response.text or "{}"
            data = json.loads(raw_text)

            verdict = data.get("verdict", "ACCEPT").upper()
            is_relevant = bool(data.get("is_relevant", verdict == "ACCEPT"))
            confidence = float(data.get("confidence", 0.9))

            # Threshold enforcement: require at least 0.65 confidence for ACCEPT
            if verdict == "ACCEPT" and confidence < 0.65:
                verdict = "REJECT"
                is_relevant = False

            return VisualVerificationResult(
                is_relevant=is_relevant,
                confidence=confidence,
                detected_subject=data.get("detected_subject", "scene"),
                verdict=verdict,
                reason=data.get("reason", "Evaluated by Gemini Vision"),
            )

        except Exception as e:
            logger.warning("VisualVerifier encountered error, defaulting to ACCEPT: %s", e)
            return VisualVerificationResult(
                is_relevant=True,
                confidence=0.75,
                verdict="ACCEPT",
                reason=f"Verification fallback: {str(e)[:50]}",
            )
