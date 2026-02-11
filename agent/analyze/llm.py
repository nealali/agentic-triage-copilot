"""
LLM-powered analysis layer.

This module enhances deterministic recommendations with LLM reasoning.
It's designed to be optional (can be disabled via env vars) and always builds
on top of the deterministic layer for auditability.

Why LLM?
--------
- Handles edge cases and ambiguous descriptions
- Generates more nuanced rationales
- Better draft message generation
- Context-aware reasoning

Design:
-------
- Always runs deterministic analysis first (source of truth)
- LLM enhances/refines the recommendation if enabled
- Stores model version and prompt version for auditability
- Falls back gracefully if LLM is unavailable
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from agent.schemas.issue import Issue
from agent.schemas.recommendation import AgentRecommendation

logger = logging.getLogger("agentic_triage_copilot.llm")


def _is_llm_enabled() -> bool:
    """Check if LLM analysis is enabled via environment variable."""
    return os.getenv("LLM_ENABLED", "").strip().lower() in ("1", "true", "yes")


def _get_openai_client(force: bool = False):
    """
    Lazy-load OpenAI client.

    Args:
        force: If True, attempt to load even if LLM_ENABLED env var is off
    """
    if not force and not _is_llm_enabled():
        return None

    try:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None

        return OpenAI(api_key=api_key)
    except ImportError:
        return None


def enhance_with_llm(
    issue: Issue,
    deterministic_rec: AgentRecommendation,
    model_version: str = "gpt-4o-mini",
    force_enable: bool = False,
) -> AgentRecommendation:
    """
    Enhance a deterministic recommendation with LLM reasoning.

    Args:
        issue: The issue being analyzed
        deterministic_rec: The recommendation from deterministic rules
        model_version: OpenAI model to use (default: gpt-4o-mini for cost efficiency)
        force_enable: If True, enable LLM even if LLM_ENABLED env var is off (for request-level override)

    Returns:
        Enhanced recommendation (or original if LLM unavailable)
    """
    if not force_enable and not _is_llm_enabled():
        return deterministic_rec

    client = _get_openai_client(force=force_enable)
    if client is None:
        # If force_enable but no API key, still return original (graceful degradation)
        if force_enable:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning(
                    "LLM requested (force_enable=True) but OPENAI_API_KEY not found in environment"
                )
            else:
                # Check if OpenAI library is installed
                try:
                    from openai import OpenAI

                    logger.warning(
                        f"LLM requested (force_enable=True) but OpenAI client creation failed. API key present: {bool(api_key)}, length: {len(api_key) if api_key else 0}. OpenAI library available: True"
                    )
                    # Try to create client directly to see the actual error
                    try:
                        test_client = OpenAI(api_key=api_key)
                        logger.warning("Direct client creation succeeded - this is unexpected")
                    except Exception as e:
                        logger.error(f"Direct client creation failed: {type(e).__name__}: {e}")
                except ImportError:
                    logger.error(
                        "LLM requested but 'openai' package is not installed. Run: pip install openai"
                    )
        return deterministic_rec

    try:
        # Build context for the LLM
        prompt = _build_analysis_prompt(issue, deterministic_rec)

        logger.info(f"Calling OpenAI API with model {model_version} for issue {issue.issue_id}")
        logger.debug(f"Prompt length: {len(prompt)} characters")

        response = client.chat.completions.create(
            model=model_version,
            messages=[
                {
                    "role": "system",
                    "content": "You are a clinical data quality analyst. Provide structured, evidence-based recommendations.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,  # Lower temperature for more deterministic outputs
            response_format={"type": "json_object"},  # Force JSON output
        )

        llm_output = json.loads(response.choices[0].message.content)
        logger.info(
            f"LLM API call successful, received response with keys: {list(llm_output.keys())}"
        )

        # Validate LLM output has at least one enhancement field
        if not any(
            key in llm_output
            for key in [
                "rationale_enhanced",
                "confidence_adjusted",
                "draft_message_enhanced",
                "missing_info_enhanced",
            ]
        ):
            # LLM didn't provide enhancements, return original
            logger.warning(
                "LLM response missing enhancement fields, returning original recommendation"
            )
            return deterministic_rec

        # Merge LLM insights with deterministic recommendation
        enhanced = _merge_recommendations(deterministic_rec, llm_output, model_version)
        logger.info("LLM enhancement successful - rationale and/or draft_message enhanced")
        return enhanced

    except Exception as e:
        # On any error, return the deterministic recommendation
        import traceback

        logger.error(f"LLM enhancement failed: {type(e).__name__}: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        # Don't set llm_enhanced flag - let the caller detect failure
        return deterministic_rec


def _build_analysis_prompt(issue: Issue, deterministic_rec: AgentRecommendation) -> str:
    """Build the prompt for LLM analysis."""
    rule_fired = deterministic_rec.tool_results.get("rule_fired", "FALLBACK")
    evidence_summary = json.dumps(
        deterministic_rec.tool_results.get("evidence_summary", {}), indent=2
    )

    # Include full evidence payload (values, reference, notes, etc.) for context
    evidence_details = ""
    if issue.evidence_payload:
        # Extract key evidence fields that are useful for message generation
        evidence_fields = {}
        for key in ["value", "values", "reference", "notes", "variable", "start_date", "end_date"]:
            if key in issue.evidence_payload:
                val = issue.evidence_payload[key]
                if val is not None and val != "":
                    evidence_fields[key] = val

        # Include any other non-empty evidence fields
        for key, val in issue.evidence_payload.items():
            if key not in evidence_fields and val is not None and val != "":
                # Skip very large values that might bloat the prompt
                val_str = str(val)
                if len(val_str) <= 500:  # Reasonable limit
                    evidence_fields[key] = val

        if evidence_fields:
            evidence_details = "\n\nEvidence Details (from source data):\n"
            evidence_details += json.dumps(evidence_fields, indent=2, default=str)
            evidence_details += "\n\nUse these evidence values when generating the draft message. If 'value' or 'values' are present, include them in the message. If 'reference' or 'notes' are present, use them to provide context."

    # Include citation information if available
    citation_info = ""
    has_draft_message = deterministic_rec.draft_message and deterministic_rec.draft_message.strip()
    has_citations = bool(deterministic_rec.citations)

    if has_citations:
        citation_hits = deterministic_rec.tool_results.get("citation_hits", [])
        if citation_hits:
            citation_info = "\n\nRetrieved Guidance Documents (Citations):\n"
            low_relevance_count = 0
            for i, hit in enumerate(citation_hits[:3], 1):  # Show top 3 citations
                title = hit.get("title", "Unknown")
                source = hit.get("source", "Unknown")
                score = hit.get("score")
                score_str = f" (similarity: {score*100:.1f}%)" if score is not None else ""
                citation_info += f"{i}. {title} ({source}){score_str}\n"
                # Check if similarity is low (below 40%)
                if score is not None and score < 0.40:
                    low_relevance_count += 1

            # Warn if all citations have low similarity scores
            if low_relevance_count == len(citation_hits[:3]) and len(citation_hits) > 0:
                citation_info += "\n⚠️ WARNING: All retrieved documents have low similarity scores (<40%), indicating they may not be relevant to this specific issue. You should state that no relevant guidance was found."

            # Special instruction when deterministic draft_message is missing
            if not has_draft_message:
                citation_info += "\n⚠️ CRITICAL: The deterministic analysis did not generate a draft message. You MUST use ONLY the guidance documents above to generate the draft_message. DO NOT make up or invent information not found in these documents. Follow the query templates and guidance patterns EXACTLY as shown in these documents."
            else:
                citation_info += "\n⚠️ CRITICAL: You MUST base your recommendations and draft message ONLY on the guidance documents above. DO NOT invent, assume, or make up information that is not explicitly stated in these documents. If information is not in these documents, state that explicitly."
        else:
            citation_info = f"\n\nCitations: {len(deterministic_rec.citations)} document(s) retrieved (details not available)."
    else:
        # No citations found - explicitly state this
        citation_info = "\n\n⚠️ NO GUIDANCE DOCUMENTS FOUND: No relevant guidance documents (citations) were retrieved for this issue. You MUST explicitly state in your rationale and draft message that no relevant guidance information was found in the RAG documents. DO NOT make up guidance or recommendations that are not grounded in actual documentation."

    prompt = f"""You are analyzing clinical data quality issues in a data management system. These issues are detected during automated quality checks and need to be communicated to site investigators or internal data management teams.

