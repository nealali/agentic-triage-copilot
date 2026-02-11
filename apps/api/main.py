import json
import logging
import os
import time
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

from apps.api.correlation import set_correlation_id
from apps.api.routes.analyze import router as analyze_router
from apps.api.routes.audit import router as audit_router
from apps.api.routes.decisions import router as decisions_router
from apps.api.routes.documents import router as documents_router
from apps.api.routes.eval import router as eval_router
from apps.api.routes.health import router as health_router
from apps.api.routes.ingest import router as ingest_router
from apps.api.routes.issues import router as issues_router

# Load environment variables from .env file (if it exists)
# This allows OPENAI_API_KEY, LLM_ENABLED, etc. to be set in .env
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Logger for request-level structured logs.
# In production you would configure handlers/formatters (JSON logs, log shipping, etc.).
logging.basicConfig(
    level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s"  # Better format for debugging
)
logger = logging.getLogger("agentic_triage_copilot.api")

# FastAPI application instance.
# FastAPI discovers routes attached to this app object.
app = FastAPI(title="Agentic Triage Copilot")

# Log environment status (for debugging)
if os.getenv("OPENAI_API_KEY"):
    logger.info("OPENAI_API_KEY is set (length: %d)", len(os.getenv("OPENAI_API_KEY", "")))
else:
    logger.warning("OPENAI_API_KEY is not set - LLM features will not work")
if os.getenv("LLM_ENABLED", "").strip().lower() in ("1", "true", "yes"):
    logger.info("LLM_ENABLED is set to true")
if os.getenv("RAG_SEMANTIC", "").strip().lower() in ("1", "true", "yes"):
    logger.info("RAG_SEMANTIC is set to true")

# Check if OpenAI library is available
try:
    from openai import OpenAI  # type: ignore[import-untyped]  # noqa: F401

    logger.info("OpenAI library is available")
except ImportError:
    logger.error(
        "OpenAI library is NOT installed - LLM features will fail. Run: pip install openai"
    )

# CORS: allow React dev server (and configured origins) to call the API.
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)


# Middleware: attach a correlation ID to every request.
# This makes it easy to trace requests in logs and audit trails.
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next) -> Response:
    correlation_id = uuid4()
    set_correlation_id(correlation_id)

    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000.0

    # Structured log line (JSON string) so it is easy to parse in log tools.
    # We keep fields small and stable for enterprise observability.
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "correlation_id": str(correlation_id),
            }
        )
    )
    response.headers["X-Correlation-ID"] = str(correlation_id)
    return response


# Register routers (API modules).
# Keeping routers in separate files is a clean-architecture pattern:
# - main.py stays small and readable
# - each router focuses on one area (issues/analyze/decisions/audit/eval)
app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(issues_router)
app.include_router(analyze_router)
app.include_router(decisions_router)
app.include_router(audit_router)
app.include_router(documents_router)
app.include_router(eval_router)


# Auto-ingest RAG documents on startup (if enabled)
def _auto_ingest_rag_documents() -> None:
    """Automatically ingest mock RAG documents on startup if enabled."""
    auto_ingest = os.getenv("AUTO_INGEST_RAG_DOCUMENTS", "").strip().lower() in ("1", "true", "yes")
    if not auto_ingest:
        return

    try:
        import sys
        from pathlib import Path

        # Add scripts directory to path
        scripts_dir = Path(__file__).parent.parent.parent / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        from ingest_mock_documents import MOCK_DOCUMENTS

        from agent.schemas.document import DocumentCreate
        from apps.api import storage

        existing_docs = storage.BACKEND.list_documents()
        existing_titles = {doc.title for doc in existing_docs}

        ingested_count = 0
        skipped_count = 0

        for doc_data in MOCK_DOCUMENTS:
            # Skip if document already exists (by title)
            if doc_data["title"] in existing_titles:
                skipped_count += 1
                continue

            try:
                doc_create = DocumentCreate(**doc_data)
                storage.BACKEND.ingest_document(doc_create)
                ingested_count += 1
            except Exception as e:
                logger.warning(f"Failed to auto-ingest document '{doc_data['title']}': {e}")

        if ingested_count > 0:
            logger.info(
                f"Auto-ingested {ingested_count} RAG documents on startup (skipped {skipped_count} existing)"
            )
        elif skipped_count > 0:
            logger.info(f"All {skipped_count} RAG documents already exist, skipping auto-ingest")
    except ImportError as e:
        logger.warning(f"Could not import mock documents for auto-ingest: {e}")
    except Exception as e:
        logger.error(f"Error during auto-ingest of RAG documents: {e}")


# Run auto-ingest after routers are registered
_auto_ingest_rag_documents()


@app.get("/health")
def health():
    """Simple health check endpoint for monitoring and smoke tests."""

    return {"status": "ok"}
