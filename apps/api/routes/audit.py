"""
Audit routes.

Audit endpoints expose append-only audit events so the system is explainable:
- what happened
- when it happened
- who/what performed the action
"""

from uuid import UUID

from fastapi import APIRouter

from agent.schemas.audit import AuditEvent
from apps.api import storage

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=list[AuditEvent])
def query_audit(issue_id: UUID | None = None, run_id: UUID | None = None) -> list[AuditEvent]:
    """
    Query audit events, optionally filtered by issue_id and/or run_id.

    Examples:
    - GET /audit                       -> all events
    - GET /audit?issue_id=<uuid>       -> events for one issue
    - GET /audit?run_id=<uuid>         -> events for one run
    - GET /audit?issue_id=...&run_id=... -> events matching both
    """

    return storage.query_audit(issue_id=issue_id, run_id=run_id)
