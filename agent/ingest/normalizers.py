"""
Issue ingestion normalizers (standardization layer).

Why this exists (enterprise realism)
-----------------------------------
In real pharma/biotech environments, issues arrive from many sources:
- EDC edit checks
- SDTM/ADaM validation tools
- SAS QC listings
- manual reviewer notes

Each source has its own payload format.

The core product goal is: regardless of source, we normalize into one canonical contract:
`IssueCreate` (source, domain, subject_id, fields, description, evidence_payload).

That standardization is what enables:
- consistent triage rules
- consistent audit trails
- consistent UI workflows
"""

from __future__ import annotations

from typing import Any

from agent.schemas.issue import IssueCreate, IssueDomain, IssueSource


def from_edc_check(payload: dict[str, Any]) -> IssueCreate:
    """
    Normalize a mock "EDC edit check" payload into IssueCreate.

    This is intentionally simple and educational.
    In production, you would:
    - validate required keys
    - map study-specific field names
    - sanitize evidence payload sizes
    """

    # Example expected payload shape (mock):
    # {
    #   "check_id": "AE_001",
    #   "domain": "AE",
    #   "subject_id": "SUBJ-123",
    #   "fields": ["AESTDTC", "AEENDTC"],
    #   "message": "AE end date is before start date",
    #   "evidence": {"start_date": "...", "end_date": "..."}
    # }

    return IssueCreate(
        source=IssueSource.EDIT_CHECK,
        domain=IssueDomain(payload.get("domain", "AE")),
        subject_id=str(payload.get("subject_id", "")),
        fields=list(payload.get("fields", [])),
        description=str(payload.get("message", "")),
        evidence_payload=dict(payload.get("evidence", {})),
    )


def from_sas_listing(payload: dict[str, Any]) -> IssueCreate:
    """
    Normalize a mock "SAS QC listing" payload into IssueCreate.

    Listing tools often provide:
    - a free-text description
    - a few row-level values (the evidence)
    """

    # Example expected payload shape (mock):
    # {
    #   "listing_name": "LB_OUTLIERS",
    #   "domain": "LB",
    #   "subject": "SUBJ-001",
    #   "fields": ["LBORRES", "LBSTRESN"],
    #   "finding": "Lab value out of range",
    #   "rows": [{"LBSTRESN": 9999, "visit": "V1"}]
    # }

    return IssueCreate(
        source=IssueSource.LISTING,
        domain=IssueDomain(payload.get("domain", "LB")),
        subject_id=str(payload.get("subject", "")),
        fields=list(payload.get("fields", [])),
        description=str(payload.get("finding", "")),
        evidence_payload={"rows": payload.get("rows", []), "listing_name": payload.get("listing_name")},
    )

