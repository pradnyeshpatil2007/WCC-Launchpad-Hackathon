"""Edge-TTS provider with byte-exact audit logging and boundary timing extraction."""

import asyncio
from typing import Any, Dict, List, Optional, Tuple
import edge_tts

from app.config import get_settings
from app.core.audit_log import AuditLogger
from app.core.errors import StageError


class LoggedEdgeTTS:
    """Wraps edge_tts.Communicate with full request/response audit logging."""

    def __init__(self, job_id: str = "_system"):
        self.job_id = job_id
        self.settings = get_settings()

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        label: str = "synthesize",
        attempt: int = 1,
        retry_of: Optional[str] = None,
    ) -> Tuple[bytes, List[Dict[str, Any]], str]:
        """Synthesize text to speech using Edge-TTS with boundary extraction.

        Returns:
            (audio_bytes, word_timings, timing_mode)
        """
        chosen_voice = voice or self.settings.TTS_VOICE
        chosen_rate = rate or self.settings.TTS_RATE
        audit = AuditLogger(job_id=self.job_id)

        async with audit.call(
            kind="tts",
            provider="edge_tts",
            label=label,
            model=chosen_voice,
            attempt=attempt,
            retry_of=retry_of,
        ) as rec:
            req_params = {
                "text": text,
                "voice": chosen_voice,
                "rate": chosen_rate,
                "volume": "+0%",
                "pitch": "+0Hz",
                "boundary": "WordBoundary",
            }
            rec.record_request(
                method="WEBSOCKET",
                url="wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1",
                headers={"Content-Type": "application/json"},
                body=req_params,
            )

            try:
                communicate = edge_tts.Communicate(
                    text=text,
                    voice=chosen_voice,
                    rate=chosen_rate,
                    boundary="WordBoundary",
                )

                audio_chunks: List[bytes] = []
                boundary_events: List[Dict[str, Any]] = []

                async for chunk in communicate.stream():
                    chunk_type = chunk.get("type", "")
                    if chunk_type == "audio":
                        audio_chunks.append(chunk.get("data", b""))
                    elif chunk_type in ("WordBoundary", "SentenceBoundary"):
                        # Offset and duration in edge-tts are 100-nanosecond ticks
                        offset_sec = chunk.get("offset", 0) / 10_000_000.0
                        duration_sec = chunk.get("duration", 0) / 10_000_000.0
                        boundary_events.append(
                            {
                                "type": chunk_type,
                                "text": chunk.get("text", ""),
                                "offset_sec": offset_sec,
                                "duration_sec": duration_sec,
                                "raw_offset": chunk.get("offset", 0),
                                "raw_duration": chunk.get("duration", 0),
                            }
                        )

                full_audio = b"".join(audio_chunks)
                if not full_audio:
                    raise StageError(
                        code="VOICE_FAILED",
                        stage="asset",
                        message=f"Edge-TTS produced 0 bytes of audio for voice {chosen_voice}",
                    )

                # Save binary audio to audit log
                bin_ref = rec.save_binary("audio.mp3", full_audio)

                timing_mode = "word_boundary" if any(e["type"] == "WordBoundary" for e in boundary_events) else "sentence_proportional"

                rec.record_response(
                    status_code=200,
                    headers={"Content-Type": "audio/mpeg"},
                    body={
                        "audio_ref": bin_ref,
                        "timing_mode": timing_mode,
                        "events_count": len(boundary_events),
                        "events": boundary_events,
                    },
                )
                rec.finalize(
                    outcome="success",
                    http_status=200,
                    bytes_in=len(full_audio),
                    bytes_out=len(text.encode("utf-8")),
                    notes=f"Synthesized {len(full_audio)} bytes, {len(boundary_events)} boundaries ({timing_mode})",
                )

                return full_audio, boundary_events, timing_mode

            except Exception as e:
                rec.record_response(error=e)
                rec.finalize(
                    outcome="transport_error",
                    notes=f"TTS synthesis error: {e}",
                )
                raise
