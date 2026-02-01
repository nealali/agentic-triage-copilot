"""
Document routes (RAG-lite ingestion + search).

Why this exists:
- In enterprise environments, recommendations should be grounded in guidance.
- This router lets you ingest guidance documents and search them deterministically.

Scope note:
- This is NOT a full embedding-based RAG system yet.
- It's a minimal, explainable baseline that supports "citations" by document ID.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from agent.schemas.audit import AuditEventType
from agent.schemas.document import Document, DocumentCreate, DocumentHit
from apps.api import storage
from apps.api.auth import require_roles

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=Document)
def ingest_document(
    document_create: DocumentCreate,
    _auth=Depends(require_roles({"writer", "admin"})),
) -> Document:
    """Ingest a guidance document into the system."""

    doc = storage.BACKEND.ingest_document(document_create)

    # Record an audit event with the authenticated actor (when auth is enabled).
    storage.BACKEND.add_audit_event(
        event_type=AuditEventType.DOCUMENT_INGESTED,
        actor=_auth.user,
        details={"doc_id": str(doc.doc_id), "title": doc.title, "source": doc.source},
    )

    return doc


@router.get("/search", response_model=list[DocumentHit])
def search_documents(q: str = Query(..., min_length=1), limit: int = 10) -> list[DocumentHit]:
    """Keyword search over ingested documents."""

    return storage.BACKEND.search_documents(query=q, limit=limit)


@router.get("/{doc_id}", response_model=Document)
def get_document(doc_id: UUID) -> Document:
    """Fetch a single document by ID."""

    doc = storage.BACKEND.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc
