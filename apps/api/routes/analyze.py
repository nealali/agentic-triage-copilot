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
from agent.schemas.analyze import AnalyzeRequest
from agent.schemas.audit import AuditEventType
from agent.schemas.issue import IssueStatus
from agent.schemas.run import AgentRun, AgentRunSummary
from apps.api import storage

router = APIRouter(prefix="/issues", tags=["analyze"])


def _build_doc_query(*, domain: str, rule_fired: str | None) -> str:
    """
    Build a simple, deterministic document search query (RAG-lite).

    Why:
    - Enterprise recommendations should be grounded in guidance.
    - For this MVP we keep retrieval explainable: keyword search + deterministic query strings.
    """

    base = domain.strip()
    if not rule_fired:
        return base

    rule = rule_fired.upper()
    if rule == "AE_DATE_INCONSISTENCY":
        return f"{base} date start end inconsistency"
    if rule == "MISSING_CRITICAL_FIELD":
        return f"{base} missing required field"
    if rule == "OUT_OF_RANGE_SIGNAL":
        return f"{base} out of range limits"
    if rule == "DUPLICATE_RECORD_SUSPECTED":
        return f"{base} duplicate record de-duplication"
    return base


@router.post("/{issue_id}/analyze", response_model=AgentRun)
def analyze(issue_id: UUID, req: AnalyzeRequest | None = None) -> AgentRun:
    """
    Run deterministic analysis for a single issue.

    What this endpoint does:
    - Loads the Issue (404 if missing)
    - Runs `analyze_issue(issue)` (deterministic rules)
    - Creates an AgentRun record (rules_version is stored for auditability)
    - Stores it under RUNS[issue_id]
    - Updates Issue.status to TRIAGED
    - Writes an audit event: ANALYZE_RUN_CREATED
    """

    issue = storage.BACKEND.get_issue(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    req = req or AnalyzeRequest()
    recommendation = analyze_issue(issue)
    # RAG-lite: attach citation IDs from ingested documents (if any).
    rule_fired = recommendation.tool_results.get("rule_fired")
    query = _build_doc_query(
        domain=issue.domain.value, rule_fired=str(rule_fired) if rule_fired else None
    )
    hits = storage.BACKEND.search_documents(query=query, limit=3)
    recommendation.citations = [str(h.doc_id) for h in hits]
    recommendation.tool_results["citation_hits"] = [
        {"doc_id": str(h.doc_id), "title": h.title, "source": h.source, "score": h.score}
        for h in hits
    ]
    # Replay metadata: link this run to a prior run_id (if provided).
    if req.replay_of_run_id is not None:
        recommendation.tool_results["replay_of_run_id"] = str(req.replay_of_run_id)

    run = AgentRun(
        issue_id=issue_id, rules_version=req.rules_version, recommendation=recommendation
    )

    storage.BACKEND.append_run(issue_id, run)
    storage.BACKEND.update_issue_status(issue_id, IssueStatus.TRIAGED)

    storage.BACKEND.add_audit_event(
        event_type=AuditEventType.ANALYZE_RUN_CREATED,
        actor="SYSTEM",
        issue_id=issue_id,
        run_id=run.run_id,
        details={
            "rules_version": run.rules_version,
            "rule_fired": recommendation.tool_results.get("rule_fired"),
            "replay_of_run_id": str(req.replay_of_run_id) if req.replay_of_run_id else None,
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

    issue = storage.BACKEND.get_issue(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    return storage.BACKEND.list_run_summaries(issue_id)
