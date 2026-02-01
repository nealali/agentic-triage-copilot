from uuid import UUID

from fastapi import APIRouter, HTTPException

from agent.schemas.issue import Issue, IssueCreate
from agent.schemas.run import AgentRunSummary
from agent.schemas.views import IssueOverview
from apps.api import storage

router = APIRouter(prefix="/issues", tags=["issues"])


@router.post("", response_model=Issue)
def create_issue(issue_create: IssueCreate) -> Issue:
    """
    Create a new issue.

    What this endpoint does:
    - Accepts an `IssueCreate` request body (the client input schema).
    - Creates a server-managed `Issue` (adds issue_id, created_at, status).
    - Stores it in the in-memory store for this MVP.

    Why this is important:
    - Issues become the "unit of work" for triage, analysis runs, and decisions.
    """
    return storage.BACKEND.create_issue(issue_create)


@router.get("", response_model=list[Issue])
def list_issues() -> list[Issue]:
    """
    List all issues.

    What this endpoint does:
    - Returns a list of all issues currently stored in memory.
    - If no issues exist, returns an empty list (this is normal).
    """
    return storage.BACKEND.list_issues()


@router.get("/{issue_id}", response_model=Issue)
def get_issue(issue_id: UUID) -> Issue:
    """
    Get a single issue by ID.

    What this endpoint does:
    - Looks up the issue_id in the store.
    - Returns the issue if found.
    - Returns HTTP 404 if not found.
    """
    issue = storage.BACKEND.get_issue(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    return issue


@router.get("/{issue_id}/overview", response_model=IssueOverview)
def get_issue_overview(issue_id: UUID, limit: int = 25) -> IssueOverview:
    """
    Return a UI-friendly overview for an issue.

    Why this endpoint exists:
    - A real UI often needs a "one call" view that includes the issue plus recent context.
    - This reduces the number of round-trips the UI has to make.

    What it returns:
    - issue
    - latest run summary (if any)
    - latest decision (if any)
    - recent audit events (most recent first)
    - counts
    """

    issue = storage.BACKEND.get_issue(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    # Latest run summary (if runs exist)
    latest_run_obj = storage.get_latest_run(issue_id)
    latest_run = AgentRunSummary.from_run(latest_run_obj) if latest_run_obj else None
    runs = storage.BACKEND.list_runs(issue_id)

    # Latest decision (most recent first)
    decisions = storage.BACKEND.list_decisions(issue_id)
    latest_decision = decisions[0] if decisions else None

    # Recent audit events (most recent first), limited for UI friendliness
    events = storage.BACKEND.query_audit(issue_id=issue_id)
    recent_events = list(reversed(events))[: max(0, limit)]

    return IssueOverview(
        issue=issue,
        latest_run=latest_run,
        latest_decision=latest_decision,
        recent_audit_events=recent_events,
        runs_count=len(runs),
        decisions_count=len(decisions),
    )
