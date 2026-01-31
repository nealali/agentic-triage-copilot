from uuid import UUID

from fastapi import APIRouter, HTTPException

from agent.schemas.issue import Issue, IssueCreate
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
    return storage.create_issue(issue_create)


@router.get("", response_model=list[Issue])
def list_issues() -> list[Issue]:
    """
    List all issues.

    What this endpoint does:
    - Returns a list of all issues currently stored in memory.
    - If no issues exist, returns an empty list (this is normal).
    """
    return storage.list_issues()


@router.get("/{issue_id}", response_model=Issue)
def get_issue(issue_id: UUID) -> Issue:
    """
    Get a single issue by ID.

    What this endpoint does:
    - Looks up the issue_id in the store.
    - Returns the issue if found.
    - Returns HTTP 404 if not found.
    """
    issue = storage.get_issue(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    return issue
