"""
Decision routes (human-in-the-loop).

These endpoints let a human reviewer approve/override/edit the system output.
The key design goal is auditability:
- every decision is tied to a specific run_id
- overrides require a reason
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from agent.schemas.decision import Decision, DecisionCreate
from agent.schemas.issue import IssueStatus
from agent.schemas.recommendation import Action
from apps.api import storage
from apps.api.auth import auth_enabled, require_roles

router = APIRouter(prefix="/issues", tags=["decisions"])


@router.post("/{issue_id}/decisions", response_model=Decision)
def create_decision(
    issue_id: UUID,
    decision_create: DecisionCreate,
    _auth=Depends(require_roles({"reviewer", "admin"})),
) -> Decision:
    """
    Record a human decision for a specific issue/run.

    What this endpoint does:
    - Ensures the issue exists (404 if missing)
    - Ensures the run_id exists for this issue (404 if missing)
    - Stores the decision (most recent first)
    - Updates issue status:
        - IGNORE -> CLOSED
        - otherwise -> TRIAGED
    - Writes an audit event: DECISION_RECORDED

    Validation note:
    - Pydantic validates that OVERRIDE requires `reason`.
    """

    issue = storage.BACKEND.get_issue(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    # If auth is enabled, do not trust "reviewer" coming from the request body.
    # Enforce that the authenticated user matches the recorded reviewer.
    if auth_enabled() and decision_create.reviewer != _auth.user:
        raise HTTPException(status_code=403, detail="reviewer must match authenticated user")

    # Storage helper raises KeyError if run_id is not valid for this issue.
    try:
        decision = storage.BACKEND.append_decision(issue_id, decision_create)
    except KeyError:
        raise HTTPException(status_code=404, detail="run_id not found for this issue")

    # Status transition rule (simple MVP behavior)
    if decision.final_action == Action.IGNORE:
        storage.BACKEND.update_issue_status(issue_id, IssueStatus.CLOSED)
    else:
        storage.BACKEND.update_issue_status(issue_id, IssueStatus.TRIAGED)

    return decision


@router.get("/{issue_id}/decisions", response_model=list[Decision])
def list_decisions(issue_id: UUID) -> list[Decision]:
    """
    List all decisions for an issue (most recent first).

    Returns 404 if issue does not exist.
    """

    issue = storage.BACKEND.get_issue(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    return storage.BACKEND.list_decisions(issue_id)
