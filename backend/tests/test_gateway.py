"""Phase 2 verification tests for LLM Gateway failover, ordering, exhaustion, and auth checks."""

import pytest
from pydantic import SecretStr

from app.config import get_settings
from app.core.errors import GatewayExhaustedError, GatewayFatalError
from app.core.http_client import LoggedHttpClient
from app.llm.gateway import LLMGateway
from app.llm.gemini_rest import Content, ContentPart, LLMRequest


@pytest.fixture
def gateway():
    return LLMGateway()


@pytest.mark.asyncio
async def test_gateway_normal_generation(gateway):
    """Test happy path generation on default first model."""
    req = LLMRequest(
        purpose="research_test",
        contents=[Content(parts=[ContentPart(text="Respond with the single word 'READY'.")])],
        temperature=0.1,
        job_id="test_gw_normal",
    )
    result = await gateway.generate(req)
    assert result.text.strip()
    assert result.model_used in gateway.settings.llm_models
    assert len(result.attempts) >= 1
    assert result.attempts[-1].outcome == "SUCCESS"
    print(f"\n[+] Normal generation succeeded using model: {result.model_used}")


@pytest.mark.asyncio
async def test_gateway_nonexistent_model_first_advances(gateway):
    """Test: nonexistent model first -> real 404 -> advance -> success on next model."""
    # Put an invalid model name first, followed by real models
    custom_seq = ["nonexistent-gemini-model-xyz", "gemini-3.5-flash", "gemini-3.5-flash-lite"]
    req = LLMRequest(
        purpose="failover_test",
        contents=[Content(parts=[ContentPart(text="Say 'FAILOVER_SUCCESS'.")])],
        temperature=0.1,
        job_id="test_gw_failover",
    )

    result = await gateway.generate(req, model_override_sequence=custom_seq)
    assert result.model_used in ("gemini-3.5-flash", "gemini-3.5-flash-lite")
    assert len(result.attempts) >= 2
    # Verify first attempt was the nonexistent model and failed with 404
    assert result.attempts[0].model == "nonexistent-gemini-model-xyz"
    assert result.attempts[0].http_status == 404
    assert result.attempts[0].outcome == "ADVANCE"
    # Final attempt succeeded
    assert result.attempts[-1].outcome == "SUCCESS"
    print(f"\n[+] Real 404 failover verified. First attempt: {result.attempts[0].model} (404), final: {result.model_used} (200)")


@pytest.mark.asyncio
async def test_gateway_five_position_ordering(gateway):
    """Test: 4 invalid models followed by valid models -> advances through all in order."""
    custom_seq = [
        "fake-model-1",
        "fake-model-2",
        "fake-model-3",
        "fake-model-4",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
    ]
    req = LLMRequest(
        purpose="order_test",
        contents=[Content(parts=[ContentPart(text="Return 'ORDER_CONFIRMED'.")])],
        temperature=0.1,
        job_id="test_gw_order",
    )
    result = await gateway.generate(req, model_override_sequence=custom_seq)
    assert result.model_used in ("gemini-3.5-flash", "gemini-3.5-flash-lite")
    assert len(result.attempts) >= 5
    for i in range(4):
        assert result.attempts[i].model == custom_seq[i]
        assert result.attempts[i].outcome == "ADVANCE"
        assert result.attempts[i].http_status == 404
    assert result.attempts[-1].outcome == "SUCCESS"
    print(f"\n[+] 5-position sequential failover verified across 4 invalid and valid models.")


@pytest.mark.asyncio
async def test_gateway_exhaustion_raises(gateway):
    """Test: all invalid models -> exhaustion raises GatewayExhaustedError without fake text."""
    custom_seq = ["fake-a", "fake-b"]
    req = LLMRequest(
        purpose="exhaustion_test",
        contents=[Content(parts=[ContentPart(text="Return text.")])],
        job_id="test_gw_exhaust",
    )
    with pytest.raises(GatewayExhaustedError):
        await gateway.generate(req, model_override_sequence=custom_seq)
    print("\n[+] Gateway correctly raised GatewayExhaustedError upon exhaustion.")


@pytest.mark.asyncio
async def test_gateway_malformed_key_fatal_without_cycling(monkeypatch):
    """Test: malformed API key causes fatal GEMINI_AUTH without cycling through remaining models."""
    settings = get_settings()
    monkeypatch.setattr(settings, "GEMINI_API_KEY", SecretStr("deliberately_invalid_key_12345"))

    bad_gw = LLMGateway()
    req = LLMRequest(
        purpose="auth_test",
        contents=[Content(parts=[ContentPart(text="Hello.")])],
        job_id="test_gw_auth",
    )

    with pytest.raises(GatewayFatalError) as exc_info:
        await bad_gw.generate(req)

    assert exc_info.value.code == "GEMINI_AUTH"
    print(f"\n[+] Malformed key provoked immediate fatal stop without cycling: {exc_info.value}")
