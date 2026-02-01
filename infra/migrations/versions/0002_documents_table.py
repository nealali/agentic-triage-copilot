"""
Add documents table for RAG-lite ingestion/search.

This supports grounding recommendations in enterprise guidance by storing ingested documents
and enabling deterministic keyword retrieval (later extend to chunking + embeddings).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_documents_table"
down_revision = "0001_initial_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("doc_id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("documents")
