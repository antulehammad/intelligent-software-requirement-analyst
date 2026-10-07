"""
Utility for querying Google Gemini API via official google-genai SDK.
Handles robust JSON parsing, markdown code block stripping, transient error retries,
model fallback mechanism, and clear error reporting.
"""

import os
import re
import json
import time
import logging
from typing import Dict, Any, Optional, Sequence

logger = logging.getLogger("RequirementAnalyst.LLMUtil")

# Standard backoff delays for transient 503/UNAVAILABLE and high-demand spikes
DEFAULT_RETRY_DELAYS = [5.0, 10.0, 20.0]

# Module-level tracking for fallback model activation and session-level unavailable state
_fallback_activated: bool = False
_last_fallback_message: Optional[str] = None
_primary_unavailable: bool = False
_quota_fallback_active: bool = False

# Default retry delays preserved for API signature backwards compatibility
DEFAULT_RETRY_DELAYS = [5.0, 10.0, 20.0]


def reset_fallback_status(reset_quota: bool = True) -> None:
    """
    Reset the module-level fallback activation flag and message.
    If reset_quota is True, also resets the primary unavailable / quota exhaustion flag.
    """
    global _fallback_activated, _last_fallback_message, _primary_unavailable, _quota_fallback_active
    _fallback_activated = False
    _last_fallback_message = None
    if reset_quota:
        _primary_unavailable = False
        _quota_fallback_active = False


def is_fallback_activated() -> bool:
    """Check if the fallback model was activated during execution."""
    return _fallback_activated


def get_fallback_message() -> Optional[str]:
    """Retrieve the fallback status notice if activated."""
    return _last_fallback_message


def is_primary_unavailable() -> bool:
    """Check if primary model is marked unavailable for the current session/workflow."""
    return _primary_unavailable or _quota_fallback_active


def is_quota_fallback_active() -> bool:
    """Check if primary model quota is exhausted for the current session/workflow."""
    return is_primary_unavailable()


def set_primary_unavailable(unavailable: bool = True) -> None:
    """Mark the primary model as unavailable for the current session/workflow."""
    global _primary_unavailable, _quota_fallback_active, _fallback_activated, _last_fallback_message
    _primary_unavailable = unavailable
    _quota_fallback_active = unavailable
    if unavailable:
        _fallback_activated = True
        _last_fallback_message = "⚠️ Primary Gemini model unavailable. Using fallback model."


def set_quota_fallback_active(active: bool = True) -> None:
    """Set the session/workflow-level quota fallback flag."""
    set_primary_unavailable(active)


def clean_json_text(text: str) -> str:
    """Extract and sanitize JSON from model response text."""
    if not text:
        return "{}"
    
    text = text.strip()
    
    # Remove markdown code block if present
    if text.startswith("```"):
        # Match ```json ... ``` or ``` ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()
        else:
            # Fallback: remove first and last lines
            lines = text.splitlines()
            if len(lines) >= 2:
                text = "\n".join(lines[1:-1]).strip()

    # Sometimes models include text before the opening { or [
    start_brace = text.find("{")
    start_bracket = text.find("[")
    
    if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
        end_brace = text.rfind("}")
        if end_brace != -1:
            text = text[start_brace : end_brace + 1]
    elif start_bracket != -1:
        end_bracket = text.rfind("]")
        if end_bracket != -1:
            text = text[start_bracket : end_bracket + 1]

    return text


def is_quota_error(e: Exception) -> bool:
    """
    Determine if an exception represents a 429 / RESOURCE_EXHAUSTED / quota limit error.
    For quota errors, we immediately activate the fallback model without retries.
    """
    err_str = str(e).lower()
    quota_keywords = [
        "429",
        "resource_exhausted",
        "quota",
        "exceeded your current quota",
        "rate limit",
        "ratelimit",
        "quota exceeded",
    ]
    return any(k in err_str for k in quota_keywords)


def is_transient_503_error(e: Exception) -> bool:
    """
    Determine if an exception represents a temporary server-side 503 / UNAVAILABLE /
    high-demand spike that warrants immediate fallback without retries or backoff delays.
    """
    if is_quota_error(e):
        return False

    err_str = str(e).lower()

    # Permanent 4xx errors that must NEVER trigger fallback or retry
    permanent_keywords = [
        "api_key_invalid",
        "api key not valid",
        "unauthenticated",
        "permission_denied",
        "permission denied",
        "invalid_argument",
        "invalid argument",
        "not_found",
        "not found",
        "bad request",
        "400",
        "401",
        "403",
        "404",
    ]

    # If it has a permanent keyword and doesn't explicitly mention 503/unavailable
    if any(pk in err_str for pk in permanent_keywords):
        if not ("503" in err_str or "unavailable" in err_str or "high demand" in err_str):
            return False

    # Transient 503 / network indicators
    transient_503_keywords = [
        "503",
        "unavailable",
        "high demand",
        "temporarily unavailable",
        "spikes in demand",
        "overloaded",
        "connection reset",
        "remote end closed",
        "timeout",
        "timed out",
    ]
    return any(tk in err_str for tk in transient_503_keywords)


def is_transient_error(e: Exception) -> bool:
    """
    Determine if an error is transient (either a 503 temporary unavailable or 429 quota error).
    Preserved for backwards compatibility with tests and callers.
    """
    return is_quota_error(e) or is_transient_503_error(e)


