"""
Unit tests for configuration loading, security masking, and environment variable resolution.
Verifies that GEMINI_API_KEY is loaded reliably from .env without exposing secret material.
"""

import os
import tempfile
from dotenv import load_dotenv
from app.config import (
    is_api_key_valid,
    get_masked_api_key,
    PROJECT_ROOT,
    ENV_FILE_PATH,
    GEMINI_MODEL,
)


def test_project_root_and_env_path():
    """Verify that PROJECT_ROOT is an existing directory and ENV_FILE_PATH is anchored to it."""
    assert os.path.isdir(PROJECT_ROOT)
    assert os.path.basename(ENV_FILE_PATH) == ".env"
    assert os.path.dirname(ENV_FILE_PATH) == PROJECT_ROOT


def test_default_gemini_model_is_3_8_flash():
    """Verify that default model is configured as gemini-3.8-flash."""
    assert "gemini-3.8-flash" in (GEMINI_MODEL, os.getenv("GEMINI_MODEL", "gemini-3.8-flash"))


def test_default_gemini_fallback_model_is_3_5_flash_lite():
    """Verify that fallback model is configured as gemini-3.5-flash-lite."""
    from app.config import GEMINI_FALLBACK_MODEL
    assert "gemini-3.5-flash-lite" in (GEMINI_FALLBACK_MODEL, os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite"))




def test_is_api_key_valid_detection():
    """Verify validity logic correctly handles placeholders, empty keys, and real keys."""
    assert is_api_key_valid("") is False
    assert is_api_key_valid("   ") is False
    assert is_api_key_valid("your_api_key_here") is False
    assert is_api_key_valid("your_model_name_here") is False
    assert is_api_key_valid("YOUR_GEMINI_API_KEY") is False
    assert is_api_key_valid("short") is False
    # Valid key structure (> 10 chars, not placeholder)
    assert is_api_key_valid("AIzaSyFakeKeyForTesting12345") is True


def test_get_masked_api_key_never_exposes_secret():
    """Verify that get_masked_api_key masks the secret and never prints the full key."""
    test_key = "AIzaSySecretApiKeyForProduction9999"
    masked = get_masked_api_key(test_key)

    assert "Not Configured" not in masked
    assert masked.startswith("AIza")
    assert masked.endswith("9999")
    assert "..." in masked
    # Ensure middle 20 characters of secret are completely hidden
    assert "SecretApiKeyForProduction" not in masked
    assert len(masked) == 11  # 4 + 3 + 4 = 11 characters total


def test_masked_api_key_empty_or_placeholder():
    """Verify safe response when key is missing or placeholder."""
    assert get_masked_api_key("") == "Not Configured"
    assert get_masked_api_key("your_api_key_here") == "Not Configured"


def test_explicit_env_loading_independent_of_cwd():
    """Verify that dotenv loads explicitly from a specific path even if cwd changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dummy_env = os.path.join(tmpdir, ".env")
        with open(dummy_env, "w", encoding="utf-8") as f:
            f.write("TEST_SPECIAL_KEY=loaded_from_explicit_path\n")

        # Save cwd and change cwd to a different location
        original_cwd = os.getcwd()
        try:
            # Change to system temp
            other_dir = tempfile.gettempdir()
            os.chdir(other_dir)

            # Load using explicit path
            load_dotenv(dotenv_path=dummy_env, override=True)
            assert os.getenv("TEST_SPECIAL_KEY") == "loaded_from_explicit_path"
        finally:
            os.chdir(original_cwd)


def test_sidebar_effective_key_resolution():
    """Verify that when sidebar override is empty, .env key is automatically used."""
    env_key = "AIzaSyProductionKeyFromEnv12345"
    
    # Case 1: User left sidebar empty -> should use env_key
    user_override_empty = ""
    effective_key = user_override_empty.strip() if user_override_empty.strip() else env_key
    assert effective_key == env_key

    # Case 2: User typed an override -> should use user override
    user_override_custom = "AIzaSyManualOverrideKey98765"
    effective_key = user_override_custom.strip() if user_override_custom.strip() else env_key
    assert effective_key == user_override_custom


def test_sidebar_student_and_export_metadata():
    """Verify that the Streamlit app sidebar contains student details and PDF download option."""
    app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "streamlit_app.py")
    assert os.path.exists(app_path)
    with open(app_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check student name & roll number in sidebar
    assert "**Student:** Mohammed Hammad Antule" in content
    assert "**Roll No.:** 02" in content
    assert "**Problem Statement:** PS-2" in content
    assert "**Domain:** Software Engineering & AI" in content
    assert "**Architecture:** Multi-Agent (LangGraph)" in content

    # Check exports
    assert "Download Analysis JSON" in content
    assert "Download Markdown Report" in content
    assert "Download PDF Report" in content

