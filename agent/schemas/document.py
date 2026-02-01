"""
Document schemas (Pydantic v2).

Why documents exist in this project
----------------------------------
In pharma/biotech, recommendations are rarely allowed to be "just an opinion".
They should be grounded in:
- a Data Review Plan
- edit check specifications
- SDTM/ADaM standards
- query writing guidance / SOPs

This module defines a simple, production-friendly contract for those documents.

Important note (MVP scope)
--------------------------
This repo implements a **RAG-lite** approach:
- you can ingest documents (title + content)
- you can search them with a simple keyword query
- the agent can attach **citation IDs** (doc_ids) to recommendations

Later, you can evolve this into full semantic search (embeddings + chunking) without
changing your API contracts too much.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    """
    Input model for ingesting a document into the system.

    A "document" can be:
    - a SOP
    - a guidance memo
    - a data review plan excerpt
    - an edit check spec

    We keep it deliberately small and generic for the MVP.
    """

    title: str = Field(..., description="Human-friendly title (e.g., 'AE Date Checks Guidance').")
    source: str = Field(
        ...,
        description="Where this doc came from (e.g., 'DRP', 'SOP', 'spec', 'wiki').",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Optional tags used for filtering/search (e.g., ['AE', 'SDTM']).",
    )
    content: str = Field(..., description="Full document text (small/medium sized for MVP).")


class Document(BaseModel):
    """Stored/returned document model (adds doc_id + created_at)."""

    doc_id: UUID = Field(default_factory=uuid4, description="Unique document identifier.")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="UTC timestamp when the document was ingested."
    )
    title: str = Field(..., description="Human-friendly title.")
    source: str = Field(..., description="Source/category of the document.")
    tags: list[str] = Field(default_factory=list, description="Optional tags for search/filtering.")
    content: str = Field(..., description="Full document text.")


class DocumentHit(BaseModel):
    """
    Search result item.

    We return a small "hit" object so UIs can show results without loading full content.
    """

    doc_id: UUID = Field(..., description="Document ID for the hit.")
    title: str = Field(..., description="Document title.")
    source: str = Field(..., description="Document source/category.")
    score: float = Field(..., description="Simple relevance score (higher is better).")
    snippet: str = Field(..., description="Short excerpt that matched the query.")
