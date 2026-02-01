"""
Initial database tables (Postgres migration path).

This migration is not required for the in-memory MVP to run.
It exists to demonstrate a clear path to persistence and auditability.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Issues table: canonical unit of work
    op.create_table(
        "issues",
        sa.Column("issue_id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence_payload", sa.JSON(), nullable=False),
    )

    # Agent runs: each analyze call produces one run record
    op.create_table(
        "agent_runs",
        sa.Column("run_id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("issue_id", sa.UUID(), sa.ForeignKey("issues.issue_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("rules_version", sa.String(length=32), nullable=False),
        # Store the recommendation as JSON for flexibility (schema can evolve).
        sa.Column("recommendation", sa.JSON(), nullable=False),
    )

    # Decisions: human-in-the-loop approvals/overrides
    op.create_table(
        "decisions",
        sa.Column("decision_id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("issue_id", sa.UUID(), sa.ForeignKey("issues.issue_id"), nullable=False),
        sa.Column("run_id", sa.UUID(), sa.ForeignKey("agent_runs.run_id"), nullable=False),
        sa.Column("decision_type", sa.String(length=16), nullable=False),
        sa.Column("final_action", sa.String(length=32), nullable=False),
        sa.Column("final_text", sa.Text(), nullable=False),
        sa.Column("reviewer", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
    )

    # Audit events: append-only event log
    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("issue_id", sa.UUID(), sa.ForeignKey("issues.issue_id"), nullable=True),
        sa.Column("run_id", sa.UUID(), sa.ForeignKey("agent_runs.run_id"), nullable=True),
        sa.Column("correlation_id", sa.UUID(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("decisions")
    op.drop_table("agent_runs")
    op.drop_table("issues")
