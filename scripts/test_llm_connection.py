"""Test LLM connection and API key."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

print("=" * 60)
print("LLM Connection Test")
print("=" * 60)

# Check environment variables
api_key = os.getenv("OPENAI_API_KEY")
llm_enabled = os.getenv("LLM_ENABLED", "").strip().lower() in ("1", "true", "yes")

print("\n1. Environment Variables:")
print(f"   OPENAI_API_KEY: {'Set' if api_key else 'NOT SET'}")
if api_key:
    print(f"   API Key length: {len(api_key)}")
    print(f"   API Key starts with 'sk-': {api_key.startswith('sk-')}")
print(f"   LLM_ENABLED: {llm_enabled}")

# Check OpenAI import
print("\n2. OpenAI Library:")
try:
    from openai import OpenAI

    print("   OK OpenAI library imported successfully")
except ImportError as e:
    print(f"   X OpenAI library import failed: {e}")
    print("   Run: pip install openai")
    sys.exit(1)

# Try to create client
print("\n3. Client Creation:")
if not api_key:
    print("   X Cannot create client - API key not set")
    sys.exit(1)

try:
    client = OpenAI(api_key=api_key)
    print("   OK OpenAI client created successfully")
except Exception as e:
    print(f"   X Client creation failed: {type(e).__name__}: {e}")
    sys.exit(1)

# Try a simple API call
print("\n4. API Call Test:")
try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say 'test'"}],
        max_tokens=5,
    )
    print("   OK API call successful")
    print(f"   Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"   X API call failed: {type(e).__name__}: {e}")
    if "api_key" in str(e).lower() or "authentication" in str(e).lower():
        print("   → This suggests the API key is invalid or expired")
    elif "rate" in str(e).lower() or "quota" in str(e).lower():
        print("   → This suggests rate limiting or quota issues")
    else:
        print("   → Check your OpenAI account and API key")
    sys.exit(1)

print("\n" + "=" * 60)
print("All tests passed! LLM should work.")
print("=" * 60)
