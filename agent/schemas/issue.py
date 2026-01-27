from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class IssueSource(str, Enum):
    """Source of the issue."""

    MANUAL = "manual"
    EDIT_CHECK = "edit_check"
    LISTING_REVIEW = "listing_review"


class IssueDomain(str, Enum):
    """Domain of the issue."""

    DM = "DM"
    VS = "VS"
    LB = "LB"
    AE = "AE"
    COMMERCIAL = "COMMERCIAL"
    MEDICAL = "MEDICAL"


class IssueCreate(BaseModel):
    """Input model for creating a new issue."""

    source: IssueSource = Field(..., description="Source of the issue")
    domain: IssueDomain = Field(..., description="Domain of the issue")
    subject_id: str = Field(..., description="ID of the subject")
    fields: list[str] = Field(..., description="List of fields related to the issue")
    description: str = Field(..., description="Description of the issue")
    evidence_payload: dict[str, Any] = Field(
        ..., description="Evidence payload containing additional data"
    )


class Issue(BaseModel):
    """Stored and returned issue model."""

    issue_id: UUID = Field(
        default_factory=uuid4, description="Unique identifier for the issue"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when the issue was created"
    )
    status: str = Field(..., description="Current status of the issue")
    source: IssueSource = Field(..., description="Source of the issue")
    domain: IssueDomain = Field(..., description="Domain of the issue")
    subject_id: str = Field(..., description="ID of the subject")
    fields: list[str] = Field(..., description="List of fields related to the issue")
    description: str = Field(..., description="Description of the issue")
    evidence_payload: dict[str, Any] = Field(
        ..., description="Evidence payload containing additional data"
    )
