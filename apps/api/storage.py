"""
In-memory storage for the FastAPI MVP.

Important concept (learning-friendly)
------------------------------------
Right now, we are storing data in plain Python data structures:
- dictionaries (dict)
- lists

This is great for an MVP because:
- it's fast to build
- it's easy to test
- it runs without installing/configuring a database

But it has a big limitation:
- **it resets on server restart**

In a production system, this module would be replaced by a database layer
(e.g., Postgres + SQLAlchemy). We keep a clean API (helper functions) so the
rest of the app doesn't care *how* data is stored.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from agent.schemas.audit import AuditEvent, AuditEventType
from agent.schemas.decision import Decision, DecisionCreate
from agent.schemas.issue import Issue, IssueCreate, IssueStatus
from agent.schemas.run import AgentRun, AgentRunSummary

# -----------------------
# Global in-memory stores
# -----------------------

# Issues by issue_id
ISSUES: dict[UUID, Issue] = {}

# Runs keyed by issue_id (each issue can have multiple runs)
RUNS: dict[UUID, list[AgentRun]] = {}

# Decisions keyed by issue_id (most recent first)
DECISIONS: dict[UUID, list[Decision]] = {}

# Audit events: append-only timeline
AUDIT: list[AuditEvent] = []


# -----------------------
# Helper functions (CRUD)
# -----------------------

def reset_in_memory_store() -> None:
    """
    Clear all global stores.

    Why this exists:
    - Tests need isolation. One test shouldn't affect another.
    - This makes it easy to do `reset_in_memory_store()` in a pytest fixture.
    """

    ISSUES.clear()
    RUNS.clear()
    DECISIONS.clear()
    AUDIT.clear()


def add_audit_event(
    *,
    event_type: AuditEventType,
    actor: str,
    issue_id: UUID | None = None,
    run_id: UUID | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """
    Append an AuditEvent to the in-memory audit log.

    We keep audit events small, structured, and append-only.
    """

    event = AuditEvent(
        event_type=event_type,
        created_at=datetime.utcnow(),
        actor=actor,
        issue_id=issue_id,
        run_id=run_id,
        details=details or {},
    )
    AUDIT.append(event)
    return event


def query_audit(*, issue_id: UUID | None = None, run_id: UUID | None = None) -> list[AuditEvent]:
    """
    Filter audit events by issue_id and/or run_id.

    This is intentionally simple for the MVP. In a database-backed system, this would
    become a SQL query with indexes.
    """

    results: list[AuditEvent] = []
    for event in AUDIT:
        if issue_id is not None and event.issue_id != issue_id:
            continue
        if run_id is not None and event.run_id != run_id:
            continue
        results.append(event)
    return results


def create_issue(issue_create: IssueCreate) -> Issue:
    """
    Create and store a new Issue from IssueCreate input.

    Pydantic v2 note:
    - `model_dump()` converts the model into a plain dict.
    """

    issue = Issue(**issue_create.model_dump())
    ISSUES[issue.issue_id] = issue

    # Record an audit event so the system is explainable.
    add_audit_event(
        event_type=AuditEventType.ISSUE_CREATED,
        actor="SYSTEM",
        issue_id=issue.issue_id,
        details={"source": issue.source, "domain": issue.domain, "subject_id": issue.subject_id},
    )
    return issue


def list_issues() -> list[Issue]:
    """Return all issues currently stored in memory."""

    return list(ISSUES.values())


def get_issue(issue_id: UUID) -> Issue | None:
    """Return an issue by ID, or None if not found."""

    return ISSUES.get(issue_id)


def update_issue_status(issue_id: UUID, status: IssueStatus) -> Issue | None:
    """
    Update issue.status and return the updated issue.

    This keeps status transitions centralized and auditable.
    """

    issue = ISSUES.get(issue_id)
    if issue is None:
        return None

    # Pydantic models are mutable by default unless configured otherwise.
    # We update the status and write back to the store for clarity.
    issue.status = status
    ISSUES[issue_id] = issue

    add_audit_event(
        event_type=AuditEventType.ISSUE_UPDATED,
        actor="SYSTEM",
        issue_id=issue_id,
        details={"status": status},
    )
    return issue


def append_run(issue_id: UUID, run: AgentRun) -> None:
    """
    Store a run record for an issue.

    We keep runs per-issue so you can list analysis history.
    """

    RUNS.setdefault(issue_id, []).append(run)


def list_run_summaries(issue_id: UUID) -> list[AgentRunSummary]:
    """
    Return compact run summaries for list views.

    If the issue has no runs, return an empty list.
    """

    runs = RUNS.get(issue_id, [])
    return [AgentRunSummary.from_run(r) for r in runs]


def get_run(issue_id: UUID, run_id: UUID) -> AgentRun | None:
    """Return a specific run for an issue, or None if not found."""

    for run in RUNS.get(issue_id, []):
        if run.run_id == run_id:
            return run
    return None


def append_decision(issue_id: UUID, decision_create: DecisionCreate) -> Decision:
    """
    Store a decision for an issue (most recent first).

    We require that the decision is tied to an existing run, which improves auditability.
    """

    # Safety check: ensure the referenced run exists for this issue.
    run = get_run(issue_id, decision_create.run_id)
    if run is None:
        raise KeyError("run_id not found for this issue")

    decision = Decision(
        issue_id=issue_id,
        run_id=decision_create.run_id,
        decision_type=decision_create.decision_type,
        final_action=decision_create.final_action,
        final_text=decision_create.final_text,
        reviewer=decision_create.reviewer,
        reason=decision_create.reason,
        timestamp=decision_create.timestamp,
    )

    # Most recent first makes it easy for UIs to show the latest decision at the top.
    DECISIONS.setdefault(issue_id, []).insert(0, decision)

    add_audit_event(
        event_type=AuditEventType.DECISION_RECORDED,
        actor=decision.reviewer,
        issue_id=issue_id,
        run_id=decision.run_id,
        details={
            "decision_type": decision.decision_type,
            "final_action": decision.final_action,
            "decision_id": str(decision.decision_id),
        },
    )

    # Apply a simple status transition rule:
    # - If final_action is IGNORE, we consider the issue closed (no further work).
    # - Otherwise, it remains triaged.
    issue = ISSUES.get(issue_id)
    if issue is not None:
        issue.status = IssueStatus.CLOSED if decision.final_action == "IGNORE" else IssueStatus.TRIAGED
        ISSUES[issue_id] = issue

    return decision


def list_decisions(issue_id: UUID) -> list[Decision]:
    """
    List decisions for an issue (most recent first).
    Returns an empty list if none exist.
    """

    return DECISIONS.get(issue_id, [])
