"""
Retrieval-Augmented Generation (RAG) module.

This module provides semantic search over ingested documents using embeddings.
"""

from agent.retrieval.rag import search_documents_semantic

__all__ = ["search_documents_semantic"]
