"""
Scorecard export helpers (pure functions).

Why a "pure function" here?
---------------------------
A pure function is a function that:
- depends only on its inputs
- has no side effects (doesn't mutate global state)

This is helpful because:
- it's easy to test
- it's easy to reuse in different contexts (API, batch job, notebook)

In this MVP, the FastAPI endpoint /eval/scorecard calls into this module.
Later you can add more evaluation metrics without changing the API layer much.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from agent.schemas.run import AgentRun


def build_scorecard_rows(runs_by_issue: dict[UUID, list[AgentRun]]) -> list[dict[str, Any]]:
    """
    Convert stored runs into simple "scorecard" rows.

    Output row fields (as requested):
    - issue_id
    - run_id
    - created_at
    - severity
    - action
    - confidence
    - rule_fired

    Notes:
    - We keep the output as plain dicts so it's easy to export to CSV/JSON later.
    - We intentionally do not include the full evidence/tool payload (too large).
    """

    rows: list[dict[str, Any]] = []

    # We iterate in a stable order: by issue_id, then by run.created_at
    # This makes exports predictable and easier to diff.
    for issue_id in sorted(runs_by_issue.keys(), key=lambda u: str(u)):
        runs = runs_by_issue.get(issue_id, [])
        runs_sorted = sorted(runs, key=lambda r: r.created_at)

        for run in runs_sorted:
            rec = run.recommendation
            rule_fired = None
            if isinstance(rec.tool_results, dict):
                rule_fired = rec.tool_results.get("rule_fired")

            rows.append(
                {
                    "issue_id": str(run.issue_id),
                    "run_id": str(run.run_id),
                    "created_at": run.created_at.isoformat(),
                    "severity": rec.severity,
                    "action": rec.action,
                    "confidence": rec.confidence,
                    "rule_fired": rule_fired,
                }
            )

    return rows