System Context:
- This is a clinical trial data quality triage system
- Issues are automatically detected from clinical data exports (e.g., RAVE, EDC systems)
- Messages will be sent to site investigators (QUERY_SITE) or used as internal notes (DATA_FIX)
- These are technical query notes, NOT emails - they should be direct and concise

Issue Details:
- Domain: {issue.domain}
- Subject ID: {issue.subject_id}
- Fields: {', '.join(issue.fields) if issue.fields else 'N/A'}
- Description: {issue.description}{evidence_details}

Deterministic Analysis:
- Rule fired: {rule_fired}
- Current recommendation: {deterministic_rec.action.value}
- Current severity: {deterministic_rec.severity.value}
- Current confidence: {deterministic_rec.confidence}
- Current rationale: {deterministic_rec.rationale}
- Current draft message: {deterministic_rec.draft_message or 'N/A'}
- Evidence Summary: {evidence_summary}{citation_info}

CRITICAL RULES - YOU MUST FOLLOW THESE:
- **ONLY use information from the guidance documents (citations) provided above**
- **DO NOT invent, assume, or make up information not found in the guidance documents**
- **If no guidance documents are provided, explicitly state "No relevant guidance information found in RAG documents"**
- **If guidance documents don't contain relevant information for this specific issue, state that explicitly**
- **Base your recommendations and messages ONLY on what is actually documented in the retrieved guidance**

