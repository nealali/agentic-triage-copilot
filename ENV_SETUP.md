# Environment Variables Setup

## Quick Fix for .env File Loading

The application now automatically loads `.env` file when starting. **You need to restart the API server** for changes to take effect.

## Your .env File

Your `.env` file should contain:

```env
OPENAI_API_KEY=sk-proj-...
LLM_ENABLED=1
LLM_MODEL=gpt-4o-mini
RAG_SEMANTIC=1
```

## Steps to Fix

1. **Restart the API server**:
   ```powershell
   # Stop the current server (Ctrl+C)
   # Then restart:
   uvicorn apps.api.main:app --reload
   ```

2. **Verify it's loaded**:
   - Check the server startup logs - you should see:
     - `OPENAI_API_KEY is set (length: XX)`
     - `LLM_ENABLED is set to true`
     - `RAG_SEMANTIC is set to true`

3. **Test in UI**:
   - Go to an issue detail page
   - Check "Use LLM enhancement" and "Use semantic RAG"
   - Click "Run analyze"
   - You should now see:
     - ✓ LLM: gpt-4o-mini (instead of warning)
     - Enhanced rationale
     - Citations from RAG

## Troubleshooting

### If LLM still doesn't work after restart:

1. **Check .env file location**:
   - Should be at: `c:\dev\agentic-triage-copilot\.env`
   - Not in `apps/api/.env` or `frontend/.env`

2. **Check API server logs**:
   - Look for: `OPENAI_API_KEY is set` or `OPENAI_API_KEY is not set`
   - If "not set", the .env file isn't being loaded

3. **Verify API key format**:
   - Should start with `sk-`
   - No extra spaces or quotes
   - No line breaks

4. **Manual test**:
   ```powershell
   python -c "from dotenv import load_dotenv; from pathlib import Path; import os; load_dotenv(dotenv_path=Path('.env')); print('API Key:', 'Set' if os.getenv('OPENAI_API_KEY') else 'Not set')"
   ```

### Alternative: Set environment variables directly

If .env loading doesn't work, you can set variables in PowerShell:

```powershell
$env:OPENAI_API_KEY="sk-proj-..."
$env:LLM_ENABLED="1"
$env:LLM_MODEL="gpt-4o-mini"
$env:RAG_SEMANTIC="1"

# Then start server
uvicorn apps.api.main:app --reload
```

## What Changed

- ✅ Added `load_dotenv()` to `apps/api/main.py` to load `.env` file
- ✅ Added logging to show when environment variables are loaded
- ✅ Updated `.env` file with correct variable names (`LLM_MODEL` instead of `MODEL_NAME`)

## Next Steps

1. **Restart your API server** (this is critical!)
2. Try running analyze again
3. You should see LLM enhancement working now
