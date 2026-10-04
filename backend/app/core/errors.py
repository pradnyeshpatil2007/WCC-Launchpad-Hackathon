"""Error definitions and error taxonomy for AutoShorts."""

from typing import Any, Dict, Optional


class StageError(Exception):
    """Domain exception representing a stage failure with public-safe messaging."""

    def __init__(
        self,
        code: str,
        stage: str,
        message: str,
        retryable: bool = True,
        public_params: Optional[Dict[str, Any]] = None,
        internal_details: Optional[str] = None,
    ):
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.message = message
        self.retryable = retryable
        self.public_params = public_params or {}
        self.internal_details = internal_details


class AuditLogFailureError(StageError):
    """Raised when audit log cannot be persisted in fail-closed mode."""

    def __init__(self, message: str = "Failed to write API audit log"):
        super().__init__(
            code="AUDIT_LOG_FAILURE",
            stage="system",
            message=message,
            retryable=True,
        )


class GatewayFatalError(StageError):
    """Raised for non-recoverable client or auth errors in the LLM Gateway."""

    def __init__(self, code: str, message: str):
        super().__init__(
            code=code,
            stage="research",
            message=message,
            retryable=False,
        )


class GatewayExhaustedError(StageError):
    """Raised when all LLM models in the sequence and retry cycles have failed."""

    def __init__(self, message: str = "All LLM models in fallback sequence were exhausted"):
        super().__init__(
            code="RESEARCH_FAILED",
            stage="research",
            message=message,
            retryable=True,
        )
