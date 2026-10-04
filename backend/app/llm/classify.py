"""Error classification for the Gemini LLM Gateway (Doc 3 §8.3)."""

from enum import Enum
import json
from typing import Any, Dict, Optional, Tuple


class Action(str, Enum):
    SUCCESS = "SUCCESS"
    ADVANCE = "ADVANCE"
    FATAL = "FATAL"


class ErrorClass(str, Enum):
    NONE = "none"
    TRANSIENT = "transient"
    MODEL_MISSING = "model_missing"
    AUTH = "auth"
    REQUEST_OR_PERMISSION = "request_or_permission"
    PROMPT_BLOCKED = "prompt_blocked"
    BAD_RESPONSE = "bad_response"


def parse_retry_after(headers: Dict[str, str], body_dict: Optional[Dict[str, Any]] = None) -> Optional[float]:
    """Extract retry delay in seconds from HTTP headers or Gemini error details if available."""
    if "retry-after" in headers:
        try:
            return float(headers["retry-after"])
        except (ValueError, TypeError):
            pass

    if body_dict and isinstance(body_dict, dict):
        error_obj = body_dict.get("error", {})
        details = error_obj.get("details", [])
        for d in details:
            if isinstance(d, dict) and "retryDelay" in d:
                delay_str = d["retryDelay"]
                # Format: "12.34s"
                if isinstance(delay_str, str) and delay_str.endswith("s"):
                    try:
                        return float(delay_str[:-1])
                    except (ValueError, TypeError):
                        pass
    return None


def classify_response(
    status_code: int,
    headers: Dict[str, str],
    body: Any,
    error: Optional[Exception] = None,
) -> Tuple[Action, ErrorClass, str, Optional[float]]:
    """Classify an HTTP response or transport error into Gateway Action, ErrorClass, reason, and cooldown."""
    if error is not None:
        return Action.ADVANCE, ErrorClass.TRANSIENT, f"Transport error: {error}", None

    # Parse body if JSON string
    body_dict = None
    if isinstance(body, dict):
        body_dict = body
    elif isinstance(body, str):
        try:
            body_dict = json.loads(body)
        except Exception:
            pass

    # 1. Check HTTP Status
    if status_code == 429:
        cooldown = parse_retry_after(headers, body_dict) or 10.0
        return Action.ADVANCE, ErrorClass.TRANSIENT, "Rate limit (HTTP 429)", cooldown

    if status_code in (500, 502, 503, 504):
        return Action.ADVANCE, ErrorClass.TRANSIENT, f"Server error (HTTP {status_code})", 3.0

    if status_code == 404:
        return Action.ADVANCE, ErrorClass.MODEL_MISSING, f"Model not found (HTTP 404)", None

    # Auth error handling
    if status_code == 401:
        return Action.FATAL, ErrorClass.AUTH, "Unauthorized (HTTP 401)", None

    if status_code == 400:
        err_msg = ""
        if body_dict and "error" in body_dict:
            err_msg = body_dict["error"].get("message", "")
        # Gemini returns 400 with "API key not valid" for bad keys
        if "api key" in err_msg.lower() or "api_key_invalid" in err_msg.lower():
            return Action.FATAL, ErrorClass.AUTH, f"Invalid Gemini API key: {err_msg}", None
        return Action.ADVANCE, ErrorClass.REQUEST_OR_PERMISSION, f"Bad request (HTTP 400): {err_msg}", None

    if status_code == 403:
        err_msg = ""
        if body_dict and "error" in body_dict:
            err_msg = body_dict["error"].get("message", "")
        if "api key" in err_msg.lower():
            return Action.FATAL, ErrorClass.AUTH, f"Forbidden API key: {err_msg}", None
        return Action.ADVANCE, ErrorClass.REQUEST_OR_PERMISSION, f"Forbidden (HTTP 403): {err_msg}", None

    if status_code != 200:
        return Action.ADVANCE, ErrorClass.TRANSIENT, f"Unexpected HTTP status {status_code}", None

    # 2. Check HTTP 200 Body
    if not body_dict:
        return Action.ADVANCE, ErrorClass.BAD_RESPONSE, "Empty or non-JSON body on HTTP 200", None

    prompt_feedback = body_dict.get("promptFeedback", {})
    if "blockReason" in prompt_feedback:
        reason = prompt_feedback.get("blockReason")
        return Action.ADVANCE, ErrorClass.PROMPT_BLOCKED, f"Prompt blocked: {reason}", None

    candidates = body_dict.get("candidates", [])
    if not candidates:
        return Action.ADVANCE, ErrorClass.BAD_RESPONSE, "No candidates in 200 response", None

    first_cand = candidates[0]
    finish_reason = first_cand.get("finishReason")
    if finish_reason and finish_reason in {"SAFETY", "RECITATION", "OTHER", "MALFORMED_FUNCTION_CALL"}:
        return Action.ADVANCE, ErrorClass.BAD_RESPONSE, f"Candidate rejected with finishReason={finish_reason}", None

    parts = first_cand.get("content", {}).get("parts", [])
    if not parts or not any("text" in p for p in parts):
        return Action.ADVANCE, ErrorClass.BAD_RESPONSE, "Candidate content parts missing text", None

    return Action.SUCCESS, ErrorClass.NONE, "Success", None
