"""Tests for 3-Tier AI Router and Privacy Filtering."""

import pytest
from core.ai.router import AIRouter, RoutingDecision
from core.ai.local_provider import LocalAIProvider
from core.ai.cloud_provider import CloudAIProvider
from core.device_resolver import DeviceResolver
from core.privacy import PrivacyFilter, PrivacyMode, PrivacyViolationError


def test_ai_router_level1_deterministic_bypass():
    resolver = DeviceResolver()
    router = AIRouter(device_resolver=resolver, deterministic_first=True)

    deterministic_decision = RoutingDecision(
        level=1,
        provider_used="deterministic",
        action_type="tool_call",
        tool_name="open_application",
        tool_args={"app_name": "Safari", "device": "paperball"},
        target_device="paperball"
    )

    decision = router.route_and_execute_intent(
        "open Safari",
        deterministic_match=deterministic_decision
    )

    assert decision.level == 1
    assert decision.provider_used == "deterministic"
    assert decision.action_type == "tool_call"
    assert decision.tool_name == "open_application"


def test_privacy_filter_redaction():
    """Verify aggressive sanitization of secrets in private mode."""
    sensitive_prompt = (
        "Here is my API key sk-abcdef1234567890abcdef123456 and password=supersecret123 "
        "along with token Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz and AWS_SECRET_ACCESS_KEY=mysecretkey."
    )

    sanitized = PrivacyFilter.sanitize_text(sensitive_prompt)
    assert "sk-abcdef" not in sanitized
    assert "[REDACTED_API_KEY]" in sanitized
    assert "supersecret123" not in sanitized
    assert "[REDACTED_PASSWORD]" in sanitized
    assert "Bearer eyJ" not in sanitized
    assert "[REDACTED_TOKEN]" in sanitized


def test_privacy_mode_blocks_cloud():
    """Verify that LOCAL_ONLY completely rejects outbound cloud AI dispatch."""
    resolver = DeviceResolver()
    cloud = CloudAIProvider(provider_name="openai", api_key="sk-fakekey", privacy_mode="local_only")
    assert not cloud.is_available

    router = AIRouter(
        device_resolver=resolver,
        cloud_provider=cloud,
        privacy_mode="local_only",
        cloud_fallback=True,
        local_first=False
    )

    # Cloud fallback must be refused under local_only
    decision = router.route_and_execute_intent("Explain quantum computing in detail.")
    assert decision.level == 1
    assert decision.provider_used == "heuristic_fallback"


def test_privacy_mode_private_allows_cloud_with_redaction():
    """Verify PRIVATE allows cloud calls with sanitized messages."""
    cloud = CloudAIProvider(provider_name="openai", api_key="sk-fakekey", privacy_mode="private")
    assert cloud.is_available

    messages = [
        {"role": "user", "content": "My API key is sk-1234567890123456789012345 and password=foobar."}
    ]
    prepared = PrivacyFilter.prepare_for_cloud(messages, "private")
    assert "sk-123456" not in prepared[0]["content"]
    assert "foobar" not in prepared[0]["content"]


@pytest.mark.asyncio
async def test_provider_agnostic_local_methods():
    """Verify text(), vision(), stream(), and structured_output() on LocalAIProvider."""
    from pydantic import BaseModel

    class DeviceSummary(BaseModel):
        device: str
        status: str

    resolver = DeviceResolver()
    local_ai = LocalAIProvider(device_resolver=resolver)

    # 1. text()
    text_res = await local_ai.text("Hello Brown")
    assert isinstance(text_res, str)
    assert len(text_res) > 0

    # 2. vision()
    dummy_image = b"fake_png_binary_data"
    vision_res = await local_ai.vision("What do you see on Error Boy?", images=[dummy_image])
    assert isinstance(vision_res, str)
    assert "Visual inspection" in vision_res or "workspace" in vision_res

    # 3. stream()
    stream_chunks = []
    async for chunk in local_ai.stream("Brief greeting"):
        stream_chunks.append(chunk)
    assert len(stream_chunks) > 0

    # 4. structured_output()
    # Structured output with mock schema
    result = await local_ai.structured_output(
        "Give me device status",
        schema=DeviceSummary,
        system_prompt='{"device": "error_boy", "status": "active"}'
    )
    assert isinstance(result, DeviceSummary)
    assert result.device == "error_boy"


@pytest.mark.asyncio
async def test_multimodal_vision_routing_privacy():
    """Verify route_vision enforces privacy boundary and local first."""
    resolver = DeviceResolver()
    local_ai = LocalAIProvider(device_resolver=resolver)
    router = AIRouter(device_resolver=resolver, local_provider=local_ai, privacy_mode="local_only")

    # Local vision route
    decision = await router.route_vision("Describe this screen", images=[b"fake_image_frame"])
    assert decision.level == 2
    assert decision.provider_used == "local"
    assert decision.direct_response is not None

