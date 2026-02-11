"""
Analyze routes.

These endpoints run deterministic analysis against an issue, optionally enhanced with LLM + RAG.
Each analysis call creates a new `AgentRun` record so you get:
- history (multiple runs over time)
- auditability (what rule fired, what version was used, LLM model if enabled)
"""

import os
from uuid import UUID

from fastapi import APIRouter, HTTPException

from agent.analyze.deterministic import analyze_issue
from agent.analyze.llm import enhance_with_llm
from agent.retrieval.rag import search_documents_semantic
from agent.schemas.analyze import AnalyzeRequest
from agent.schemas.audit import AuditEventType
from agent.schemas.run import AgentRun, AgentRunSummary
from apps.api import storage

router = APIRouter(prefix="/issues", tags=["analyze"])


def _build_doc_query(
    *, domain: str, rule_fired: str | None, issue_description: str | None = None
) -> str:
    """
    Build a document search query for RAG retrieval.

    Why:
    - Enterprise recommendations should be grounded in guidance.
    - For semantic RAG, richer queries with context work better than short keywords.
    """

    base = domain.strip()
    if not rule_fired:
        # For cases without a specific rule, include domain and description
        if issue_description:
            return f"{base} {issue_description}".strip()
        return base

    rule = rule_fired.upper()
    if rule == "AE_DATE_INCONSISTENCY":
        return f"{base} adverse event date start end inconsistency"
    if rule == "MISSING_CRITICAL_FIELD":
        return f"{base} missing required field data quality"
    if rule == "OUT_OF_RANGE_SIGNAL":
        return f"{base} out of range limits validation"
    if rule == "DUPLICATE_RECORD_SUSPECTED":
        return f"{base} duplicate record de-duplication data quality"
    if rule == "FALLBACK":
        # For FALLBACK cases, use domain + description to get better semantic matches
        if issue_description:
            return f"{base} {issue_description}".strip()
        return f"{base} data quality issue"
    return base


