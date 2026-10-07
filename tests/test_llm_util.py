"""
Unit tests for Gemini LLM utility, immediate fallback mechanism, and model fallback.
Verifies that:
1. Primary model (gemini-3.8-flash) success returns data immediately.
2. 429 Quota errors immediately activate fallback (gemini-3.5-flash-lite) WITHOUT retrying primary.
3. 503 Service Unavailable errors immediately activate fallback (gemini-3.5-flash-lite) WITHOUT retrying primary.
4. Subsequent calls in the same workflow/session directly use fallback model without calling primary.
5. Permanent 4xx errors fail immediately without retry or fallback.
6. Fallback success and failure handling are robust.
"""

from unittest.mock import MagicMock, call
import pytest
from app.agents.llm_util import (
    is_quota_error,
    is_transient_503_error,
    is_transient_error,
    call_gemini_json,
    clean_json_text,
    reset_fallback_status,
    is_fallback_activated,
    get_fallback_message,
    is_primary_unavailable,
    is_quota_fallback_active,
)


@pytest.fixture(autouse=True)
def run_before_each_test():
    """Ensure fallback state is clean before each test."""
    reset_fallback_status()
    yield
    reset_fallback_status()


def test_clean_json_text_markdown_stripping():
    """Verify clean_json_text strips markdown fences properly."""
    raw = "```json\n{\"key\": \"value\"}\n```"
    assert clean_json_text(raw) == '{"key": "value"}'

    raw_no_json = "```\n{\"key\": \"value\"}\n```"
    assert clean_json_text(raw_no_json) == '{"key": "value"}'

    raw_prefix = "Here is the response:\n{\"key\": \"value\"}\nHope this helps!"
    assert clean_json_text(raw_prefix) == '{"key": "value"}'


def test_is_quota_error_detection():
    """Verify 429 and RESOURCE_EXHAUSTED errors are properly classified as quota errors."""
    e_429 = Exception("429 RESOURCE_EXHAUSTED: You exceeded your current quota.")
    assert is_quota_error(e_429) is True

    e_quota = Exception("ResourceExhausted: quota exceeded for quota metric 'GenerateContent'")
    assert is_quota_error(e_quota) is True

    e_rate = Exception("429 Rate limit exceeded. Please try again later.")
    assert is_quota_error(e_rate) is True

    # 503 is not a quota error
    e_503 = Exception("503 UNAVAILABLE: High demand.")
    assert is_quota_error(e_503) is False

    # 400 is not a quota error
    e_400 = Exception("400 INVALID_ARGUMENT: Invalid API key.")
    assert is_quota_error(e_400) is False


def test_is_transient_503_error_detection():
    """Verify transient 503 vs permanent error classification."""
    # 503 high demand
    e_503 = Exception(
        "503 UNAVAILABLE: This model is currently experiencing high demand. "
        "Spikes in demand are usually temporary. Please try again later."
    )
    assert is_transient_503_error(e_503) is True
    assert is_transient_error(e_503) is True

    # Quota is not a 503 error, but is a transient error in general
    e_429 = Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for quota metric.")
    assert is_transient_503_error(e_429) is False
    assert is_transient_error(e_429) is True

    # Network reset
    e_reset = Exception("Connection reset by peer")
    assert is_transient_503_error(e_reset) is True

    # Permanent 400 invalid API key
    e_bad_key = Exception(
        "400 INVALID_ARGUMENT. API key not valid. Please pass a valid API key. (reason: API_KEY_INVALID)"
    )
    assert is_transient_503_error(e_bad_key) is False
    assert is_transient_error(e_bad_key) is False

    # Permanent 401 unauthenticated
    e_401 = Exception("401 UNAUTHENTICATED: Request had invalid authentication credentials.")
    assert is_transient_503_error(e_401) is False
    assert is_transient_error(e_401) is False

    # Permanent 404 model not found
    e_404 = Exception("404 NOT_FOUND: models/gemini-old is not found.")
    assert is_transient_503_error(e_404) is False
    assert is_transient_error(e_404) is False


