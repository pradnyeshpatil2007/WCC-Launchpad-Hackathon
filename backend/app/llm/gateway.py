"""LLM Gateway with sequential failover, cooldowns, and error classification (Doc 3 §8)."""

import asyncio
from datetime import datetime, timezone
import json
import random
import time
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel

from app.config import get_settings
from app.core.errors import GatewayExhaustedError, GatewayFatalError, StageError
from app.core.http_client import LoggedHttpClient
from app.llm.classify import Action, ErrorClass, classify_response
from app.llm.gemini_rest import LLMRequest, shape_gemini_request


class AttemptRecord(BaseModel):
    model: str
    cycle: int
    outcome: str
    http_status: Optional[int] = None
    error_message: Optional[str] = None
    latency_ms: int = 0


class GatewayResult(BaseModel):
    text: str
    parsed: Optional[Dict[str, Any]] = None
    model_used: str
    attempts: List[AttemptRecord]


class LLMGateway:
    """Custom LLM Gateway ensuring strict sequential failover without direct agent calls."""

    def __init__(self, http_client: Optional[LoggedHttpClient] = None):
        self.settings = get_settings()
        self.http_client = http_client or LoggedHttpClient(
            timeout=float(self.settings.LLM_REQUEST_TIMEOUT_SECONDS)
        )
        self.cooldowns: Dict[str, float] = {}  # model_name -> monotonic timestamp when cooldown expires
        self.unavailable_models: Set[str] = set()
        self._semaphore = asyncio.Semaphore(4)

    def is_in_cooldown(self, model: str) -> bool:
        now = time.monotonic()
        expiry = self.cooldowns.get(model, 0.0)
        return now < expiry

    def set_cooldown(self, model: str, seconds: float) -> None:
        self.cooldowns[model] = time.monotonic() + seconds

    def mark_unavailable(self, model: str) -> None:
        self.unavailable_models.add(model)

    async def generate(self, req: LLMRequest, model_override_sequence: Optional[List[str]] = None) -> GatewayResult:
        """Execute generation across the model sequence with sequential failover."""
        sequence = model_override_sequence or self.settings.llm_models
        if not sequence:
            raise GatewayFatalError("CONFIG_ERROR", "LLM model sequence is empty")

        deadline = time.monotonic() + self.settings.LLM_TOTAL_DEADLINE_SECONDS
        attempts: List[AttemptRecord] = []
        request_err_count = 0
        prompt_blocked_count = 0
        total_evaluations = 0

        async with self._semaphore:
            for cycle in range(1, self.settings.LLM_MAX_FULL_CYCLES + 1):
                # Check if all models in sequence are currently skipped
                active_models = [
                    m for m in sequence
                    if not self.is_in_cooldown(m) and m not in self.unavailable_models
                ]
                # If all are skipped, ignore skips for this cycle to avoid premature exhaustion
                models_to_try = active_models if active_models else sequence

                for model in models_to_try:
                    if time.monotonic() > deadline:
                        break

                    start_time = time.monotonic()
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                    gemini_key = self.settings.GEMINI_API_KEY.get_secret_value()
                    headers = {
                        "x-goog-api-key": gemini_key,
                        "Content-Type": "application/json",
                    }
                    body = shape_gemini_request(req)

                    resp = None
                    call_error: Optional[Exception] = None
                    try:
                        resp = await self.http_client.request(
                            method="POST",
                            url=url,
                            kind="llm",
                            provider="gemini",
                            label=req.purpose,
                            job_id=req.job_id,
                            model=model,
                            attempt=len(attempts) + 1,
                            headers=headers,
                            json_data=body,
                        )
                    except Exception as e:
                        call_error = e

                    latency_ms = int((time.monotonic() - start_time) * 1000)
                    total_evaluations += 1

                    status_code = resp.status_code if resp is not None else 0
                    resp_headers = dict(resp.headers) if resp is not None else {}
                    resp_body = None
                    if resp is not None:
                        try:
                            resp_body = resp.json()
                        except Exception:
                            resp_body = resp.text

                    action, err_class, reason, cooldown = classify_response(
                        status_code=status_code,
                        headers=resp_headers,
                        body=resp_body,
                        error=call_error,
                    )

                    attempt_rec = AttemptRecord(
                        model=model,
                        cycle=cycle,
                        outcome=action.value,
                        http_status=status_code if resp is not None else None,
                        error_message=reason if action != Action.SUCCESS else None,
                        latency_ms=latency_ms,
                    )
                    attempts.append(attempt_rec)

                    if action == Action.SUCCESS:
                        # Extract candidates text
                        cand_parts = resp_body["candidates"][0]["content"]["parts"]
                        full_text = "".join(p.get("text", "") for p in cand_parts)
                        parsed_dict = None
                        if req.json_schema is not None:
                            try:
                                parsed_dict = json.loads(full_text)
                            except Exception as e:
                                # Bad JSON body, advance to next model
                                attempt_rec.outcome = Action.ADVANCE.value
                                attempt_rec.error_message = f"JSON parse error: {e}"
                                continue

                        return GatewayResult(
                            text=full_text,
                            parsed=parsed_dict,
                            model_used=model,
                            attempts=attempts,
                        )

                    elif action == Action.FATAL:
                        # Fatal auth error or critical request flaw
                        if err_class == ErrorClass.AUTH:
                            raise GatewayFatalError("GEMINI_AUTH", reason)
                        raise GatewayFatalError("FATAL_ERROR", reason)

                    elif action == Action.ADVANCE:
                        if err_class == ErrorClass.TRANSIENT and cooldown:
                            self.set_cooldown(model, cooldown)
                        elif err_class == ErrorClass.MODEL_MISSING:
                            self.mark_unavailable(model)
                        elif err_class == ErrorClass.REQUEST_OR_PERMISSION:
                            request_err_count += 1
                            if request_err_count >= 2:
                                raise GatewayFatalError("REQUEST_INVALID", f"Recurring request invalidity: {reason}")
                        elif err_class == ErrorClass.PROMPT_BLOCKED:
                            prompt_blocked_count += 1

                # Full cycle completed without success -> backoff before next cycle
                if cycle < self.settings.LLM_MAX_FULL_CYCLES and time.monotonic() < deadline:
                    jitter = random.uniform(0.1, 0.9)
                    backoff = min(
                        self.settings.LLM_BACKOFF_BASE_SECONDS * (2 ** (cycle - 1)) + jitter,
                        self.settings.LLM_BACKOFF_MAX_SECONDS,
                    )
                    remaining = deadline - time.monotonic()
                    sleep_time = min(backoff, max(0.1, remaining))
                    await asyncio.sleep(sleep_time)

        # Check terminal failure condition
        if prompt_blocked_count >= total_evaluations and total_evaluations > 0:
            raise StageError(
                code="PROMPT_REFUSED",
                stage="research",
                message="The prompt was blocked by safety policies across models",
                retryable=False,
            )

        raise GatewayExhaustedError(
            f"All {len(sequence)} LLM models were exhausted after {len(attempts)} attempts"
        )