@router.post("/{issue_id}/analyze", response_model=AgentRun)
def analyze(issue_id: UUID, req: AnalyzeRequest | None = None) -> AgentRun:
    """
    Run deterministic analysis for a single issue.

    What this endpoint does:
    - Loads the Issue (404 if missing)
    - Runs `analyze_issue(issue)` (deterministic rules)
    - Optionally enhances with RAG (document retrieval) and LLM reasoning
    - Creates an AgentRun record (rules_version is stored for auditability)
    - Stores it under RUNS[issue_id]
    - Writes an audit event: ANALYZE_RUN_CREATED

    Note: Issue status remains OPEN after analysis. Status changes to TRIAGED only when
    a decision is recorded via POST /issues/{issue_id}/decisions.
    """

    issue = storage.BACKEND.get_issue(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    req = req or AnalyzeRequest()

    # Step 1: Run deterministic analysis (always runs, source of truth)
    recommendation = analyze_issue(issue)

    # Step 2: RAG - retrieve relevant guidance documents (always runs)
    # RAG adds citations to recommendations, making them evidence-grounded
    rule_fired = recommendation.tool_results.get("rule_fired")
    query = _build_doc_query(
        domain=issue.domain.value,
        rule_fired=str(rule_fired) if rule_fired else None,
        issue_description=issue.description,
    )

    # Use semantic RAG if requested (request-level override, then issue_type, then env var)
    use_semantic_rag = (
        req.use_semantic_rag
        if req.use_semantic_rag is not None
        else issue.issue_type.value == "llm_required"
        or os.getenv("RAG_SEMANTIC", "").strip().lower() in ("1", "true", "yes")
    )

    import logging

    logger = logging.getLogger("agentic_triage_copilot.api.routes.analyze")

    if use_semantic_rag:
        all_docs = storage.BACKEND.list_documents()
        logger.info(f"Semantic RAG: searching {len(all_docs)} documents with query: '{query}'")
        hits = search_documents_semantic(query=query, documents=all_docs, limit=3)
        recommendation.tool_results["rag_method"] = "semantic"

        # Filter out low-relevance matches (similarity < 0.40 = 40%)
        # Documents below 40% similarity are not relevant enough to be useful citations
        high_relevance_hits = [h for h in hits if h.score >= 0.40]
        if high_relevance_hits:
            hits = high_relevance_hits
            logger.info(
                f"Semantic RAG: {len(hits)} high-relevance documents found (similarity >= 40%)"
            )
        elif hits:
            # All hits have low similarity - treat as no relevant guidance found
            logger.info(
                f"Semantic RAG: Found {len(hits)} documents but all have low similarity (<40%) - treating as no relevant guidance"
            )
            hits = []
        else:
            logger.warning(
                f"Semantic RAG found no citations for query: '{query}' (domain: {issue.domain.value}, rule: {rule_fired})"
            )
    else:
        hits = storage.BACKEND.search_documents(query=query, limit=3)
        recommendation.tool_results["rag_method"] = "keyword"

    # Always add citations (even if empty list - indicates no matching documents)
    recommendation.citations = [str(h.doc_id) for h in hits]
    recommendation.tool_results["citation_hits"] = [
        {"doc_id": str(h.doc_id), "title": h.title, "source": h.source, "score": h.score}
        for h in hits
    ]
    # Note: Citations may be empty if no documents match the query

    # Step 3: LLM enhancement
    # Priority: request-level flag > issue_type > env var
    # Note: For deterministic issues, LLM enhancement only happens if explicitly requested (req.use_llm=True) or LLM_ENABLED=1
    # For LLM-required issues, LLM is automatically used unless explicitly disabled (req.use_llm=False)
    use_llm = (
        req.use_llm
        if req.use_llm is not None
        else issue.issue_type.value == "llm_required"
        or os.getenv("LLM_ENABLED", "").strip().lower() in ("1", "true", "yes")
    )
    if use_llm:
        llm_model = req.llm_model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        import logging

        logger = logging.getLogger("agentic_triage_copilot.api")
        logger.info(
            f"LLM enhancement requested for issue {issue_id}, use_llm={req.use_llm}, issue_type={issue.issue_type.value}, force_enable={req.use_llm is True or issue.issue_type.value == 'llm_required'}"
        )

        # Check if OpenAI is available before attempting
        try:
            from openai import OpenAI  # noqa: F401

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("LLM requested but OPENAI_API_KEY not found in environment variables")
                recommendation.tool_results["llm_requested"] = True
                recommendation.tool_results["llm_failed"] = True
                recommendation.tool_results["llm_failure_reason"] = (
                    "OPENAI_API_KEY not set in .env file"
                )
            else:
                recommendation = enhance_with_llm(
                    issue,
                    recommendation,
                    model_version=llm_model,
                    force_enable=req.use_llm is True or issue.issue_type.value == "llm_required",
                )
                # Verify LLM actually enhanced (check if llm_enhanced flag is set)
                if not recommendation.tool_results.get("llm_enhanced", False):
                    # LLM was requested but didn't enhance (likely API key missing or error)
                    # Keep original recommendation but note in tool_results
                    logger.warning(
                        f"LLM was requested for issue {issue_id} but enhancement failed. Check server logs for details."
                    )
                    recommendation.tool_results["llm_requested"] = True
                    recommendation.tool_results["llm_failed"] = True
                    if "llm_failure_reason" not in recommendation.tool_results:
                        recommendation.tool_results["llm_failure_reason"] = (
                            "Check server logs for error details"
                        )
                else:
                    logger.info(f"LLM enhancement successful for issue {issue_id}")
        except ImportError:
            logger.error(
                "LLM requested but 'openai' package is not installed. Run: pip install openai"
            )
            recommendation.tool_results["llm_requested"] = True
            recommendation.tool_results["llm_failed"] = True
            recommendation.tool_results["llm_failure_reason"] = (
                "OpenAI package not installed - restart server after: pip install openai"
            )
        # Note: LLM enhancement modifies rationale, draft_message, and confidence
        # Action and severity remain from deterministic analysis (source of truth)

    # Replay metadata: link this run to a prior run_id (if provided).
    if req.replay_of_run_id is not None:
        recommendation.tool_results["replay_of_run_id"] = str(req.replay_of_run_id)

    run = AgentRun(
        issue_id=issue_id, rules_version=req.rules_version, recommendation=recommendation
    )

    storage.BACKEND.append_run(issue_id, run)
    # Note: Status is NOT updated here. Status changes to TRIAGED only when a decision is recorded.

    storage.BACKEND.add_audit_event(
        event_type=AuditEventType.ANALYZE_RUN_CREATED,
        actor="SYSTEM",
        issue_id=issue_id,
        run_id=run.run_id,
        details={
            "rules_version": run.rules_version,
            "rule_fired": recommendation.tool_results.get("rule_fired"),
            "replay_of_run_id": str(req.replay_of_run_id) if req.replay_of_run_id else None,
            "llm_enhanced": recommendation.tool_results.get("llm_enhanced", False),
            "llm_model": recommendation.tool_results.get("llm_model"),
            "rag_method": recommendation.tool_results.get("rag_method", "keyword"),
        },
    )

    return run


@router.get("/{issue_id}/runs", response_model=list[AgentRunSummary])
def list_runs(issue_id: UUID) -> list[AgentRunSummary]:
    """
    List run history for an issue (summary view).

    Returns 404 if the issue does not exist. This keeps behavior consistent with other
    issue-scoped endpoints.
    """

    issue = storage.BACKEND.get_issue(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    return storage.BACKEND.list_run_summaries(issue_id)


@router.get("/{issue_id}/runs/{run_id}", response_model=AgentRun)
def get_run(issue_id: UUID, run_id: UUID) -> AgentRun:
    """
    Get a specific run by ID (full details including recommendation).

    Returns 404 if the issue or run does not exist.
    """

    issue = storage.BACKEND.get_issue(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    run = storage.BACKEND.get_run(issue_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found for this issue")

    return run
