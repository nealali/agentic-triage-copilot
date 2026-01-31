"""
Deterministic (non-LLM) issue analysis.

Goal of this module
-------------------
Given an `Issue`, produce a structured `AgentRecommendation` **without any randomness**
and without calling any external services (no LLMs, no network).

Why deterministic analysis matters in clinical/biostats workflows
---------------------------------------------------------------
In regulated environments you often need:
- reproducible results (same input -> same output)
- explainability ("which rule fired and why?")
- auditability (small structured evidence, not huge dumps)

This file implements a simple rule-based analyzer. It's intentionally small and easy
to understand. Later you can replace or extend these rules, or combine them with
retrieval + LLM reasoning, while keeping the deterministic layer as the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from agent.schemas.issue import Issue
from agent.schemas.recommendation import Action, AgentRecommendation, Severity

# -----------------------------
# Small helpers (pure functions)
# -----------------------------


def _lower(text: str) -> str:
    """Lower-case helper (keeps code below tidy)."""

    return text.lower()


def _contains_all(haystack: str, needles: Iterable[str]) -> bool:
    """
    Returns True if *all* keywords in `needles` appear in `haystack`.

    We use this for simple keyword-based detection rules.
    """

    h = _lower(haystack)
    return all(n in h for n in needles)


def _walk_values(obj: Any) -> Iterable[Any]:
    """
    Recursively walk through nested dict/list structures and yield values.

    Why:
    `evidence_payload` is a generic JSON-like structure (dicts/lists/strings/numbers).
    To detect missing values or numeric signals, we need a safe way to scan it.
    """

    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_values(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_values(item)
    else:
        yield obj


def _has_missing_value(evidence_payload: dict[str, Any]) -> bool:
    """
    Heuristic missingness detection.

    Returns True if we see any obvious "missing" signal in the evidence:
    - Python None
    - empty string
    - strings like "null" / "none" (common in JSON exports)
    """

    for v in _walk_values(evidence_payload):
        if v is None:
            return True
        if isinstance(v, str) and v.strip() == "":
            return True
        if isinstance(v, str) and v.strip().lower() in {"null", "none", "na", "n/a"}:
            return True
    return False


def _try_parse_datetime(value: Any) -> datetime | None:
    """
    Try to parse a datetime from a value.

    We support common ISO-like strings:
    - "2024-01-31"
    - "2024-01-31T12:34:56"
    - "2024-01-31T12:34:56Z"  (we strip the trailing Z)

    If parsing fails, return None instead of raising (so the analyzer stays robust).
    """

    if not isinstance(value, str):
        return None

    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1]

    # `datetime.fromisoformat` is a standard-library parser for ISO strings.
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _extract_possible_dates(
    evidence_payload: dict[str, Any],
) -> tuple[datetime | None, datetime | None, dict[str, Any]]:
    """
    Extract likely start/end dates from evidence_payload.

    We use a *heuristic* approach:
    - If keys contain "start" we treat them as possible start date fields
    - If keys contain "end" we treat them as possible end date fields

    Returns (start_dt, end_dt, signals) where signals are small explainable pieces.
    """

    start_dt: datetime | None = None
    end_dt: datetime | None = None
    signals: dict[str, Any] = {"start_candidates": [], "end_candidates": []}

    for k, v in evidence_payload.items():
        key = str(k).lower()
        if "start" in key:
            parsed = _try_parse_datetime(v)
            signals["start_candidates"].append({"key": k, "value": v, "parsed": bool(parsed)})
            if parsed and start_dt is None:
                start_dt = parsed
        if "end" in key:
            parsed = _try_parse_datetime(v)
            signals["end_candidates"].append({"key": k, "value": v, "parsed": bool(parsed)})
            if parsed and end_dt is None:
                end_dt = parsed

    return start_dt, end_dt, signals


def _extract_numeric_signals(evidence_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract numeric values from evidence_payload (shallow heuristic).

    We keep this intentionally small: we only pick up numbers that appear as
    direct dict values or inside lists/dicts.

    Returns a list of {key_path, value} style entries, capped later for audit friendliness.
    """

    signals: list[dict[str, Any]] = []

    def walk(obj: Any, path: str) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                walk(item, f"{path}[{i}]")
        else:
            if isinstance(obj, (int, float)) and not isinstance(obj, bool):
                signals.append({"key_path": path, "value": obj})

    walk(evidence_payload, "")
    return signals


def _is_out_of_range_signal(key_path: str, value: float) -> bool:
    """
    Very simple clinical-style heuristics for "out of range" signals.

    This is not meant to be clinically definitive — it's a proof-of-concept.
    The key idea is: deterministic checks produce a structured signal that can
    later be reviewed and refined.
    """

    k = key_path.lower()

    # If the key hints at systolic/diastolic blood pressure.
    if "sys" in k or "sbp" in k:
        return value < 50 or value > 250
    if "dia" in k or "dbp" in k:
        return value < 30 or value > 150

    # Heart rate / pulse
    if "hr" in k or "pulse" in k:
        return value < 30 or value > 220

    # Temperature (Celsius-ish)
    if "temp" in k:
        return value < 34 or value > 43

    # Generic fallback heuristic:
    # Very large/small values are suspicious in many contexts.
    return value < -1_000_000 or value > 1_000_000


# -----------------------------
# Rule engine (simple & explicit)
# -----------------------------


@dataclass(frozen=True)
class _RuleMatch:
    """Internal structure for returning a matched rule and its outputs."""

    rule_fired: str
    severity: Severity
    action: Action
    confidence: float
    rationale: str
    missing_info: list[str]
    tool_results: dict[str, Any]
    draft_message: str | None