def test_primary_gemini_3_8_flash_success():
    """Verify primary gemini-3.8-flash returns output on first attempt without retrying or fallback."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"status": "success", "model": "primary"}'
    mock_client.models.generate_content.return_value = mock_response

    result = call_gemini_json(
        client=mock_client,
        model="gemini-3.8-flash",
        prompt="test prompt",
        fallback_model="gemini-3.5-flash-lite",
    )

    assert result == {"status": "success", "model": "primary"}
    assert mock_client.models.generate_content.call_count == 1
    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-3.8-flash"
    assert is_fallback_activated() is False


def test_429_quota_immediately_triggers_fallback_without_retries():
    """
    Verify that a 429 RESOURCE_EXHAUSTED quota error immediately activates
    the fallback model (gemini-3.5-flash-lite) WITHOUT repeated retries on primary.
    """
    mock_client = MagicMock()

    mock_fallback_response = MagicMock()
    mock_fallback_response.text = '{"status": "success", "model": "gemini-3.5-flash-lite"}'

    # Primary model throws 429 RESOURCE_EXHAUSTED, fallback returns response
    mock_client.models.generate_content.side_effect = [
        Exception("429 RESOURCE_EXHAUSTED: You exceeded your current quota, please check your plan."),
        mock_fallback_response,
    ]

    result = call_gemini_json(
        client=mock_client,
        model="gemini-3.8-flash",
        prompt="extract requirements",
        retry_delays=[5.0, 10.0, 20.0],  # Even though 3 retries are configured, primary must NOT retry!
        fallback_model="gemini-3.5-flash-lite",
    )

    assert result == {"status": "success", "model": "gemini-3.5-flash-lite"}
    # Crucial assertion: Total calls must be EXACTLY 2 (1 primary attempt + 1 fallback attempt)
    assert mock_client.models.generate_content.call_count == 2
    calls = mock_client.models.generate_content.call_args_list
    assert calls[0].kwargs["model"] == "gemini-3.8-flash"
    assert calls[1].kwargs["model"] == "gemini-3.5-flash-lite"
    assert is_fallback_activated() is True
    assert "fallback model" in get_fallback_message().lower()


def test_503_immediately_triggers_fallback_without_retries():
    """
    Verify that a 503 SERVICE_UNAVAILABLE error on primary model immediately activates
    the fallback model (gemini-3.5-flash-lite) WITHOUT repeated retries or backoff delays.
    """
    mock_client = MagicMock()

    mock_fallback_response = MagicMock()
    mock_fallback_response.text = '{"status": "success", "model": "gemini-3.5-flash-lite"}'

    # Primary model throws 503 UNAVAILABLE on first attempt, fallback succeeds
    mock_client.models.generate_content.side_effect = [
        Exception("503 UNAVAILABLE: This model is currently experiencing high demand. Spikes in demand are usually temporary."),
        mock_fallback_response,
    ]

    result = call_gemini_json(
        client=mock_client,
        model="gemini-3.8-flash",
        prompt="extract requirements",
        retry_delays=[5.0, 10.0, 20.0],  # Even with retry_delays specified, must NOT retry on 503!
        fallback_model="gemini-3.5-flash-lite",
    )

    assert result == {"status": "success", "model": "gemini-3.5-flash-lite"}
    # Crucial assertion: Total calls must be EXACTLY 2 (1 primary attempt + 1 fallback attempt, ZERO retries)
    assert mock_client.models.generate_content.call_count == 2
    calls = mock_client.models.generate_content.call_args_list
    assert calls[0].kwargs["model"] == "gemini-3.8-flash"
    assert calls[1].kwargs["model"] == "gemini-3.5-flash-lite"
    assert is_fallback_activated() is True
    assert "fallback model" in get_fallback_message().lower()


def test_subsequent_calls_directly_use_fallback_after_503():
    """
    Verify that once a 503 error occurs on the primary model (Agent 1),
    all subsequent agents (Agents 2, 3, 4) directly use the fallback model
    WITHOUT first attempting the primary model.
    """
    from app.agents.llm_util import is_primary_unavailable

    mock_client = MagicMock()
    mock_resp_fb1 = MagicMock(text='{"agent": "extraction", "model": "fallback"}')
    mock_resp_fb2 = MagicMock(text='{"agent": "validation", "model": "fallback"}')
    mock_resp_fb3 = MagicMock(text='{"agent": "user_stories", "model": "fallback"}')
    mock_resp_fb4 = MagicMock(text='{"agent": "architecture", "model": "fallback"}')

    # Call 1 (Agent 1): Primary 503, then fallback succeeds
    # Calls 2, 3, 4: Directly succeed on fallback without calling primary
    mock_client.models.generate_content.side_effect = [
        Exception("503 UNAVAILABLE: Model is busy."),
        mock_resp_fb1,
        mock_resp_fb2,
        mock_resp_fb3,
        mock_resp_fb4,
    ]

    assert is_primary_unavailable() is False

    # --- Agent 1 Call --- (hits 503 on primary, immediately falls back)
    res1 = call_gemini_json(
        client=mock_client,
        model="gemini-3.8-flash",
        prompt="agent 1 prompt",
        fallback_model="gemini-3.5-flash-lite",
    )
    assert res1["agent"] == "extraction"
    assert is_primary_unavailable() is True
    assert mock_client.models.generate_content.call_count == 2  # 1 primary + 1 fallback

    # --- Agent 2 Call --- (Must directly use fallback, 0 primary attempts!)
    res2 = call_gemini_json(
        client=mock_client,
        model="gemini-3.8-flash",
        prompt="agent 2 prompt",
        fallback_model="gemini-3.5-flash-lite",
    )
    assert res2["agent"] == "validation"
    assert mock_client.models.generate_content.call_count == 3  # +1 direct fallback

    # --- Agent 3 Call --- (Must directly use fallback, 0 primary attempts!)
    res3 = call_gemini_json(
        client=mock_client,
        model="gemini-3.8-flash",
        prompt="agent 3 prompt",
        fallback_model="gemini-3.5-flash-lite",
    )
    assert res3["agent"] == "user_stories"
    assert mock_client.models.generate_content.call_count == 4  # +1 direct fallback

    # --- Agent 4 Call --- (Must directly use fallback, 0 primary attempts!)
    res4 = call_gemini_json(
        client=mock_client,
        model="gemini-3.8-flash",
        prompt="agent 4 prompt",
        fallback_model="gemini-3.5-flash-lite",
    )
    assert res4["agent"] == "architecture"
    assert mock_client.models.generate_content.call_count == 5  # +1 direct fallback

    # Verify model arguments for each call
    calls = mock_client.models.generate_content.call_args_list
    assert calls[0].kwargs["model"] == "gemini-3.8-flash"      # Agent 1 primary (hit 503)
    assert calls[1].kwargs["model"] == "gemini-3.5-flash-lite"  # Agent 1 fallback
    assert calls[2].kwargs["model"] == "gemini-3.5-flash-lite"  # Agent 2 DIRECT fallback
    assert calls[3].kwargs["model"] == "gemini-3.5-flash-lite"  # Agent 3 DIRECT fallback
    assert calls[4].kwargs["model"] == "gemini-3.5-flash-lite"  # Agent 4 DIRECT fallback


def test_case_3_agent_1_succeeds_agent_2_hits_503_and_subsequent_bypass():
    """
    Verify Case 3 flow:
    Agent 1 -> gemini-3.8-flash -> 200 OK
    Agent 2 -> gemini-3.8-flash -> 503 -> immediately switch to gemini-3.5-flash-lite -> Agent 2 succeeds
    Agent 3 -> gemini-3.5-flash-lite directly
    Agent 4 -> gemini-3.5-flash-lite directly
    """
    from app.agents.llm_util import is_primary_unavailable

    mock_client = MagicMock()
    mock_resp_p1 = MagicMock(text='{"agent": "extraction", "model": "primary"}')
    mock_resp_fb2 = MagicMock(text='{"agent": "validation", "model": "fallback"}')
    mock_resp_fb3 = MagicMock(text='{"agent": "user_stories", "model": "fallback"}')
    mock_resp_fb4 = MagicMock(text='{"agent": "architecture", "model": "fallback"}')

    mock_client.models.generate_content.side_effect = [
        mock_resp_p1,                                         # Call 1: Agent 1 primary 200 OK
        Exception("503 UNAVAILABLE: Model is overloaded."),   # Call 2: Agent 2 primary 503
        mock_resp_fb2,                                        # Call 3: Agent 2 fallback succeeds
        mock_resp_fb3,                                        # Call 4: Agent 3 directly uses fallback
        mock_resp_fb4,                                        # Call 5: Agent 4 directly uses fallback
    ]

    assert is_primary_unavailable() is False

    # --- Agent 1 Call --- (Succeeds on primary)
    res1 = call_gemini_json(
        client=mock_client,
        model="gemini-3.8-flash",
        prompt="agent 1 prompt",
        fallback_model="gemini-3.5-flash-lite",
    )
    assert res1["agent"] == "extraction"
    assert is_primary_unavailable() is False
    assert mock_client.models.generate_content.call_count == 1

    # --- Agent 2 Call --- (Hits 503 on primary, immediately falls back to flash-lite)
    res2 = call_gemini_json(
        client=mock_client,
        model="gemini-3.8-flash",
        prompt="agent 2 prompt",
        fallback_model="gemini-3.5-flash-lite",
    )
    assert res2["agent"] == "validation"
    assert is_primary_unavailable() is True
    assert mock_client.models.generate_content.call_count == 3  # 1 (A1) + 1 (A2 primary) + 1 (A2 fallback)

    # --- Agent 3 Call --- (Directly calls fallback model, 0 primary attempts)
    res3 = call_gemini_json(
        client=mock_client,
        model="gemini-3.8-flash",
        prompt="agent 3 prompt",
        fallback_model="gemini-3.5-flash-lite",
    )
    assert res3["agent"] == "user_stories"
    assert mock_client.models.generate_content.call_count == 4

    # --- Agent 4 Call --- (Directly calls fallback model, 0 primary attempts)
    res4 = call_gemini_json(
        client=mock_client,
        model="gemini-3.8-flash",
        prompt="agent 4 prompt",
        fallback_model="gemini-3.5-flash-lite",
    )
    assert res4["agent"] == "architecture"
    assert mock_client.models.generate_content.call_count == 5

    # Check exact sequence of models invoked
    calls = mock_client.models.generate_content.call_args_list
    assert calls[0].kwargs["model"] == "gemini-3.8-flash"      # Agent 1 primary
    assert calls[1].kwargs["model"] == "gemini-3.8-flash"      # Agent 2 primary (503)
    assert calls[2].kwargs["model"] == "gemini-3.5-flash-lite"  # Agent 2 fallback
    assert calls[3].kwargs["model"] == "gemini-3.5-flash-lite"  # Agent 3 direct fallback
    assert calls[4].kwargs["model"] == "gemini-3.5-flash-lite"  # Agent 4 direct fallback


def test_primary_and_fallback_both_failing():
    """Verify clear error message when primary exhausted and fallback also fails."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        Exception("503 UNAVAILABLE: Primary is down."),
        Exception("503 UNAVAILABLE: Fallback is also down."),
    ]

    with pytest.raises(RuntimeError, match="both failed"):
        call_gemini_json(
            client=mock_client,
            model="gemini-3.8-flash",
            prompt="test prompt",
            retry_delays=[],  # 0 retries on primary (1 attempt on primary)
            fallback_model="gemini-3.5-flash-lite",
        )

    # 1 attempt for primary, 1 attempt for fallback
    assert mock_client.models.generate_content.call_count == 2
    assert is_fallback_activated() is True


