"""Logged HTTP client wrapping httpx.AsyncClient for byte-exact audit logging."""

import json
from typing import Any, Dict, Optional
import httpx

from app.core.audit_log import AuditLogger


class LoggedHttpClient:
    """Thin wrapper around httpx.AsyncClient that logs every request/response payload."""

    def __init__(self, timeout: float = 60.0):
        self._client: Optional[httpx.AsyncClient] = None
        self.default_timeout = timeout

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.default_timeout))
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        url: str,
        kind: str,
        provider: str,
        label: str,
        job_id: str = "_system",
        model: Optional[str] = None,
        attempt: int = 1,
        retry_of: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Any = None,
        content: Optional[bytes] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        """Execute an HTTP request with automatic fail-closed audit logging."""
        audit = AuditLogger(job_id=job_id)
        client = await self.get_client()
        req_headers = dict(headers or {})

        async with audit.call(
            kind=kind,
            provider=provider,
            label=label,
            model=model,
            attempt=attempt,
            retry_of=retry_of,
        ) as rec:
            # Prepare body representation for request.json
            body_rep = json_data
            if body_rep is None and content is not None:
                body_rep = f"<binary {len(content)} bytes>"

            # Format full URL with query params for logging
            req_url = str(client.build_request(method, url, params=params).url)

            # Record request BEFORE sending (fail-closed integrity)
            rec.record_request(
                method=method,
                url=req_url,
                headers=req_headers,
                body=body_rep,
            )

            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=req_headers,
                    params=params,
                    json=json_data,
                    content=content,
                    timeout=timeout or self.default_timeout,
                )
            except Exception as e:
                rec.record_response(error=e)
                rec.finalize(
                    outcome="transport_error",
                    notes=f"{type(e).__name__}: {e}",
                )
                raise

            # Process response body
            resp_headers = dict(response.headers)
            content_type = response.headers.get("content-type", "").lower()
            resp_bytes = response.content
            bytes_in = len(resp_bytes)
            bytes_out = len(content or b"") + len(json.dumps(json_data).encode("utf-8") if json_data else b"")

            resp_body_rep: Any = None
            if "application/json" in content_type:
                try:
                    resp_body_rep = response.json()
                    # Check for Gemini inlineData base64 image parts to externalize
                    if isinstance(resp_body_rep, dict) and "candidates" in resp_body_rep:
                        for cand_idx, cand in enumerate(resp_body_rep.get("candidates", [])):
                            parts = cand.get("content", {}).get("parts", [])
                            for part_idx, part in enumerate(parts):
                                if "inlineData" in part and "data" in part["inlineData"]:
                                    import base64
                                    raw_b64 = part["inlineData"]["data"]
                                    mime = part["inlineData"].get("mimeType", "image/png")
                                    ext = "jpg" if "jpeg" in mime else "png"
                                    img_data = base64.b64decode(raw_b64)
                                    img_ref = rec.save_binary(f"image_{cand_idx}_{part_idx}.{ext}", img_data)
                                    part["inlineData"]["data"] = img_ref
                except Exception:
                    resp_body_rep = response.text
            elif any(t in content_type for t in ["image/", "audio/", "video/", "application/octet-stream"]):
                # Save binary download
                ext = "bin"
                if "jpeg" in content_type or "jpg" in content_type:
                    ext = "jpg"
                elif "png" in content_type:
                    ext = "png"
                elif "webp" in content_type:
                    ext = "webp"
                elif "mp3" in content_type or "mpeg" in content_type:
                    ext = "mp3"
                elif "wav" in content_type:
                    ext = "wav"
                resp_body_rep = rec.save_binary(f"response.{ext}", resp_bytes)
            else:
                resp_body_rep = response.text[:2000]

            rec.record_response(
                status_code=response.status_code,
                headers=resp_headers,
                body=resp_body_rep,
            )

            outcome = "success" if response.is_success else "http_error"
            rec.finalize(
                outcome=outcome,
                http_status=response.status_code,
                bytes_in=bytes_in,
                bytes_out=bytes_out,
                notes=f"HTTP {response.status_code}",
            )

            return response