def _build_query_site_message(issue: Issue) -> str:
    """
    Template for a polite site query.

    In a real product, you'd version these templates and apply org-specific tone rules.
    """

    fields_str = ", ".join(issue.fields) if issue.fields else "(unspecified fields)"
    return (
        f"Subject {issue.subject_id}: Please review the following potential issue "
        f"in {issue.domain} for fields [{fields_str}]. {issue.description} "
        "Kindly confirm and/or provide clarification/corrections as appropriate."
    )


def _build_data_fix_message(issue: Issue) -> str:
    """Template for an internal data-fix note."""

    fields_str = ", ".join(issue.fields) if issue.fields else "(unspecified fields)"
    return (
        f"Recommended data fix for subject {issue.subject_id} in {issue.domain} "
        f"for fields [{fields_str}]. Review the evidence payload and apply a consistent correction."
    )


def analyze_issue(issue: Issue) -> AgentRecommendation:
    """
    Main entrypoint: analyze an Issue and return an AgentRecommendation.

    The rules are evaluated in priority order (first match wins), which makes behavior predictable.
    """

    desc = issue.description or ""
    desc_l = _lower(desc)
    evidence = issue.evidence_payload or {}

    # Rule 1: AE date inconsistency
    # Trigger if:
    # - description mentions "end before start" (keyword style), OR
    # - evidence has start/end dates and end < start
    start_dt, end_dt, date_signals = _extract_possible_dates(evidence)
    ae_keywords_hit = _contains_all(desc, ["end", "before", "start"])
    ae_dates_inconsistent = bool(start_dt and end_dt and end_dt < start_dt)

    if ae_keywords_hit or ae_dates_inconsistent:
        tool_results = {
            "rule_fired": "AE_DATE_INCONSISTENCY",
            "signals": {
                "keyword_match": ae_keywords_hit,
                "parsed_start_found": bool(start_dt),
                "parsed_end_found": bool(end_dt),
                "end_before_start": ae_dates_inconsistent,
                "date_candidates": date_signals,
            },
            "evidence_summary": {
                "subject_id": issue.subject_id,
                "fields": issue.fields,
            },
        }
        return AgentRecommendation(
            severity=Severity.HIGH,
            action=Action.QUERY_SITE,
            confidence=0.9,
            rationale="Potential AE date inconsistency: end appears to be before start.",
            missing_info=[],
            citations=[],
            tool_results=tool_results,
            draft_message=_build_query_site_message(issue),
        )

    # Rule 2: Missing critical field
    missing_keyword = "missing" in desc_l
    missing_in_evidence = _has_missing_value(evidence)
    if missing_keyword or missing_in_evidence:
        tool_results = {
            "rule_fired": "MISSING_CRITICAL_FIELD",
            "signals": {
                "keyword_match": missing_keyword,
                "missing_value_detected": missing_in_evidence,
            },
            "evidence_summary": {
                "subject_id": issue.subject_id,
                "fields": issue.fields,
            },
        }
        return AgentRecommendation(
            severity=Severity.MEDIUM,
            action=Action.DATA_FIX,
            confidence=0.7,
            rationale="Missing value(s) detected for one or more critical fields.",
            missing_info=[],
            citations=[],
            tool_results=tool_results,
            draft_message=_build_data_fix_message(issue),
        )

    # Rule 3: Out-of-range vitals/labs
    oor_keyword = "out of range" in desc_l
    numeric_signals = _extract_numeric_signals(evidence)
    oor_values = [
        s for s in numeric_signals if _is_out_of_range_signal(s["key_path"], float(s["value"]))
    ]
    if oor_keyword or oor_values:
        tool_results = {
            "rule_fired": "OUT_OF_RANGE",
            "signals": {
                "keyword_match": oor_keyword,
                # Keep evidence small: include only first few suspicious values.
                "out_of_range_values": oor_values[:5],
                "out_of_range_count": len(oor_values),
            },
            "evidence_summary": {
                "subject_id": issue.subject_id,
                "fields": issue.fields,
            },
        }
        return AgentRecommendation(
            severity=Severity.MEDIUM,
            action=Action.QUERY_SITE,
            confidence=0.7,
            rationale="Potential out-of-range value(s) detected in evidence.",
            missing_info=[],
            citations=[],
            tool_results=tool_results,
            draft_message=_build_query_site_message(issue),
        )

    # Rule 4: Duplicate record
    dup_keyword = "duplicate" in desc_l
    if dup_keyword:
        tool_results = {
            "rule_fired": "DUPLICATE_RECORD",
            "signals": {"keyword_match": True},
            "evidence_summary": {
                "subject_id": issue.subject_id,
                "fields": issue.fields,
            },
        }
        return AgentRecommendation(
            severity=Severity.LOW,
            action=Action.DATA_FIX,
            confidence=0.6,
            rationale="Possible duplicate record indicated by the issue description.",
            missing_info=[],
            citations=[],
            tool_results=tool_results,
            draft_message=_build_data_fix_message(issue),
        )

    # Fallback rule: ask for medical review (low confidence)
    # This is a safe default when deterministic signals are weak/absent.
    tool_results = {
        "rule_fired": "FALLBACK",
        "signals": {"keyword_match": False},
        "evidence_summary": {
            "subject_id": issue.subject_id,
            "fields": issue.fields,
        },
    }
    return AgentRecommendation(
        severity=Severity.LOW,
        action=Action.MEDICAL_REVIEW,
        confidence=0.3,
        rationale="Insufficient deterministic signals to make a strong recommendation.",
        missing_info=[
            "Confirm which records/visits are impacted.",
            "Provide relevant start/end dates or measurement values.",
            "Confirm the expected rule/specification for this check.",
        ],
        citations=[],
        tool_results=tool_results,
        draft_message=None,
    )
