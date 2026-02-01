"""
View models (Pydantic v2) for API responses.

Why do we need "view models"?
-----------------------------
Your core schemas (Issue, AgentRun, Decision, AuditEvent) represent individual records.

In real applications, frontends rarely want "just one table".
They usually want a *composed view* like:
  "Show me the issue, the latest run, the latest decision, and recent audit events."

This module defines those combined response shapes in a typed, validated way.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from agent.schemas.audit import AuditEvent
from agent.schemas.decision import Decision
from agent.schemas.issue import Issue
from agent.schemas.run import AgentRunSummary


class IssueOverview(BaseModel):
    """
    A UI-friendly overview for a single issue.

    This is intended for "issue detail" screens where you want:
    - the issue itself
    - the latest analysis run (if any)
    - the latest human decision (if any)
    - recent audit events for the timeline
    - counts to support quick badges in the UI
    """

    issue: Issue = Field(..., description="The issue record.")
    latest_run: AgentRunSummary | None = Field(
        default=None,
        description="Most recent analysis run summary (if the issue has been analyzed).",
    )
    latest_decision: Decision | None = Field(
        default=None,
        description="Most recent human decision for this issue (if any).",
    )
    recent_audit_events: list[AuditEvent] = Field(
        default_factory=list,
        description="Recent audit events for this issue (most recent first).",
    )
    runs_count: int = Field(..., ge=0, description="Total number of runs for this issue.")
    decisions_count: int = Field(
        ..., ge=0, description="Total number of decisions recorded for this issue."
    )