def test_permanent_error_without_retry_and_without_fallback():
    """Verify permanent 400 error fails immediately without retrying and without fallback."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception(
        "400 INVALID_ARGUMENT: API key not valid."
    )

    with pytest.raises(RuntimeError, match="Gemini API error"):
        call_gemini_json(
            client=mock_client,
            model="gemini-3.8-flash",
            prompt="test prompt",
            retry_delays=[0.01, 0.01],
            fallback_model="gemini-3.5-flash-lite",
        )

    # Must only attempt once and NEVER call fallback
    assert mock_client.models.generate_content.call_count == 1
    assert is_fallback_activated() is False


def test_subsequent_calls_directly_use_fallback_after_429():
    """
    Verify that once a 429 quota error occurs on the primary model,
    all subsequent calls (e.g. Agents 2, 3, 4) directly use the fallback model
    WITHOUT first attempting the primary model.
    """
    from app.agents.llm_util import is_quota_fallback_active

    mock_client = MagicMock()
    mock_resp_fb1 = MagicMock(text='{"agent": "extraction", "model": "fallback"}')
    mock_resp_fb2 = MagicMock(text='{"agent": "validation", "model": "fallback"}')
    mock_resp_fb3 = MagicMock(text='{"agent": "user_stories", "model": "fallback"}')
    mock_resp_fb4 = MagicMock(text='{"agent": "architecture", "model": "fallback"}')

    # Call 1 (Agent 1): Primary 429, then fallback succeeds
    # Calls 2, 3, 4: Directly succeed on fallback without calling primary
    mock_client.models.generate_content.side_effect = [
        Exception("429 RESOURCE_EXHAUSTED: You exceeded your current quota."),
        mock_resp_fb1,
        mock_resp_fb2,
        mock_resp_fb3,
        mock_resp_fb4,
    ]

    assert is_quota_fallback_active() is False

    # --- Agent 1 Call ---
    res1 = call_gemini_json(
        client=mock_client,
        model="gemini-3.8-flash",
        prompt="agent 1 prompt",
        fallback_model="gemini-3.5-flash-lite",
    )
    assert res1["agent"] == "extraction"
    assert is_quota_fallback_active() is True
    assert mock_client.models.generate_content.call_count == 2  # 1 primary + 1 fallback

    # --- Agent 2 Call --- (Must directly use fallback, 0 primary attempts!)
    res2 = call_gemini_json(
        client=mock_client,
        model="gemini-3.8-flash",
        prompt="agent 2 prompt",
        fallback_model="gemini-3.5-flash-lite",
    )
    assert res2["agent"] == "validation"
    assert mock_client.models.generate_content.call_count == 3  # +1 direct fallback

    # --- Agent 3 Call --- (Must directly use fallback, 0 primary attempts!)
    res3 = call_gemini_json(
        client=mock_client,
        model="gemini-3.8-flash",
        prompt="agent 3 prompt",
        fallback_model="gemini-3.5-flash-lite",
    )
    assert res3["agent"] == "user_stories"
    assert mock_client.models.generate_content.call_count == 4  # +1 direct fallback

    # --- Agent 4 Call --- (Must directly use fallback, 0 primary attempts!)
    res4 = call_gemini_json(
        client=mock_client,
        model="gemini-3.8-flash",
        prompt="agent 4 prompt",
        fallback_model="gemini-3.5-flash-lite",
    )
    assert res4["agent"] == "architecture"
    assert mock_client.models.generate_content.call_count == 5  # +1 direct fallback

    # Verify model arguments for each call
    calls = mock_client.models.generate_content.call_args_list
    assert calls[0].kwargs["model"] == "gemini-3.8-flash"      # Agent 1 primary (hit 429)
    assert calls[1].kwargs["model"] == "gemini-3.5-flash-lite"  # Agent 1 fallback
    assert calls[2].kwargs["model"] == "gemini-3.5-flash-lite"  # Agent 2 DIRECT fallback
    assert calls[3].kwargs["model"] == "gemini-3.5-flash-lite"  # Agent 3 DIRECT fallback
    assert calls[4].kwargs["model"] == "gemini-3.5-flash-lite"  # Agent 4 DIRECT fallback
