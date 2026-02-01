"""
Tests for PostgresStorageBackend.

Why test with SQLite?
---------------------
We want to test the *logic* of the database backend without requiring a real Postgres
instance in every developer environment.

SQLAlchemy supports multiple databases via "database URLs".
Using SQLite in tests gives us:
- fast tests
- no external services required

In CI/production you can also add an integration test job with a real Postgres container.
"""

from __future__ import annotations

from uuid import UUID

from agent.analyze.deterministic import analyze_issue
from agent.schemas.decision import DecisionCreate, DecisionType
from agent.schemas.issue import IssueCreate, IssueDomain, IssueSource, IssueStatus
from agent.schemas.recommendation import Action
from agent.schemas.run import AgentRun
from apps.api.storage import PostgresStorageBackend


def test_postgres_storage_backend_round_trip(tmp_path) -> None:
    """
    End-to-end storage test:
    - create issue
    - update status
    - add run
    - add decision
    - query audit
    """

    db_path = tmp_path / "triage_test.sqlite"
    backend = PostgresStorageBackend(f"sqlite:///{db_path}", auto_create_schema=True)
    backend.reset()

    issue_create = IssueCreate(
        source=IssueSource.MANUAL,
        domain=IssueDomain.AE,
        subject_id="SUBJ-1",
        fields=["AESTDTC", "AEENDTC"],
        description="AE end before start",
        evidence_payload={"start_date": "2024-01-10", "end_date": "2024-01-01"},
    )
    issue = backend.create_issue(issue_create)
    assert isinstance(issue.issue_id, UUID)

    # Status update persists
    updated = backend.update_issue_status(issue.issue_id, IssueStatus.TRIAGED)
    assert updated is not None
    assert updated.status == IssueStatus.TRIAGED

    # Add a run
    rec = analyze_issue(issue)
    run = AgentRun(issue_id=issue.issue_id, rules_version="v0.1", recommendation=rec)
    backend.append_run(issue.issue_id, run)
    runs = backend.list_runs(issue.issue_id)
    assert len(runs) == 1
    assert runs[0].run_id == run.run_id

    # Add a decision tied to run
    decision_create = DecisionCreate(
        run_id=run.run_id,
        decision_type=DecisionType.APPROVE,
        final_action=Action.QUERY_SITE,
        final_text="Send site query.",
        reviewer="tester",
        reason=None,
    )
    decision = backend.append_decision(issue.issue_id, decision_create)
    assert decision.issue_id == issue.issue_id
    assert decision.run_id == run.run_id

    decisions = backend.list_decisions(issue.issue_id)
    assert len(decisions) == 1

    audit = backend.query_audit(issue_id=issue.issue_id)
    assert len(audit) >= 2  # at least issue created + status updated
    assert any(e.event_type.value == "ISSUE_CREATED" for e in audit)

