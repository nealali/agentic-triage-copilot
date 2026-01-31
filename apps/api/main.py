from fastapi import FastAPI

from apps.api.routes.analyze import router as analyze_router
from apps.api.routes.audit import router as audit_router
from apps.api.routes.decisions import router as decisions_router
from apps.api.routes.eval import router as eval_router
from apps.api.routes.issues import router as issues_router

# FastAPI application instance.
# FastAPI discovers routes attached to this app object.
app = FastAPI(title="Agentic Triage Copilot")

# Register routers (API modules).
# Keeping routers in separate files is a clean-architecture pattern:
# - main.py stays small and readable
# - each router focuses on one area (issues/analyze/decisions/audit/eval)
app.include_router(issues_router)
app.include_router(analyze_router)
app.include_router(decisions_router)
app.include_router(audit_router)
app.include_router(eval_router)


@app.get("/health")
def health():
    """Simple health check endpoint for monitoring and smoke tests."""

    return {"status": "ok"}