Your task:
1. Review the deterministic analysis above carefully
2. Check if guidance documents (citations) are provided:
   - If YES: Use ONLY information from these documents. Do not add information not found in them.
   - If NO: Explicitly state in your rationale that "No relevant guidance information found in RAG documents"
3. Consider if the recommendation needs refinement based on context:
   - If the deterministic analysis used FALLBACK rule (rule_fired: "FALLBACK"), you should provide a more specific recommendation if possible
   - If the issue clearly requires site query (missing data, inconsistencies), consider if action should be QUERY_SITE
   - If the issue is clearly a data error that can be fixed internally, consider if action should be DATA_FIX
   - If medical judgment is truly needed, MEDICAL_REVIEW is appropriate
4. Provide a JSON response with:
   - "rationale_enhanced": A more detailed, context-aware rationale (2-3 sentences) that explains WHY this specific action is recommended. Be specific about what needs to be done and why. CRITICAL: If guidance documents are provided, base your rationale ONLY on those documents. If no guidance documents are provided or they don't contain relevant information, explicitly state "No relevant guidance information found in RAG documents for this issue." DO NOT invent guidance or recommendations.
   - "confidence_adjusted": Adjusted confidence score (0.0-1.0) based on your analysis. If you have strong evidence for a specific action, increase confidence. If uncertain, decrease it.
   - "draft_message_enhanced": An improved draft message. CRITICAL FORMATTING RULES:
     * GROUNDING REQUIREMENT: You MUST base the draft message ONLY on information from the guidance documents (citations) provided above. If no guidance documents are provided, or if they don't contain relevant information, you MUST include a statement like "Note: No specific guidance found in RAG documents for this issue type" in your message.
     * If the deterministic analysis shows "Current draft message: N/A" (no message was generated):
       - If guidance documents ARE provided: Generate a draft message using ONLY the query templates and guidance patterns from those documents. DO NOT add information not found in the documents.
       - If NO guidance documents are provided: Generate a basic message but explicitly state that no relevant guidance was found in RAG documents.
     * INCORPORATE EVIDENCE VALUES: If "Evidence Details" are provided above, include relevant values in your message:
       - If "value" or "values" are present, mention the actual value(s) in the message (e.g., "value [X] is outside range")
       - If "reference" is present, use it to provide context (e.g., "per reference [X]")
       - If "notes" are present, incorporate relevant information from notes
       - Include specific dates if "start_date" or "end_date" are present
     * If action is QUERY_SITE: Create a concise query note for site investigators. Format: "Subject [ID]: Please review [issue] in [domain] for fields [field_list]. [Specific issue description with values if available]. Kindly confirm and/or provide clarification/corrections as appropriate."
     * If action is DATA_FIX: Create a brief internal note for data management team. Format: "Recommended data fix for subject [ID] in [domain] for fields [field_list]. [Specific issue with values and recommended action]."
     * If action is MEDICAL_REVIEW: Create a brief internal note for medical review team. Format: "Medical review requested for subject [ID] in [domain] for fields [field_list]. [Specific issue with values and what needs medical assessment]. Please review for clinical significance and protocol compliance."
     * If action is OTHER: Create a brief note explaining what specific action is needed. Format: "Action required for subject [ID] in [domain] for fields [field_list]. [Specific issue with values and what action is needed]."
     * REQUIRED elements: Subject ID ({issue.subject_id}), Domain ({issue.domain}), Field names ({', '.join(issue.fields) if issue.fields else 'N/A'})
     * TONE: Professional, direct, concise. NO email greetings (no "Dear", "Hello"), NO email closings (no "Best regards", "Thank you", "Sincerely"). Write as a technical query note, not an email.
     * LENGTH: Keep it concise - 2-3 sentences maximum. Be specific about the issue but avoid unnecessary pleasantries. Include actual values from evidence when available.
     * If action is IGNORE, set this to null.
   - "missing_info_enhanced": List of specific missing information that would improve the analysis

