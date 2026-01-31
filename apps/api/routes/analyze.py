"""
Analyze routes.

These endpoints run deterministic analysis against an issue.
Each analysis call creates a new `AgentRun` record so you get:
- history (multiple runs over time)
- auditability (what rule fired, what version was used)
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from agent.analyze.deterministic import analyze_issue
from agent.schemas.audit import AuditEventType
from agent.schemas.issue import IssueStatus
from agent.schemas.run import AgentRun, AgentRunSummary
from apps.api import storage

router = APIRouter(prefix="/issues", tags=["analyze"])


@router.post("/{issue_id}/analyze", response_model=AgentRun)
def analyze(issue_id: UUID) -> AgentRun:
    """
    Run deterministic analysis for a single issue.

    What this endpoint does:
    - Loads the Issue (404 if missing)
    - Runs `analyze_issue(issue)` (deterministic rules)
    - Creates an AgentRun record (rules_version v0.1)
    - Stores it under RUNS[issue_id]
    - Updates Issue.status to TRIAGED
    - Writes an audit event: ANALYZE_RUN_CREATED
    """

    issue = storage.get_issue(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    recommendation = analyze_issue(issue)
    run = AgentRun(issue_id=issue_id, rules_version="v0.1", recommendation=recommendation)

    storage.append_run(issue_id, run)
    storage.update_issue_status(issue_id, IssueStatus.TRIAGED)

    storage.add_audit_event(
        event_type=AuditEventType.ANALYZE_RUN_CREATED,
        actor="SYSTEM",
        issue_id=issue_id,
        run_id=run.run_id,
        details={
            "rules_version": run.rules_version,
            "rule_fired": recommendation.tool_results.get("rule_fired"),
        },
    )

    return run


@router.get("/{issue_id}/runs", response_model=list[AgentRunSummary])
def list_runs(issue_id: UUID) -> list[AgentRunSummary]:
    """
    List run history for an issue (summary view).

    Returns 404 if the issue does not exist. This keeps behavior consistent with other
    issue-scoped endpoints.
    """

    issue = storage.get_issue(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    return storage.list_run_summaries(issue_id)
