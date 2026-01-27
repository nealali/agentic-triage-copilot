from uuid import UUID

from fastapi import APIRouter, HTTPException

from agent.schemas.issue import Issue, IssueCreate
from apps.api.storage import ISSUES

router = APIRouter(prefix="/issues", tags=["issues"])


@router.post("", response_model=Issue)
def create_issue(issue_create: IssueCreate) -> Issue:
    """
    Create a new issue from the provided IssueCreate data.
    Generates a new UUID, sets created_at timestamp, and stores it in memory.
    """
    # Create Issue from IssueCreate using model_dump() and add required fields
    issue_data = issue_create.model_dump()
    issue = Issue(
        **issue_data,
        status="open"  # Default status for new issues
    )
    
    # Store the issue in memory
    ISSUES[issue.issue_id] = issue
    
    return issue


@router.get("", response_model=list[Issue])
def list_issues() -> list[Issue]:
    """
    Retrieve all issues from the in-memory store.
    Returns an empty list if no issues exist.
    """
    return list(ISSUES.values())


@router.get("/{issue_id}", response_model=Issue)
def get_issue(issue_id: UUID) -> Issue:
    """
    Retrieve a specific issue by its UUID.
    Returns 404 if the issue is not found.
    """
    if issue_id not in ISSUES:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    return ISSUES[issue_id]
