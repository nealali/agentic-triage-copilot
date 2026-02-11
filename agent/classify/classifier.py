"""
Automatic issue classification.

This module analyzes issue characteristics to determine if an issue can be handled
deterministically (rule-based) or requires LLM+RAG for nuanced analysis.

Classification Strategy (Production Best Practices):
---------------------------------------------------
1. **General rules first**: Apply domain-agnostic patterns before domain-specific logic
2. **Scoring system**: Use weighted scoring to combine multiple signals
3. **Priority-based**: High-priority rules override low-priority ones
4. **Evidence-based**: Consider description, evidence payload, domain, and fields
5. **Confidence scoring**: Return confidence levels for downstream decision-making
6. **LLM fallback**: Use LLM for uncertain cases when enabled

Rule Categories:
--------------
1. **High-priority general rules** (checked first):
   - Explicit complexity keywords (e.g., "requires review", "unclear")
   - Explicit deterministic patterns (e.g., "missing", "out of range")
   
2. **Structural analysis** (general, domain-agnostic):
   - Description length and complexity
   - Evidence payload ambiguity
   - Multiple conflicting signals
   
3. **Domain-specific refinements** (applied after general rules):
   - Domain-specific patterns that refine general classification
   - Domain-specific exceptions to general rules

4. **Default behavior**:
   - Default to deterministic with low confidence
   - Triggers LLM fallback if enabled

Classification criteria:
- DETERMINISTIC: Clear, rule-based issues (missing fields, date inconsistencies, simple out-of-range)
- LLM_REQUIRED: Complex issues requiring clinical judgment, ambiguity resolution, or nuanced analysis
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from agent.schemas.issue import IssueCreate, IssueDomain, IssueType

# ============================================================================
# GENERAL CLASSIFICATION RULES (Domain-Agnostic)
# ============================================================================

# High-priority keywords that strongly indicate LLM-required complexity
# These are checked first as they are explicit signals of complexity
LLM_REQUIRED_KEYWORDS = {
    # Explicit review requirements
    "requires review",
    "requires manual",
    "requires medical",
    "manual review",
    "medical review",
    "clinical review",
    # Ambiguity indicators
    "complex",
    "ambiguous",
    "unclear",
    "unclear if",
    "may be",
    "suspected",
    # Context and judgment requirements
    "clinical significance",
    "significance unclear",
    "context needed",
    "clinical context",
    "medical judgment",
    # Discrepancy and conflict indicators
    "discrepancy",
    "discrepancy vs",
    "differs from",
    "conflicts",
    "reconciliation",
    # Assessment requirements
    "assess if",
    "determine if",
    "need to assess",
    "need to determine",
    # Non-standard situations
    "uncommon",
    "not in standard",
    "not standard",
    "not in dictionary",
    "not found in",
    # Multiple/related conditions
    "multiple related",
    "related conditions",
}

# High-priority patterns that strongly indicate deterministic handling
# These are clear, rule-based patterns that don't require judgment
DETERMINISTIC_PATTERNS = {
    # Missing data patterns
    "missing",
    "missing required",
    "missing field",
    # Range validation patterns
    "out of range",
    "outside range",
    "outside limits",
    # Data type/format issues
    "invalid",
    "invalid format",
    "invalid date",
    "invalid value",
    # Date consistency patterns (simple)
    "before start",
    "after end",
    "end before start",
    "end date is before start",
    # Duplicate detection
    "duplicate",
    "duplicate record",
    "duplicate entry",
    # Unit consistency (simple cases)
    "inconsistent units",
    # Partial/incomplete data (simple cases)
    "partial date",
    "incomplete",
}

# Medium-priority patterns that suggest complexity (but less definitive)
COMPLEXITY_INDICATORS = {
    "timeline conflicts",
    "date reconciliation",
    "impact on",
    "affects",
    "calculations",
    "bmi",
    "combination product",
    "coding issue",
}

# Patterns that suggest simple deterministic handling (medium priority)
SIMPLE_PATTERNS = {
    "required field",
    "field required",
    "value required",
}


# ============================================================================
# DOMAIN-SPECIFIC RULES (Refinements to General Rules)
# ============================================================================

# Domain-specific patterns that refine classification
# These are checked after general rules and can override or refine the classification
DOMAIN_SPECIFIC_RULES: dict[IssueDomain, dict[str, list[str]]] = {
    IssueDomain.AE: {
        "llm_required": [
            "multiple related",
            "single or multiple",
            "related conditions",
            "clinical significance",
            "timeline conflicts",
            "date reconciliation",
        ],
        "deterministic": [
            "end before start",
            "end date is before start",
        ],
    },
    IssueDomain.LB: {
        "llm_required": [
            "discrepancy vs",
            "differs from",
            "clinical significance",
            "significance unclear",
        ],
        "deterministic": [
            # Simple out-of-range (without significance concerns)
            # Handled by general pattern with exclusion check
        ],
    },
    IssueDomain.DM: {
        "llm_required": [
            "impact on",
            "affects",
            "calculations",
            "bmi",
        ],
        "deterministic": [
            # Simple unit inconsistencies (without impact)
            # Handled by general pattern with exclusion check
        ],
    },
    IssueDomain.CM: {
        "llm_required": [
            "not in standard",
            "not standard",
            "uncommon",
            "manual review",
            "requires manual",
            "requires review",
            "combination product",
            "not in dictionary",
            "coding issue",
        ],
        "deterministic": [],
    },
}


# ============================================================================
# CLASSIFICATION RESULT MODEL
# ============================================================================


@dataclass
class ClassificationResult:
    """
    Result of issue classification with confidence indicator.

    Attributes:
        issue_type: The classified type (DETERMINISTIC or LLM_REQUIRED)
        confidence: Confidence level ("high", "medium", "low")
        method: How classification was performed ("rule_based" or "llm_fallback")
        reason: Human-readable explanation of the classification
        score: Optional numeric score (higher = more confident in LLM_REQUIRED)
    """

    issue_type: IssueType
    confidence: str  # "high", "medium", "low"
    method: str  # "rule_based" or "llm_fallback"
    reason: str | None = None
    score: float | None = (
        None  # Optional: -1.0 to 1.0, negative = deterministic, positive = LLM-required
    )


# ============================================================================
# MAIN CLASSIFICATION FUNCTION
# ============================================================================


def classify_issue(issue_create: IssueCreate, use_llm_fallback: bool | None = None) -> IssueType:
    """
    Automatically classify an issue as DETERMINISTIC or LLM_REQUIRED.

    Classification logic (production best practices):
    1. Rule-based classification (fast, deterministic)
       - General rules first (domain-agnostic)
       - Domain-specific refinements
       - Scoring-based decision
    2. LLM fallback for uncertain cases (optional, configurable)

    Args:
        issue_create: The issue to classify
        use_llm_fallback: If True, use LLM for uncertain cases. If None, checks CLASSIFIER_USE_LLM_FALLBACK env var.

    Returns:
        IssueType indicating the required handling approach
    """
    # Run rule-based classification
    result = _classify_rule_based(issue_create)

    # If confidence is low and LLM fallback is enabled, try LLM classification
    if result.confidence == "low":
        if use_llm_fallback is None:
            use_llm_fallback = os.getenv("CLASSIFIER_USE_LLM_FALLBACK", "").strip().lower() in (
                "1",
                "true",
                "yes",
            )

        if use_llm_fallback:
            llm_result = _classify_with_llm(issue_create)
            if llm_result:
                return llm_result.issue_type

    return result.issue_type


# ============================================================================
# RULE-BASED CLASSIFICATION (General Rules First)
# ============================================================================


def _classify_rule_based(issue_create: IssueCreate) -> ClassificationResult:
    """
    Rule-based classification following production best practices.

    Classification order (general → specific):
    1. High-priority general rules (explicit keywords/patterns)
    2. Structural analysis (description length, evidence ambiguity)
    3. Domain-specific refinements
    4. Default behavior

    Returns:
        ClassificationResult with issue_type, confidence, method, and reason
    """
    desc_lower = (issue_create.description or "").lower()
    domain = issue_create.domain
    evidence = issue_create.evidence_payload or {}

    # Track scoring for multi-signal decisions
    llm_score = 0.0
    deterministic_score = 0.0
    matched_rules: list[str] = []

    # ========================================================================
    # STEP 1: High-Priority General Rules (Checked First)
    # ========================================================================

    # Check for explicit LLM-required keywords (high priority, high confidence)
    for keyword in LLM_REQUIRED_KEYWORDS:
        if keyword in desc_lower:
            return ClassificationResult(
                IssueType.LLM_REQUIRED,
                confidence="high",
                method="rule_based",
                reason=f"Explicit complexity keyword: '{keyword}'",
                score=1.0,
            )

    # Check for explicit deterministic patterns (high priority, high confidence)
    for pattern in DETERMINISTIC_PATTERNS:
        if pattern in desc_lower:
            # Some deterministic patterns need exclusion checks for complexity
            if _is_simple_deterministic_pattern(pattern, desc_lower, domain):
                return ClassificationResult(
                    IssueType.DETERMINISTIC,
                    confidence="high",
                    method="rule_based",
                    reason=f"Deterministic pattern: '{pattern}'",
                    score=-1.0,
                )

    # ========================================================================
    # STEP 2: Structural Analysis (General, Domain-Agnostic)
    # ========================================================================

    # Check evidence payload for ambiguity indicators
    evidence_ambiguity = _assess_evidence_ambiguity(evidence, desc_lower)
    if evidence_ambiguity:
        llm_score += 0.5
        matched_rules.append(f"Evidence ambiguity: {evidence_ambiguity}")

    # Check description length and structural complexity
    structural_complexity = _assess_structural_complexity(
        issue_create.description or "", desc_lower
    )
    if structural_complexity:
        llm_score += 0.3
        matched_rules.append(structural_complexity)

    # Check for complexity indicators (medium priority)
    for indicator in COMPLEXITY_INDICATORS:
        if indicator in desc_lower:
            llm_score += 0.4
            matched_rules.append(f"Complexity indicator: '{indicator}'")

    # Check for simple patterns (medium priority)
    for pattern in SIMPLE_PATTERNS:
        if pattern in desc_lower:
            deterministic_score += 0.3
            matched_rules.append(f"Simple pattern: '{pattern}'")

    # ========================================================================
    # STEP 3: Domain-Specific Refinements
    # ========================================================================

    domain_refinement = _apply_domain_specific_rules(domain, desc_lower)
    if domain_refinement:
        if domain_refinement["type"] == "llm_required":
            llm_score += 0.6
            matched_rules.append(f"Domain-specific ({domain.value}): {domain_refinement['reason']}")
        else:
            deterministic_score += 0.6
            matched_rules.append(f"Domain-specific ({domain.value}): {domain_refinement['reason']}")

    # ========================================================================
    # STEP 4: Decision Based on Scoring
    # ========================================================================

    # Calculate net score (positive = LLM-required, negative = deterministic)
    net_score = llm_score - deterministic_score

    # High confidence thresholds
    if llm_score >= 0.8:
        return ClassificationResult(
            IssueType.LLM_REQUIRED,
            confidence="high",
            method="rule_based",
            reason="; ".join(matched_rules) if matched_rules else "Multiple complexity indicators",
            score=net_score,
        )

    if deterministic_score >= 0.8:
        return ClassificationResult(
            IssueType.DETERMINISTIC,
            confidence="high",
            method="rule_based",
            reason=(
                "; ".join(matched_rules) if matched_rules else "Multiple deterministic indicators"
            ),
            score=net_score,
        )

    # Medium confidence thresholds
    if net_score > 0.3:
        return ClassificationResult(
            IssueType.LLM_REQUIRED,
            confidence="medium",
            method="rule_based",
            reason="; ".join(matched_rules) if matched_rules else "Moderate complexity indicators",
            score=net_score,
        )

    if net_score < -0.3:
        return ClassificationResult(
            IssueType.DETERMINISTIC,
            confidence="medium",
            method="rule_based",
            reason=(
                "; ".join(matched_rules) if matched_rules else "Moderate deterministic indicators"
            ),
            score=net_score,
        )

    # Low confidence - default to deterministic but trigger LLM fallback consideration
    return ClassificationResult(
        IssueType.DETERMINISTIC,
        confidence="low",
        method="rule_based",
        reason="No clear indicators, defaulting to deterministic",
        score=net_score,
    )


# ============================================================================
# HELPER FUNCTIONS FOR GENERAL RULES
# ============================================================================


def _is_simple_deterministic_pattern(pattern: str, desc_lower: str, domain: IssueDomain) -> bool:
    """
    Check if a deterministic pattern is truly simple (not complex).

    Some patterns like "out of range" or "inconsistent units" can be simple
    OR complex depending on context. This function applies exclusion logic.

    Args:
        pattern: The deterministic pattern matched
        desc_lower: Lowercase description
        domain: Issue domain

    Returns:
        True if pattern indicates simple deterministic handling
    """
    # "out of range" is simple unless it mentions clinical significance
    if pattern == "out of range":
        return "significance" not in desc_lower

    # "inconsistent units" is simple unless it affects calculations
    if pattern == "inconsistent units":
        return (
            "impact" not in desc_lower
            and "affects" not in desc_lower
            and "calculations" not in desc_lower
        )

    # All other patterns are simple by default
    return True


def _assess_evidence_ambiguity(evidence: dict[str, Any], description_lower: str) -> str | None:
    """
    Assess if evidence payload suggests ambiguity requiring LLM analysis.

    This is a general rule that works across all domains.

    Args:
        evidence: The evidence payload
        description_lower: Lowercase description for context

    Returns:
        Reason string if ambiguity detected, None otherwise
    """
    # Check for conflicting values mentioned in description
    if "conflicts" in description_lower or "differs" in description_lower:
        return "Conflicting values in evidence"

    # Check for multiple related values that need interpretation
    if isinstance(evidence.get("rows"), list) and len(evidence.get("rows", [])) > 1:
        if "assess" in description_lower or "determine" in description_lower:
            return "Multiple rows requiring assessment"

    # Check for date conflicts
    if "start_date" in evidence and "end_date" in evidence:
        if any(word in description_lower for word in ["conflict", "reconciliation", "timeline"]):
            return "Date conflicts in evidence"

    # Check for reference values that differ from actual values
    if "reference" in evidence and "value" in evidence:
        if "differs" in description_lower or "discrepancy" in description_lower:
            return "Value-reference discrepancy"

    return None


def _assess_structural_complexity(description: str, desc_lower: str) -> str | None:
    """
    Assess structural complexity of description (general rule).

    Longer descriptions with multiple clauses often indicate complexity.
    This is domain-agnostic and works across all issue types.

    Args:
        description: Original description
        desc_lower: Lowercase description

    Returns:
        Reason string if complexity detected, None otherwise
    """
    desc_len = len(description)

    # Very short descriptions (< 20 chars) are usually simple
    if desc_len < 20:
        return None

    # Long descriptions (> 100 chars) with multiple clauses suggest complexity
    if desc_len > 100:
        # Count clauses (rough heuristic: periods, semicolons, "and", "or")
        clause_count = (
            desc_lower.count(".")
            + desc_lower.count(";")
            + desc_lower.count(" and ")
            + desc_lower.count(" or ")
        )

        if clause_count >= 3:
            # Multiple clauses + no clear deterministic pattern = likely complex
            if not any(pattern in desc_lower for pattern in DETERMINISTIC_PATTERNS):
                return f"Long description ({desc_len} chars) with {clause_count} clauses"

    # Check for question marks (indicates uncertainty)
    if "?" in description:
        return "Description contains questions (uncertainty indicator)"

    # Check for conditional language
    conditional_words = ["if", "whether", "may", "might", "could", "possibly"]
    if any(word in desc_lower for word in conditional_words):
        conditional_count = sum(1 for word in conditional_words if word in desc_lower)
        if conditional_count >= 2:
            return f"Multiple conditional phrases ({conditional_count}) indicating uncertainty"

    return None


def _apply_domain_specific_rules(domain: IssueDomain, desc_lower: str) -> dict[str, str] | None:
    """
    Apply domain-specific rules to refine classification.

    These rules are checked AFTER general rules and can refine or override
    the general classification based on domain-specific knowledge.

    Args:
        domain: Issue domain
        desc_lower: Lowercase description

    Returns:
        Dict with "type" and "reason" if domain rule matches, None otherwise
    """
    domain_rules = DOMAIN_SPECIFIC_RULES.get(domain)
    if not domain_rules:
        return None

    # Check LLM-required patterns first (higher priority)
    for pattern in domain_rules.get("llm_required", []):
        if pattern in desc_lower:
            return {
                "type": "llm_required",
                "reason": f"Domain-specific pattern: '{pattern}'",
            }

    # Check deterministic patterns
    for pattern in domain_rules.get("deterministic", []):
        if pattern in desc_lower:
            return {
                "type": "deterministic",
                "reason": f"Domain-specific pattern: '{pattern}'",
            }

    return None


# ============================================================================
# LLM FALLBACK CLASSIFICATION
# ============================================================================


def _classify_with_llm(issue_create: IssueCreate) -> ClassificationResult | None:
    """
    Use LLM to classify an issue when rule-based classification is uncertain.

    This is a fallback mechanism for edge cases where the rule-based classifier
    has low confidence.

    Args:
        issue_create: The issue to classify

    Returns:
        ClassificationResult if LLM classification succeeds, None otherwise
    """
    try:
        from agent.analyze.llm import _get_openai_client, _is_llm_enabled

        if not _is_llm_enabled():
            return None

        client = _get_openai_client(force=False)
        if client is None:
            return None

        # Build classification prompt
        prompt = _build_classification_prompt(issue_create)

        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": "You are a clinical data quality analyst. Classify issues as either 'deterministic' (can be handled by simple rules) or 'llm_required' (needs nuanced analysis). Respond with JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,  # Very low temperature for consistent classification
            response_format={"type": "json_object"},
        )

        llm_output = json.loads(response.choices[0].message.content)
        issue_type_str = llm_output.get("classification", "deterministic").lower()
        issue_type = (
            IssueType.LLM_REQUIRED if issue_type_str == "llm_required" else IssueType.DETERMINISTIC
        )

        return ClassificationResult(
            issue_type=issue_type,
            confidence="high",
            method="llm_fallback",
            reason=llm_output.get("reason", "LLM classification"),
        )

    except Exception:
        # On any error, return None to fall back to rule-based result
        return None


def _build_classification_prompt(issue_create: IssueCreate) -> str:
    """
    Build a prompt for LLM-based classification.

    Args:
        issue_create: The issue to classify

    Returns:
        Prompt string for the LLM
    """
    evidence_summary = (
        json.dumps(issue_create.evidence_payload, indent=2)
        if issue_create.evidence_payload
        else "{}"
    )

    prompt = f"""Classify this clinical data quality issue.

Issue Details:
- Domain: {issue_create.domain.value}
- Subject ID: {issue_create.subject_id}
- Fields: {', '.join(issue_create.fields) if issue_create.fields else 'N/A'}
- Description: {issue_create.description}
- Evidence: {evidence_summary}

Classification Options:
1. "deterministic": Simple, rule-based issues (missing fields, date inconsistencies, out-of-range values, duplicates)
2. "llm_required": Complex issues requiring clinical judgment, ambiguity resolution, or nuanced analysis

Respond with JSON:
{{
  "classification": "deterministic" or "llm_required",
  "reason": "Brief explanation of why this classification was chosen"
}}"""

    return prompt
