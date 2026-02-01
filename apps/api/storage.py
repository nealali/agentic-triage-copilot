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

import os
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from agent.schemas.audit import AuditEvent, AuditEventType
from agent.schemas.decision import Decision, DecisionCreate
from agent.schemas.issue import Issue, IssueCreate, IssueStatus
from agent.schemas.run import AgentRun, AgentRunSummary
from apps.api.correlation import get_correlation_id

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


# -----------------------------
# Storage interface (swap-ready)
# -----------------------------
#
# Why define an interface now?
# - Today we store data in memory (fast MVP).
# - Later we want to swap to Postgres without rewriting route handlers.
# - An interface makes the boundary explicit: "these are the operations storage must support".
#
# This is a strong "enterprise" signal because it shows you are designing for change.


class StorageBackend(Protocol):
    """Interface that any storage backend (in-memory, Postgres, etc.) must implement."""

    def reset(self) -> None: ...

    def create_issue(self, issue_create: IssueCreate) -> Issue: ...
    def list_issues(self) -> list[Issue]: ...
    def get_issue(self, issue_id: UUID) -> Issue | None: ...
    def update_issue_status(self, issue_id: UUID, status: IssueStatus) -> Issue | None: ...

    def append_run(self, issue_id: UUID, run: AgentRun) -> None: ...
    def list_runs(self, issue_id: UUID) -> list[AgentRun]: ...
    def list_run_summaries(self, issue_id: UUID) -> list[AgentRunSummary]: ...
    def runs_by_issue(self) -> dict[UUID, list[AgentRun]]: ...

    def append_decision(self, issue_id: UUID, decision_create: DecisionCreate) -> Decision: ...
    def list_decisions(self, issue_id: UUID) -> list[Decision]: ...

    def add_audit_event(
        self,
        *,
        event_type: AuditEventType,
        actor: str,
        issue_id: UUID | None = None,
        run_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent: ...

    def query_audit(
        self, *, issue_id: UUID | None = None, run_id: UUID | None = None
    ) -> list[AuditEvent]: ...


class InMemoryStorageBackend:
    """
    In-memory implementation of StorageBackend.

    This class delegates to the module-level functions below.
    It's mainly here to demonstrate the "swappable storage" pattern cleanly.
    """

    def reset(self) -> None:
        reset_in_memory_store()

    def create_issue(self, issue_create: IssueCreate) -> Issue:
        return create_issue(issue_create)

    def list_issues(self) -> list[Issue]:
        return list_issues()

    def get_issue(self, issue_id: UUID) -> Issue | None:
        return get_issue(issue_id)

    def update_issue_status(self, issue_id: UUID, status: IssueStatus) -> Issue | None:
        return update_issue_status(issue_id, status)

    def append_run(self, issue_id: UUID, run: AgentRun) -> None:
        append_run(issue_id, run)

    def list_runs(self, issue_id: UUID) -> list[AgentRun]:
        return list_runs(issue_id)

    def list_run_summaries(self, issue_id: UUID) -> list[AgentRunSummary]:
        return list_run_summaries(issue_id)

    def runs_by_issue(self) -> dict[UUID, list[AgentRun]]:
        # Return the underlying in-memory mapping.
        # Important: do NOT call the module-level `runs_by_issue()` helper here,
        # because that helper delegates to BACKEND and would create recursion.
        return RUNS

    def append_decision(self, issue_id: UUID, decision_create: DecisionCreate) -> Decision:
        return append_decision(issue_id, decision_create)

    def list_decisions(self, issue_id: UUID) -> list[Decision]:
        return list_decisions(issue_id)

    def add_audit_event(
        self,
        *,
        event_type: AuditEventType,
        actor: str,
        issue_id: UUID | None = None,
        run_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return add_audit_event(
            event_type=event_type, actor=actor, issue_id=issue_id, run_id=run_id, details=details
        )

    def query_audit(
        self, *, issue_id: UUID | None = None, run_id: UUID | None = None
    ) -> list[AuditEvent]:
        return query_audit(issue_id=issue_id, run_id=run_id)


class PostgresStorageBackend:
    """
    Postgres-backed implementation of StorageBackend (production path).

    In-memory vs Postgres (why this exists)
    --------------------------------------
    - In-memory is great for fast MVP iteration, but you lose all data on restart.
    - Postgres keeps issues/runs/decisions/audit events **persistent** so you can
      review historical decisions and support inspection-ready traceability.

    Design choices (keep it simple for learning)
    --------------------------------------------
    - Use SQLAlchemy Core (tables + SQL) instead of the ORM.
    - Store UUIDs as strings for portability (SQLite tests / Postgres production).
    - Store structured payloads as JSON columns.
    """

    def __init__(self, database_url: str, *, auto_create_schema: bool = True) -> None:
        # We import SQLAlchemy inside __init__ so the rest of the file stays readable.
        # (It also keeps the in-memory story clear.)
        from sqlalchemy import (
            JSON,
            Column,
            DateTime,
            ForeignKey,
            MetaData,
            String,
            Table,
            Text,
            create_engine,
            delete,
            select,
            update,
        )

        self._delete = delete
        self._select = select
        self._update = update

        # Engine manages DB connections.
        self._engine = create_engine(database_url, future=True)

        # UUID handling (production vs tests)
        # -------------------------------
        # Our Alembic migration defines UUID columns for Postgres.
        # In tests we use SQLite, which doesn't have a native UUID type.
        #
        # This backend supports both by:
        # - using native UUID columns in Postgres
        # - using String(36) columns in SQLite
        self._use_native_uuid = self._engine.dialect.name == "postgresql"
        if self._use_native_uuid:
            # Postgres-native UUID columns (matches Alembic migrations).
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID

            uuid_type: Any = PG_UUID(as_uuid=True)
        else:
            # Portable UUID-as-string columns for SQLite tests / local demos.
            uuid_type = String(36)

        def _bind_uuid(value: UUID | None) -> Any:
            """Convert UUID to DB-compatible representation."""

            if value is None:
                return None
            return value if self._use_native_uuid else str(value)

        self._bind_uuid = _bind_uuid

        # Table definitions (mirror the Alembic migration path).
        metadata = MetaData()
        self._metadata = metadata

        self._issues = Table(
            "issues",
            metadata,
            Column("issue_id", uuid_type, primary_key=True),
            Column("created_at", DateTime, nullable=False),
            Column("status", String(32), nullable=False),
            Column("source", String(32), nullable=False),
            Column("domain", String(32), nullable=False),
            Column("subject_id", String(128), nullable=False),
            Column("fields", JSON, nullable=False),
            Column("description", Text, nullable=False),
            Column("evidence_payload", JSON, nullable=False),
        )

        self._runs = Table(
            "agent_runs",
            metadata,
            Column("run_id", uuid_type, primary_key=True),
            Column("issue_id", uuid_type, ForeignKey("issues.issue_id"), nullable=False),
            Column("created_at", DateTime, nullable=False),
            Column("rules_version", String(32), nullable=False),
            Column("recommendation", JSON, nullable=False),
        )

        self._decisions = Table(
            "decisions",
            metadata,
            Column("decision_id", uuid_type, primary_key=True),
            Column("issue_id", uuid_type, ForeignKey("issues.issue_id"), nullable=False),
            Column("run_id", uuid_type, ForeignKey("agent_runs.run_id"), nullable=False),
            Column("decision_type", String(16), nullable=False),
            Column("final_action", String(32), nullable=False),
            Column("final_text", Text, nullable=False),
            Column("reviewer", String(128), nullable=False),
            Column("reason", Text, nullable=True),
            Column("timestamp", DateTime, nullable=False),
        )

        self._audit = Table(
            "audit_events",
            metadata,
            Column("event_id", uuid_type, primary_key=True),
            Column("created_at", DateTime, nullable=False),
            Column("event_type", String(64), nullable=False),
            Column("actor", String(128), nullable=False),
            Column("issue_id", uuid_type, ForeignKey("issues.issue_id"), nullable=True),
            Column("run_id", uuid_type, ForeignKey("agent_runs.run_id"), nullable=True),
            Column("correlation_id", uuid_type, nullable=True),
            Column("details", JSON, nullable=False),
        )

        # For easy local demos/tests, optionally create tables automatically.
        # In production you would usually run Alembic migrations instead.
        if auto_create_schema:
            metadata.create_all(self._engine)

    def reset(self) -> None:
        """Delete all rows (useful for tests)."""

        with self._engine.begin() as conn:
            conn.execute(self._delete(self._audit))
            conn.execute(self._delete(self._decisions))
            conn.execute(self._delete(self._runs))
            conn.execute(self._delete(self._issues))

    def create_issue(self, issue_create: IssueCreate) -> Issue:
        issue = Issue(**issue_create.model_dump())

        with self._engine.begin() as conn:
            conn.execute(
                self._issues.insert().values(
                    issue_id=self._bind_uuid(issue.issue_id),
                    created_at=issue.created_at,
                    status=issue.status.value,
                    source=issue.source.value,
                    domain=issue.domain.value,
                    subject_id=issue.subject_id,
                    fields=issue.fields,
                    description=issue.description,
                    evidence_payload=issue.evidence_payload,
                )
            )

        self.add_audit_event(
            event_type=AuditEventType.ISSUE_CREATED,
            actor="SYSTEM",
            issue_id=issue.issue_id,
            details={
                "source": issue.source.value,
                "domain": issue.domain.value,
                "subject_id": issue.subject_id,
            },
        )

        return issue

    def list_issues(self) -> list[Issue]:
        with self._engine.begin() as conn:
            rows = conn.execute(self._select(self._issues)).mappings().all()
        return [Issue(**dict(r)) for r in rows]

    def get_issue(self, issue_id: UUID) -> Issue | None:
        with self._engine.begin() as conn:
            row = (
                conn.execute(
                    self._select(self._issues).where(
                        self._issues.c.issue_id == self._bind_uuid(issue_id)
                    )
                )
                .mappings()
                .first()
            )
        return Issue(**dict(row)) if row else None

    def update_issue_status(self, issue_id: UUID, status: IssueStatus) -> Issue | None:
        with self._engine.begin() as conn:
            conn.execute(
                self._update(self._issues)
                .where(self._issues.c.issue_id == self._bind_uuid(issue_id))
                .values(status=status.value)
            )

        self.add_audit_event(
            event_type=AuditEventType.ISSUE_UPDATED,
            actor="SYSTEM",
            issue_id=issue_id,
            details={"status": status.value},
        )

        return self.get_issue(issue_id)

    def append_run(self, issue_id: UUID, run: AgentRun) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                self._runs.insert().values(
                    run_id=self._bind_uuid(run.run_id),
                    issue_id=self._bind_uuid(issue_id),
                    created_at=run.created_at,
                    rules_version=run.rules_version,
                    recommendation=run.recommendation.model_dump(mode="json"),
                )
            )

    def list_runs(self, issue_id: UUID) -> list[AgentRun]:
        with self._engine.begin() as conn:
            rows = (
                conn.execute(
                    self._select(self._runs)
                    .where(self._runs.c.issue_id == self._bind_uuid(issue_id))
                    .order_by(self._runs.c.created_at)
                )
                .mappings()
                .all()
            )
        return [AgentRun(**dict(r)) for r in rows]

    def list_run_summaries(self, issue_id: UUID) -> list[AgentRunSummary]:
        return [AgentRunSummary.from_run(r) for r in self.list_runs(issue_id)]

    def runs_by_issue(self) -> dict[UUID, list[AgentRun]]:
        runs_by: dict[UUID, list[AgentRun]] = {}
        with self._engine.begin() as conn:
            rows = conn.execute(self._select(self._runs)).mappings().all()
        for r in rows:
            run = AgentRun(**dict(r))
            runs_by.setdefault(run.issue_id, []).append(run)
        return runs_by

    def append_decision(self, issue_id: UUID, decision_create: DecisionCreate) -> Decision:
        # Ensure the run exists for this issue (auditability).
        with self._engine.begin() as conn:
            found = (
                conn.execute(
                    self._select(self._runs.c.run_id)
                    .where(self._runs.c.issue_id == self._bind_uuid(issue_id))
                    .where(self._runs.c.run_id == self._bind_uuid(decision_create.run_id))
                )
                .first()
            )
        if found is None:
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

        with self._engine.begin() as conn:
            conn.execute(
                self._decisions.insert().values(
                    decision_id=self._bind_uuid(decision.decision_id),
                    issue_id=self._bind_uuid(issue_id),
                    run_id=self._bind_uuid(decision.run_id),
                    decision_type=decision.decision_type.value,
                    final_action=decision.final_action.value,
                    final_text=decision.final_text,
                    reviewer=decision.reviewer,
                    reason=decision.reason,
                    timestamp=decision.timestamp,
                )
            )

        self.add_audit_event(
            event_type=AuditEventType.DECISION_RECORDED,
            actor=decision.reviewer,
            issue_id=issue_id,
            run_id=decision.run_id,
            details={
                "decision_type": decision.decision_type.value,
                "final_action": decision.final_action.value,
                "decision_id": str(decision.decision_id),
            },
        )

        return decision

    def list_decisions(self, issue_id: UUID) -> list[Decision]:
        with self._engine.begin() as conn:
            rows = (
                conn.execute(
                    self._select(self._decisions)
                    .where(self._decisions.c.issue_id == self._bind_uuid(issue_id))
                    .order_by(self._decisions.c.timestamp.desc())
                )
                .mappings()
                .all()
            )
        return [Decision(**dict(r)) for r in rows]

    def add_audit_event(
        self,
        *,
        event_type: AuditEventType,
        actor: str,
        issue_id: UUID | None = None,
        run_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        correlation_id = get_correlation_id()

        event = AuditEvent(
            event_type=event_type,
            created_at=datetime.utcnow(),
            actor=actor,
            issue_id=issue_id,
            run_id=run_id,
            correlation_id=correlation_id,
            details=details or {},
        )

        with self._engine.begin() as conn:
            conn.execute(
                self._audit.insert().values(
                    event_id=self._bind_uuid(event.event_id),
                    created_at=event.created_at,
                    event_type=event.event_type.value,
                    actor=event.actor,
                    issue_id=self._bind_uuid(event.issue_id),
                    run_id=self._bind_uuid(event.run_id),
                    correlation_id=self._bind_uuid(event.correlation_id),
                    details=event.details,
                )
            )

        return event

    def query_audit(
        self, *, issue_id: UUID | None = None, run_id: UUID | None = None
    ) -> list[AuditEvent]:
        stmt = self._select(self._audit)
        if issue_id is not None:
            stmt = stmt.where(self._audit.c.issue_id == self._bind_uuid(issue_id))
        if run_id is not None:
            stmt = stmt.where(self._audit.c.run_id == self._bind_uuid(run_id))

        with self._engine.begin() as conn:
            rows = conn.execute(stmt.order_by(self._audit.c.created_at)).mappings().all()
        return [AuditEvent(**dict(r)) for r in rows]


# The active backend.
#
# Default: in-memory (fast, no setup).
# To enable Postgres, set:
#   STORAGE_BACKEND=postgres
#   DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db
#
# AUTO_CREATE_SCHEMA=1 will create tables automatically (helpful for demos/tests).
_backend_name = os.getenv("STORAGE_BACKEND", "inmemory").strip().lower()
_auto_create = os.getenv("AUTO_CREATE_SCHEMA", "1").strip() in {"1", "true", "yes"}

if _backend_name == "postgres":
    _database_url = os.getenv("DATABASE_URL")
    if not _database_url:
        raise RuntimeError("STORAGE_BACKEND=postgres requires DATABASE_URL to be set")
    BACKEND = PostgresStorageBackend(_database_url, auto_create_schema=_auto_create)
else:
    BACKEND = InMemoryStorageBackend()


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


def list_runs(issue_id: UUID) -> list[AgentRun]:
    """Return the full run objects for an issue (oldest -> newest)."""

    return RUNS.get(issue_id, [])


def runs_by_issue() -> dict[UUID, list[AgentRun]]:
    """
    Return the underlying runs dict.

    We return the actual dict for convenience in the MVP (used by eval exports).
    In a database-backed implementation, this would likely become a query function.
    """

    return BACKEND.runs_by_issue()


def get_latest_run(issue_id: UUID) -> AgentRun | None:
    """
    Return the most recent run for an issue, or None if none exist.

    Why this uses BACKEND:
    - When we switch to Postgres, runs are no longer stored in a Python dict.
    - Using BACKEND keeps this helper working across storage implementations.
    """

    runs = BACKEND.list_runs(issue_id)
    return runs[-1] if runs else None


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

    # Pull correlation_id from the current request context (if available).
    # This lets us connect audit events back to the API request that created them.
    correlation_id = get_correlation_id()

    event = AuditEvent(
        event_type=event_type,
        created_at=datetime.utcnow(),
        actor=actor,
        issue_id=issue_id,
        run_id=run_id,
        correlation_id=correlation_id,
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
        details={
            "source": issue.source.value,
            "domain": issue.domain.value,
            "subject_id": issue.subject_id,
        },
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
        if decision.final_action == "IGNORE":
            issue.status = IssueStatus.CLOSED
        else:
            issue.status = IssueStatus.TRIAGED
        ISSUES[issue_id] = issue

    return decision


def list_decisions(issue_id: UUID) -> list[Decision]:
    """
    List decisions for an issue (most recent first).
    Returns an empty list if none exist.
    """

    return DECISIONS.get(issue_id, [])
