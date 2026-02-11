"""
Semantic RAG: embedding-based document retrieval.

This module provides semantic search over documents using sentence transformers.
It's an upgrade from the keyword-based "RAG-lite" approach.

Why embeddings?
---------------
- Keyword search misses semantically similar content (e.g., "adverse event" vs "AE")
- Embeddings capture meaning, not just exact word matches
- Better citation quality for recommendations

Design:
-------
- Uses sentence-transformers for local embeddings (no API calls needed)
- Computes embeddings on-the-fly (can be cached later)
- Returns top-k most similar documents with similarity scores
"""

from __future__ import annotations

import os

from agent.schemas.document import Document, DocumentHit


def _get_embedding_model():
    """
    Lazy-load the embedding model (expensive to import).

    Uses a lightweight model suitable for clinical/biotech text.
    """
    try:
        from sentence_transformers import SentenceTransformer

        # Use a general-purpose model that works well for technical/medical text
        # This is cached after first load
        model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        return SentenceTransformer(model_name)
    except ImportError:
        return None


def search_documents_semantic(
    query: str, documents: list[Document], limit: int = 3
) -> list[DocumentHit]:
    """
    Semantic search over documents using embeddings.

    Args:
        query: Search query string
        documents: List of documents to search
        limit: Maximum number of results

    Returns:
        List of DocumentHit objects sorted by similarity (highest first)
    """
    if not query or not documents:
        return []

    model = _get_embedding_model()
    if model is None:
        # Fallback to keyword search if embeddings not available
        return _keyword_fallback(query, documents, limit)

    try:
        # Encode query and documents
        query_embedding = model.encode(query, convert_to_numpy=True)
        doc_texts = [
            f"{doc.title}\n{doc.source}\n{' '.join(doc.tags)}\n{doc.content}" for doc in documents
        ]
        doc_embeddings = model.encode(doc_texts, convert_to_numpy=True)

        # Compute cosine similarity
        import numpy as np

        # Normalize embeddings for cosine similarity
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        doc_norms = doc_embeddings / (np.linalg.norm(doc_embeddings, axis=1, keepdims=True) + 1e-8)

        # Cosine similarity = dot product of normalized vectors
        similarities = np.dot(doc_norms, query_norm)

        # Create hits with scores
        # For semantic search, include documents with reasonable similarity
        # Cosine similarity with normalized embeddings typically ranges from 0 to 1
        # Higher threshold (0.35) ensures only truly relevant documents are included
        # Documents below 0.35 are likely not relevant enough to be useful citations
        hits: list[DocumentHit] = []
        for i, doc in enumerate(documents):
            score = float(similarities[i])
            # Include documents with similarity >= 0.35 to ensure relevance
            # This threshold filters out low-relevance matches that aren't useful
            if score >= 0.35:
                snippet = _extract_snippet(doc.content, query)
                hits.append(
                    DocumentHit(
                        doc_id=doc.doc_id,
                        title=doc.title,
                        source=doc.source,
                        score=score,
                        snippet=snippet,
                    )
                )

        # Sort by score descending
        hits.sort(key=lambda h: h.score, reverse=True)

        # Log for debugging (can be removed in production)
        import logging

        logger = logging.getLogger("agentic_triage_copilot.rag")
        if hits:
            logger.debug(
                f"Semantic search found {len(hits)} documents for query '{query[:50]}...' (top score: {hits[0].score:.3f})"
            )
        else:
            logger.debug(
                f"Semantic search found no documents above threshold (0.35) for query '{query[:50]}...' (total docs: {len(documents)})"
            )
            if documents:
                # Log top similarity scores for debugging
                top_scores = sorted(
                    [float(similarities[i]) for i in range(len(documents))], reverse=True
                )[:3]
                logger.debug(f"Top similarity scores: {[f'{s:.3f}' for s in top_scores]}")
                if top_scores and top_scores[0] < 0.35:
                    logger.info(
                        f"Highest similarity score ({top_scores[0]:.3f}) below threshold - no relevant documents found"
                    )

        return hits[:limit]

    except Exception:
        # Fallback to keyword search on any error
        return _keyword_fallback(query, documents, limit)


def _keyword_fallback(query: str, documents: list[Document], limit: int) -> list[DocumentHit]:
    """Fallback keyword search if embeddings fail."""
    terms = [t.lower() for t in query.split() if t]

    def _score(doc: Document) -> float:
        haystack = f"{doc.title}\n{doc.source}\n{' '.join(doc.tags)}\n{doc.content}".lower()
        return float(sum(1 for t in terms if t in haystack))

    hits: list[DocumentHit] = []
    for doc in documents:
        score = _score(doc)
        if score > 0:
            snippet = _extract_snippet(doc.content, query)
            hits.append(
                DocumentHit(
                    doc_id=doc.doc_id,
                    title=doc.title,
                    source=doc.source,
                    score=score,
                    snippet=snippet,
                )
            )

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]


def _extract_snippet(content: str, query: str, max_length: int = 200) -> str:
    """Extract a snippet around the first query term match."""
    content_lower = content.lower()
    query_lower = query.lower()
    terms = [t for t in query_lower.split() if len(t) > 2]

    if not terms:
        return content[:max_length].replace("\n", " ").strip()

    # Find first occurrence of any term
    idx = -1
    for term in terms:
        pos = content_lower.find(term)
        if pos >= 0:
            idx = pos
            break

    if idx < 0:
        return content[:max_length].replace("\n", " ").strip()

    start = max(0, idx - 80)
    end = min(len(content), idx + max_length - 80)
    snippet = content[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."
    return snippet
