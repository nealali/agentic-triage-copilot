"""
Analyze request schemas (Pydantic v2).

Why this exists
---------------
The analyze endpoint started as a simple "run analysis" call.
As the system matures, we want:
- explicit versioning (which rules/prompt/version produced this run)
- replay support (run again and link to a prior run_id)

This file defines the request contract that enables those features without changing the
stored `AgentRun` model shape.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """
    Optional request body for analysis runs.

    Notes:
    - `rules_version` is stored on the AgentRun for auditability.
    - `replay_of_run_id` lets you explicitly link this run to a prior run (re-run / replay).
    - `use_llm` and `use_semantic_rag` allow per-request control (overrides env vars).
    - `llm_model` overrides the default LLM model (if LLM is enabled).
    """

    rules_version: str = Field(
        default="v0.1",
        description="Version label for the deterministic rules used to produce this run.",
    )
    replay_of_run_id: UUID | None = Field(
        default=None,
        description="Optional prior run_id that this analysis run is replaying.",
    )
    use_llm: bool | None = Field(
        default=None,
        description="Enable LLM enhancement for this run. If None, uses LLM_ENABLED env var.",
    )
    use_semantic_rag: bool | None = Field(
        default=None,
        description="Use semantic RAG (embeddings) instead of keyword search. If None, uses RAG_SEMANTIC env var.",
    )
    llm_model: str | None = Field(
        default=None,
        description="Optional LLM model override (e.g., 'gpt-4o-mini', 'gpt-4'). Uses LLM_MODEL env var if not provided.",
    )
