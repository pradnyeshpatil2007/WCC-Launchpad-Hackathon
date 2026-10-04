"""Audit logging subsystem for external API calls (FR-60 to FR-64).

Writes raw request.json, response.json, meta.json, and externalized binary assets
under logs/api_calls/<job_id>/{seq:04d}_{kind}_{provider}_{label}/.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.config import get_settings
from app.core.errors import AuditLogFailureError
from app.core.ids import generate_call_id


REDACTED_HEADER_NAMES = {
    "x-goog-api-key",
    "authorization",
    "cookie",
    "set-cookie",
}

REDACTED_QUERY_PARAMS = {
    "key",
    "api_key",
    "token",
}


def get_configured_secret_values() -> List[str]:
    """Retrieve raw secret string values from settings for exact redaction scanning."""
    settings = get_settings()
    secrets: List[str] = []
    for secret_attr in [settings.GEMINI_API_KEY, settings.PEXELS_API_KEY, settings.PIXABAY_API_KEY]:
        val = secret_attr.get_secret_value().strip()
        if val and not val.startswith("PASTE_") and not val.startswith("SET_") and len(val) >= 6:
            secrets.append(val)
    return secrets


def redact_url(url_str: str) -> Tuple[str, int]:
    """Redact sensitive query parameters from a URL."""
    redactions = 0
    try:
        parsed = urlparse(url_str)
        if not parsed.query:
            return url_str, 0
        qs = parse_qs(parsed.query, keep_blank_values=True)
        new_qs = {}
        for k, v_list in qs.items():
            if k.lower() in REDACTED_QUERY_PARAMS:
                new_qs[k] = ["[REDACTED]"] * len(v_list)
                redactions += len(v_list)
            else:
                new_qs[k] = v_list
        new_query = urlencode(new_qs, doseq=True)
        redacted_url = urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
        )
        return redacted_url, redactions
    except Exception:
        return url_str, 0


def redact_headers(headers: Dict[str, str]) -> Tuple[Dict[str, str], int]:
    """Redact sensitive HTTP request and response headers."""
    redactions = 0
    redacted = {}
    for k, v in headers.items():
        if k.lower() in REDACTED_HEADER_NAMES:
            redacted[k] = "[REDACTED]"
            redactions += 1
        else:
            redacted[k] = v
    return redacted, redactions


def redact_string_content(text: str, secrets: List[str]) -> Tuple[str, int]:
    """Scan string content for exact occurrences of configured API secrets."""
    redactions = 0
    result = text
    for secret in secrets:
        if secret in result:
            count = result.count(secret)
            redactions += count
            result = result.replace(secret, "[REDACTED]")
    return result, redactions


def sanitize_payload(obj: Any, secrets: List[str]) -> Tuple[Any, int]:
    """Recursively sanitize JSON structures, redacting any secrets in string values."""
    total_redactions = 0
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            new_val, r = sanitize_payload(v, secrets)
            new_dict[k] = new_val
            total_redactions += r
        return new_dict, total_redactions
    elif isinstance(obj, list):
        new_list = []
        for item in obj:
            new_val, r = sanitize_payload(item, secrets)
            new_list.append(new_val)
            total_redactions += r
        return new_list, total_redactions
    elif isinstance(obj, str):
        return redact_string_content(obj, secrets)
    return obj, total_redactions


class CallRecord:
    """Tracks state and logs for a single outbound API call."""

    def __init__(
        self,
        call_id: str,
        job_id: str,
        kind: str,
        provider: str,
        label: str,
        seq: int,
        call_dir: Path,
        model: Optional[str] = None,
        attempt: int = 1,
        retry_of: Optional[str] = None,
    ):
        self.call_id = call_id
        self.job_id = job_id
        self.kind = kind
        self.provider = provider
        self.label = label
        self.seq = seq
        self.call_dir = call_dir
        self.model = model
        self.attempt = attempt
        self.retry_of = retry_of
        self.started_at: datetime = datetime.now(timezone.utc)
        self.ended_at: Optional[datetime] = None
        self.outcome: str = "in_flight"
        self.http_status: Optional[int] = None
        self.bytes_in: int = 0
        self.bytes_out: int = 0
        self.redactions: int = 0
        self.notes: Optional[str] = None

    def record_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Any = None,
    ) -> None:
        """Write request.json before sending to ensure fail-closed evidence capture."""
        secrets = get_configured_secret_values()
        clean_url, r_url = redact_url(url)
        clean_headers, r_hdr = redact_headers(headers)
        clean_body, r_body = sanitize_payload(body, secrets) if body is not None else (None, 0)
        self.redactions += r_url + r_hdr + r_body

        req_payload = {
            "method": method,
            "url": clean_url,
            "headers": clean_headers,
            "body": clean_body,
        }

        try:
            self.call_dir.mkdir(parents=True, exist_ok=True)
            req_path = self.call_dir / "request.json"
            req_path.write_text(json.dumps(req_payload, indent=2), encoding="utf-8")
        except Exception as e:
            settings = get_settings()
            if settings.LOG_FAIL_CLOSED:
                raise AuditLogFailureError(f"Could not write request.json to {self.call_dir}: {e}")

    def save_binary(self, filename: str, data: bytes) -> Dict[str, Any]:
        """Externalize binary content (images, audio) into the call directory."""
        try:
            self.call_dir.mkdir(parents=True, exist_ok=True)
            bin_path = self.call_dir / filename
            bin_path.write_bytes(data)
            sha256 = hashlib.sha256(data).hexdigest()
            return {
                "$binary_ref": filename,
                "bytes": len(data),
                "sha256": sha256,
            }
        except Exception as e:
            settings = get_settings()
            if settings.LOG_FAIL_CLOSED:
                raise AuditLogFailureError(f"Could not save binary file {filename}: {e}")
            return {"$binary_ref": filename, "error": str(e)}

    def record_response(
        self,
        status_code: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
        body: Any = None,
        error: Optional[Exception] = None,
    ) -> None:
        """Write response.json upon response reception or transport failure."""
        secrets = get_configured_secret_values()
        clean_headers, r_hdr = redact_headers(headers or {})
        self.redactions += r_hdr

        if error is not None:
            err_type = type(error).__name__
            clean_repr, r_err = redact_string_content(repr(error), secrets)
            self.redactions += r_err
            resp_payload = {
                "error_type": err_type,
                "error_repr": clean_repr,
            }
        else:
            clean_body, r_body = sanitize_payload(body, secrets) if body is not None else (None, 0)
            self.redactions += r_body
            resp_payload = {
                "status_code": status_code,
                "headers": clean_headers,
                "body": clean_body,
            }

        try:
            self.call_dir.mkdir(parents=True, exist_ok=True)
            resp_path = self.call_dir / "response.json"
            resp_path.write_text(json.dumps(resp_payload, indent=2), encoding="utf-8")
        except Exception as e:
            settings = get_settings()
            if settings.LOG_FAIL_CLOSED:
                raise AuditLogFailureError(f"Could not write response.json to {self.call_dir}: {e}")

    def finalize(
        self,
        outcome: str,
        http_status: Optional[int] = None,
        bytes_in: int = 0,
        bytes_out: int = 0,
        notes: Optional[str] = None,
    ) -> None:
        """Write meta.json and append index.jsonl summary."""
        self.ended_at = datetime.now(timezone.utc)
        self.outcome = outcome
        self.http_status = http_status
        self.bytes_in = bytes_in
        self.bytes_out = bytes_out
        self.notes = notes

        latency_ms = int((self.ended_at - self.started_at).total_seconds() * 1000)

        meta_payload = {
            "call_id": self.call_id,
            "job_id": self.job_id,
            "kind": self.kind,
            "provider": self.provider,
            "label": self.label,
            "model": self.model,
            "attempt": self.attempt,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
            "latency_ms": latency_ms,
            "outcome": self.outcome,
            "http_status": self.http_status,
            "bytes_in": self.bytes_in,
            "bytes_out": self.bytes_out,
            "retry_of": self.retry_of,
            "redactions": self.redactions,
            "notes": self.notes,
        }

        try:
            self.call_dir.mkdir(parents=True, exist_ok=True)
            meta_path = self.call_dir / "meta.json"
            meta_path.write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")

            # Append to index.jsonl in job log root
            job_log_root = self.call_dir.parent
            index_path = job_log_root / "index.jsonl"
            summary_line = {
                "seq": self.seq,
                "kind": self.kind,
                "provider": self.provider,
                "label": self.label,
                "model": self.model,
                "outcome": self.outcome,
                "http_status": self.http_status,
                "latency_ms": latency_ms,
                "path": str(self.call_dir.name),
            }
            with index_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(summary_line) + "\n")
        except Exception as e:
            settings = get_settings()
            if settings.LOG_FAIL_CLOSED:
                raise AuditLogFailureError(f"Could not finalize meta.json: {e}")


class AuditLogger:
    """Manages call sequences and directory creation for a specific job or system scope."""

    def __init__(self, job_id: str = "_system"):
        self.job_id = job_id
        self.settings = get_settings()
        self.base_dir = self.settings.resolved_log_dir / self.job_id
        self._seq = 0
        self._init_seq()

    def _init_seq(self) -> None:
        """Initialize seq counter by scanning existing directories."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        index_file = self.base_dir / "index.jsonl"
        if index_file.exists():
            try:
                for line in index_file.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        data = json.loads(line)
                        if "seq" in data and isinstance(data["seq"], int):
                            if data["seq"] > self._seq:
                                self._seq = data["seq"]
            except Exception:
                pass

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    @asynccontextmanager
    async def call(
        self,
        kind: str,
        provider: str,
        label: str,
        model: Optional[str] = None,
        attempt: int = 1,
        retry_of: Optional[str] = None,
    ):
        seq = self.next_seq()
        call_id = generate_call_id()
        folder_name = f"{seq:04d}_{kind}_{provider}_{label}"
        call_dir = self.base_dir / folder_name

        rec = CallRecord(
            call_id=call_id,
            job_id=self.job_id,
            kind=kind,
            provider=provider,
            label=label,
            seq=seq,
            call_dir=call_dir,
            model=model,
            attempt=attempt,
            retry_of=retry_of,
        )

        try:
            yield rec
        except Exception as e:
            if rec.outcome == "in_flight":
                rec.finalize(outcome="transport_error", notes=f"{type(e).__name__}: {e}")
            raise
        else:
            if rec.outcome == "in_flight":
                rec.finalize(outcome="success")
