"""
Recommendation schemas (Pydantic v2).

This module defines the structured output we want from the "agent recommendation" step.
In an enterprise setting, we want recommendations to be:

- **Structured**: consistent fields for severity/action/confidence every time
- **Validatable**: e.g., confidence must be between 0 and 1
- **Auditable**: rationale + citations + tool_results can be stored and reviewed later
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Action(str, Enum):
    """What the system recommends doing next for an issue."""

    QUERY_SITE = "QUERY_SITE"
    DATA_FIX = "DATA_FIX"
    MEDICAL_REVIEW = "MEDICAL_REVIEW"
    IGNORE = "IGNORE"
    OTHER = "OTHER"


class Severity(str, Enum):
    """How serious/urgent the issue appears to be."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AgentRecommendation(BaseModel):
    """
    A structured recommendation produced by the agent.

    This model is designed to be stored, displayed, and audited:
    - **severity/action** help prioritize and route work
    - **confidence** communicates uncertainty (0 = not confident, 1 = very confident)
    - **rationale** provides a short human-readable explanation
    - **missing_info** makes uncertainty explicit (what would improve confidence)
    - **citations** points to retrieved evidence (future RAG integration)
    - **tool_results** captures small structured outputs from deterministic checks
    - **draft_message** is optional text that a human can review/edit (e.g., site query)
    """

    severity: Severity = Field(..., description="Severity level of the issue.")
    action: Action = Field(..., description="Recommended next action for the issue.")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1 (inclusive).",
    )
    rationale: str = Field(
        ...,
        description="Short, non-rambling rationale explaining the recommendation.",
    )
    missing_info: list[str] = Field(
        default_factory=list,
        description="List of missing information that would improve the recommendation.",
    )
    citations: list[str] = Field(
        default_factory=list,
        description="List of citation IDs for supporting guidance (for future RAG).",
    )
    tool_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured evidence returned by deterministic tools (not raw dumps).",
    )
    draft_message: str | None = Field(
        default=None,
        description="Optional draft message/query text for human review and editing.",
    )
