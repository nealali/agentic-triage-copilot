"""
Evaluation routes.

This is a lightweight "export hook" for now.
The goal is to make it easy to:
- pull structured run outputs
- compute scorecards/metrics externally

Later, this can evolve into a proper evaluation harness (gold sets, metrics, reports).
"""

from fastapi import APIRouter

from apps.api import storage
from eval.scorecard import build_scorecard_rows

router = APIRouter(prefix="/eval", tags=["eval"])


@router.get("/scorecard", response_model=list[dict])
def scorecard() -> list[dict]:
    """
    Export a simple scorecard view of stored runs.

    For each run we export:
    - issue_id, run_id, created_at
    - severity, action, confidence
    - rule_fired (from deterministic tool_results)
    """

    return build_scorecard_rows(storage.BACKEND.runs_by_issue())
