"""
Configuration and Environment settings for Intelligent Software Requirement Analyst.
Handles Gemini API client initialization and runtime options.
Guarantees reliable loading from the project root .env file regardless of invocation directory.
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv

# Explicitly resolve project root directory and .env location
PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE_PATH: str = os.path.join(PROJECT_ROOT, ".env")

# Always load the project-root .env file with override enabled
if os.path.exists(ENV_FILE_PATH):
    load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
else:
    load_dotenv()

# Configure basic logging
LOG_FORMAT = "%(asctime)s - [%(levelname)s] - %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("RequirementAnalyst")

# Configuration constants
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
GEMINI_FALLBACK_MODEL: str = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite").strip()
PORT: int = int(os.getenv("PORT", "8000"))
HOST: str = os.getenv("HOST", "0.0.0.0")
FASTAPI_BACKEND_URL: str = os.getenv("FASTAPI_BACKEND_URL", "http://localhost:8000").rstrip("/")

OUTPUT_DIR: str = os.path.join(PROJECT_ROOT, "output")
SAMPLE_DATA_DIR: str = os.path.join(PROJECT_ROOT, "sample_data")

# Ensure required directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SAMPLE_DATA_DIR, exist_ok=True)


def reload_env() -> None:
    """Explicitly reload environment variables from the project root .env file."""
    global GEMINI_API_KEY, GEMINI_MODEL, GEMINI_FALLBACK_MODEL, PORT, HOST, FASTAPI_BACKEND_URL
    if os.path.exists(ENV_FILE_PATH):
        load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
    GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite").strip()
    PORT = int(os.getenv("PORT", "8000"))
    HOST = os.getenv("HOST", "0.0.0.0")
    FASTAPI_BACKEND_URL = os.getenv("FASTAPI_BACKEND_URL", "http://localhost:8000").rstrip("/")




def is_api_key_valid(api_key: Optional[str] = None) -> bool:
    """Check if the provided or configured Gemini API key is valid (not empty and not placeholder)."""
    key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    if not key:
        return False
    lower_key = key.lower()
    if any(placeholder in lower_key for placeholder in ["your_", "placeholder", "api_key_here", "model_name_here"]):
        return False
    return len(key) >= 15



def get_masked_api_key(api_key: Optional[str] = None) -> str:
    """Return a safely masked representation of the API key for UI/logging display."""
    key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    if not is_api_key_valid(key):
        return "Not Configured"
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def get_gemini_client(api_key: Optional[str] = None):
    """
    Instantiate and return the Google GenAI client using the official google-genai SDK.
    Raises ValueError with actionable instructions if the key is missing or invalid.
    """
    key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    
    if not is_api_key_valid(key):
        raise ValueError(
            "GEMINI_API_KEY is not configured or is using placeholder text. "
            "Please set a valid Gemini API key in your .env file or Streamlit sidebar."
        )

    try:
        from google import genai
        # Initialize client with resolved key
        client = genai.Client(api_key=key)
        effective_model = os.getenv("GEMINI_MODEL", GEMINI_MODEL).strip()
        logger.info("Successfully initialized Google GenAI Client with model: %s", effective_model)
        return client
    except Exception as e:
        logger.error("Failed to initialize Google GenAI Client: %s", str(e))
        raise RuntimeError(f"Could not initialize Google GenAI Client: {e}") from e
