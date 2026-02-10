"""
Issue schemas (Pydantic v2).

What this file does
-------------------
This module defines the **data contracts** used by the API (and later, the agent workflow).
In a production system—especially in pharma/biotech—having strict contracts is essential
because it makes the system:

- **Consistent**: every issue looks the same shape everywhere (API, DB, logs, UI).
- **Validatable**: bad or missing data is caught early, at the boundary.
- **Auditable**: decisions can reference structured fields (domain, source, evidence).

Educational note
----------------
These models use **Pydantic v2**. Pydantic models are normal Python classes that:
- validate input data (types, required fields)
- convert from JSON/dicts into Python objects
- serialize back to JSON/dicts for APIs
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class IssueSource(str, Enum):
    """
    Where this issue came from.

    Why an Enum?
    - An Enum restricts values to a known set (no typos like "manul").
    - Using `str, Enum` means values are JSON-friendly strings.

    Example allowed values:
    - "manual"
    - "edit_check"
    - "listing"
    """

    MANUAL = "manual"
    EDIT_CHECK = "edit_check"
    LISTING = "listing"


class IssueStatus(str, Enum):
    """
    Lifecycle status of an issue.

    Why track status?
    - It helps teams filter work (what is new vs already reviewed).
    - It helps systems enforce workflow steps (e.g., only triaged issues can be closed).

    Typical lifecycle for this MVP:
    - OPEN: newly created issue, not yet analyzed
    - TRIAGED: analyzed, recommendation/run exists
    - CLOSED: resolved/accepted/ignored (no further action)
    """

    OPEN = "open"
    TRIAGED = "triaged"
    CLOSED = "closed"


class IssueDomain(str, Enum):
    """
    Which domain (dataset area / business area) this issue belongs to.

    In clinical trials, examples include:
    - DM: demographics
    - VS: vital signs
    - LB: labs
    - AE: adverse events

    We also include COMMERCIAL and MEDICAL to reflect broader enterprise use cases.
    """

    DM = "DM"
    VS = "VS"
    LB = "LB"
    AE = "AE"
    COMMERCIAL = "COMMERCIAL"
    MEDICAL = "MEDICAL"


class IssueCreate(BaseModel):
    """
    Input model used when a client creates an issue.

    Important idea: this model intentionally does NOT include `issue_id` or `created_at`.
    Those are **system-managed fields** (the server generates them) so the client can't:
    - accidentally create duplicates
    - spoof timestamps/IDs

    In Pydantic v2, you can convert a model to a plain dict with:
    - `issue_create.model_dump()`
    """

    # Type hints (like `str`, `list[str]`) tell both:
    # - humans reading the code what to expect
    # - Pydantic how to validate incoming JSON
    source: IssueSource = Field(..., description="Source of the issue")
    domain: IssueDomain = Field(..., description="Domain of the issue")
    subject_id: str = Field(..., description="ID of the subject")
    fields: list[str] = Field(..., description="List of fields related to the issue")
    description: str = Field(..., description="Description of the issue")
    evidence_payload: dict[str, Any] = Field(
        ..., description="Evidence payload containing additional data"
    )


class IssueStatusUpdate(BaseModel):
    """Request body for PATCH /issues/{issue_id} to change status (e.g. close issue)."""

    status: IssueStatus = Field(..., description="New status (open, triaged, closed).")


class Issue(BaseModel):
    """
    Stored/returned issue model.

    This is what the API returns after creation, and what we store in persistence later.

    It contains everything from `IssueCreate` PLUS additional system fields:
    - `issue_id`: unique identifier (UUID)
    - `created_at`: timestamp when the issue was created
    - `status`: lifecycle state (e.g., open/closed) — later you may make this an Enum too
    """

    # `UUID` is a standard type for unique IDs.
    # `default_factory=uuid4` means: "if not provided, generate a new UUID automatically".
    issue_id: UUID = Field(default_factory=uuid4, description="Unique identifier for the issue")

    # `datetime` holds timestamps.
    # `default_factory=datetime.utcnow` generates the timestamp at creation time.
    #
    # Note: `utcnow()` returns a UTC time without timezone info ("naive datetime").
    # In production you may choose timezone-aware UTC timestamps; we keep it simple here.
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp when the issue was created"
    )
    status: IssueStatus = Field(
        default=IssueStatus.OPEN,
        description="Current status of the issue (open/triaged/closed).",
    )

    # These fields mirror IssueCreate so Issue contains the full issue context.
    source: IssueSource = Field(..., description="Source of the issue")
    domain: IssueDomain = Field(..., description="Domain of the issue")
    subject_id: str = Field(..., description="ID of the subject")
    fields: list[str] = Field(..., description="List of fields related to the issue")
    description: str = Field(..., description="Description of the issue")
    evidence_payload: dict[str, Any] = Field(
        ..., description="Evidence payload containing additional data"
    )
