"""Health check and diagnostic endpoints."""

import os
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Basic health check endpoint."""
    return {"status": "ok"}


@router.get("/health/llm")
def llm_health_check():
    """
    Check LLM configuration and availability.

    Returns diagnostic information about LLM setup.
    """
    from dotenv import load_dotenv

    # Load .env file
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    load_dotenv(dotenv_path=env_path, override=True)

    api_key = os.getenv("OPENAI_API_KEY")
    llm_enabled = os.getenv("LLM_ENABLED", "").strip().lower() in ("1", "true", "yes")

    # Check if OpenAI library is installed
    try:
        from openai import OpenAI

        openai_available = True
        openai_error = None
    except ImportError as e:
        openai_available = False
        openai_error = str(e)

    # Try to create client
    client_created = False
    client_error = None
    if openai_available and api_key:
        try:
            client = OpenAI(api_key=api_key)
            client_created = True
        except Exception as e:
            client_error = f"{type(e).__name__}: {str(e)}"

    # Try a simple API call
    api_call_works = False
    api_call_error = None
    if client_created:
        try:
            _ = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Say 'test'"}],
                max_tokens=5,
            )
            api_call_works = True
        except Exception as e:
            api_call_error = f"{type(e).__name__}: {str(e)}"

    return {
        "llm_enabled": llm_enabled,
        "api_key_set": bool(api_key),
        "api_key_length": len(api_key) if api_key else 0,
        "openai_library_installed": openai_available,
        "openai_import_error": openai_error,
        "client_created": client_created,
        "client_error": client_error,
        "api_call_works": api_call_works,
        "api_call_error": api_call_error,
        "status": "ok" if (api_call_works) else "degraded" if (client_created) else "failed",
    }
