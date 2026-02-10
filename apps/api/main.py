import json
import logging
import os
import time
from uuid import uuid4

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
from apps.api.routes.ingest import router as ingest_router
from apps.api.routes.issues import router as issues_router

# FastAPI application instance.
# FastAPI discovers routes attached to this app object.
app = FastAPI(title="Agentic Triage Copilot")

# CORS: allow React dev server (and configured origins) to call the API.
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# Logger for request-level structured logs.
# In production you would configure handlers/formatters (JSON logs, log shipping, etc.).
logger = logging.getLogger("agentic_triage_copilot.api")


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
app.include_router(ingest_router)
app.include_router(issues_router)
app.include_router(analyze_router)
app.include_router(decisions_router)
app.include_router(audit_router)
app.include_router(documents_router)
app.include_router(eval_router)


@app.get("/health")
def health():
    """Simple health check endpoint for monitoring and smoke tests."""

    return {"status": "ok"}