IMPORTANT: The deterministic analysis is a starting point. Use your judgment to enhance it. If you believe a different action would be more appropriate based on the issue details, you can suggest it in the rationale, but note that action/severity changes require strong justification."""

    return prompt


def _merge_recommendations(
    deterministic: AgentRecommendation, llm_output: dict[str, Any], model_version: str
) -> AgentRecommendation:
    """Merge LLM output with deterministic recommendation."""
    # Use LLM-enhanced values if provided, otherwise fall back to deterministic
    # Note: Empty strings are valid LLM outputs, so we check for None specifically
    rationale = (
        llm_output.get("rationale_enhanced")
        if llm_output.get("rationale_enhanced") is not None
        else deterministic.rationale
    )
    confidence = (
        llm_output.get("confidence_adjusted")
        if llm_output.get("confidence_adjusted") is not None
        else deterministic.confidence
    )
    draft_message = (
        llm_output.get("draft_message_enhanced")
        if llm_output.get("draft_message_enhanced") is not None
        else deterministic.draft_message
    )
    missing_info = (
        llm_output.get("missing_info_enhanced")
        if llm_output.get("missing_info_enhanced") is not None
        else deterministic.missing_info
    )

    # Ensure confidence is in valid range
    confidence = max(0.0, min(1.0, float(confidence)))

    # Add LLM metadata to tool_results
    tool_results = deterministic.tool_results.copy()
    tool_results["llm_enhanced"] = True
    tool_results["llm_model"] = model_version
    tool_results["llm_rationale_original"] = deterministic.rationale
    tool_results["llm_confidence_original"] = deterministic.confidence

    return AgentRecommendation(
        severity=deterministic.severity,  # Keep deterministic severity
        action=deterministic.action,  # Keep deterministic action
        confidence=confidence,
        rationale=rationale,
        missing_info=missing_info,
        citations=deterministic.citations,  # Keep citations from RAG
        tool_results=tool_results,
        draft_message=draft_message,
    )