def call_gemini_json(
    client,
    model: str,
    prompt: str,
    system_instruction: Optional[str] = None,
    retry_delays: Optional[Sequence[float]] = None,
    fallback_model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Call Gemini model and return parsed JSON object.
    Includes:
    1. Immediate fallback to GEMINI_FALLBACK_MODEL on 429 RESOURCE_EXHAUSTED (no primary retries).
    2. Immediate fallback to GEMINI_FALLBACK_MODEL on 503 SERVICE_UNAVAILABLE (no primary retries or delays).
    3. Workflow/session-level fallback persistence: remaining agents directly use fallback model without calling primary.
    4. Permanent 4xx errors (bad key, auth, not found) fail immediately without retry or fallback.
    5. Clean JSON sanitization and compatibility with Gemini 3.8.
    """
    from google.genai import types

    # Resolve fallback model
    if fallback_model is not None:
        effective_fallback = fallback_model.strip()
    else:
        try:
            from app.config import GEMINI_FALLBACK_MODEL
            effective_fallback = os.getenv("GEMINI_FALLBACK_MODEL", GEMINI_FALLBACK_MODEL).strip()
        except Exception:
            effective_fallback = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite").strip()

    # GenerateContentConfig without deprecated temperature/top_p/thinking_budget parameters for Gemini 3.8 compatibility
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        system_instruction=system_instruction if system_instruction else None,
    )

    global _fallback_activated, _last_fallback_message

    # Fast-path: If primary model was marked unavailable (due to 429 or 503) in this session/workflow,
    # directly use fallback model without attempting the primary model.
    if is_primary_unavailable() and effective_fallback and effective_fallback != model:
        _fallback_activated = True
        _last_fallback_message = "⚠️ Primary Gemini model unavailable. Using fallback model."
        logger.info(
            "Primary Gemini model unavailable. Directly calling fallback model '%s' for workflow call...",
            effective_fallback,
        )
        try:
            response = client.models.generate_content(
                model=effective_fallback,
                contents=prompt,
                config=config,
            )
            raw_text = response.text or ""
            cleaned_text = clean_json_text(raw_text)
            try:
                parsed = json.loads(cleaned_text)
                logger.info("Fallback model '%s' succeeded!", effective_fallback)
                return parsed
            except json.JSONDecodeError as jde:
                logger.error("Failed to parse JSON from fallback response: %s", jde)
                raise ValueError(
                    f"Fallback model returned invalid JSON format. Preview: {raw_text[:200]}..."
                ) from jde
        except Exception as fb_err:
            logger.error("Fallback model '%s' also failed: %s", effective_fallback, str(fb_err))
            raise RuntimeError(
                f"Primary model '{model}' and fallback model '{effective_fallback}' both failed. "
                f"Fallback error: {fb_err}"
            ) from fb_err

    # Attempt primary model (single attempt - NO retries or delays on 429 or 503)
    try:
        logger.info(
            "Calling Gemini model '%s' (prompt len: %d chars)",
            model,
            len(prompt),
        )

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )

        raw_text = response.text or ""
        cleaned_text = clean_json_text(raw_text)

        try:
            parsed = json.loads(cleaned_text)
            return parsed
        except json.JSONDecodeError as jde:
            logger.error("Failed to parse JSON from Gemini response: %s\nRaw output: %s", jde, raw_text[:500])
            raise ValueError(
                f"Model returned invalid JSON format. Preview: {raw_text[:200]}..."
            ) from jde

    except Exception as e:
        # If it's a JSON decoding error, re-raise immediately
        if isinstance(e, ValueError) and "invalid JSON" in str(e):
            raise

        is_429 = is_quota_error(e)
        is_503 = is_transient_503_error(e)

        # Trigger immediate fallback on 429 RESOURCE_EXHAUSTED or 503 SERVICE_UNAVAILABLE
        if is_429 or is_503:
            # 1. Mark the primary model as unavailable for the current workflow/session
            set_primary_unavailable(True)

            # 2. Log specific message based on error type
            if is_429:
                logger.warning(
                    "Primary model quota exhausted. Using fallback model for remaining workflow calls."
                )
            else:
                logger.warning(
                    "Primary Gemini model temporarily unavailable (503). Switching to fallback model for remaining workflow calls."
                )

            # 3. Immediately call fallback model for this agent without retrying primary
            if effective_fallback and effective_fallback != model:
                logger.info("Immediately calling fallback model '%s'...", effective_fallback)
                try:
                    fb_response = client.models.generate_content(
                        model=effective_fallback,
                        contents=prompt,
                        config=config,
                    )
                    fb_raw_text = fb_response.text or ""
                    fb_cleaned_text = clean_json_text(fb_raw_text)
                    try:
                        fb_parsed = json.loads(fb_cleaned_text)
                        logger.info("Fallback model '%s' succeeded!", effective_fallback)
                        return fb_parsed
                    except json.JSONDecodeError as fb_jde:
                        logger.error("Failed to parse JSON from fallback response: %s", fb_jde)
                        raise ValueError(
                            f"Fallback model returned invalid JSON format. Preview: {fb_raw_text[:200]}..."
                        ) from fb_jde
                except Exception as fb_err:
                    logger.error("Fallback model '%s' also failed: %s", effective_fallback, str(fb_err))
                    raise RuntimeError(
                        f"Primary model '{model}' and fallback model '{effective_fallback}' both failed. "
                        f"Fallback error: {fb_err}"
                    ) from fb_err
            else:
                # No fallback model available
                if is_429:
                    raise RuntimeError(
                        f"Gemini quota exceeded (429 RESOURCE_EXHAUSTED): {e}"
                    ) from e
                else:
                    raise RuntimeError(
                        f"Gemini service is temporarily unavailable (503 UNAVAILABLE): {e}"
                    ) from e

        # Permanent 4xx errors (e.g. 400, 401, 403, 404, invalid key, auth, not found)
        logger.error("Non-transient error in Gemini API call (will not retry/fallback): %s", str(e))
        raise RuntimeError(f"Gemini API error: {e}") from e
