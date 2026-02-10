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


# Columns that map directly to IssueCreate (case-insensitive key).
_ISSUE_KEYS = {"source", "domain", "subject_id", "fields", "description"}
# Columns that go into evidence_payload (optional); any other column also goes there.
_EVIDENCE_KEYS = {
    "start_date",
    "end_date",
    "variable",
    "value",
    "reference",
    "notes",
}


def _normalize_key(k: str) -> str:
    """Normalize Excel column to lowercase with underscores."""
    return k.strip().lower().replace(" ", "_")


def from_excel_row(row: dict[str, Any]) -> IssueCreate:
    """
    Normalize a single Excel row (e.g. from RAVE/QC export) into IssueCreate.

    Expected columns (case-insensitive): Source, Domain, Subject_ID, Fields,
    Description. Optional: Start_Date, End_Date, Variable, Value, Reference, Notes
    (and any other columns) are merged into evidence_payload.

    - Source must be edit_check or listing; default edit_check.
    - Fields can be comma-separated string or list.
    """
    normalized = {_normalize_key(k): v for k, v in row.items() if v is not None and v != ""}
    # Build evidence from optional + any extra columns
    evidence: dict[str, Any] = {}
    for k, v in normalized.items():
        if k in _ISSUE_KEYS:
            continue
        if k in _EVIDENCE_KEYS or k not in _ISSUE_KEYS:
            evidence[k] = v

    source_raw = str(normalized.get("source", "edit_check")).strip().lower()
    source = (
        IssueSource.EDIT_CHECK
        if source_raw == "edit_check"
        else IssueSource.LISTING
        if source_raw == "listing"
        else IssueSource.EDIT_CHECK
    )
    domain = IssueDomain(str(normalized.get("domain", "AE")).strip().upper())
    subject_id = str(normalized.get("subject_id", "")).strip()
    fields_raw = normalized.get("fields", [])
    if isinstance(fields_raw, str):
        fields = [f.strip() for f in fields_raw.split(",") if f.strip()]
    else:
        fields = [str(f).strip() for f in fields_raw if f]
    description = str(normalized.get("description", "")).strip()
    if not description:
        description = "No description"
    return IssueCreate(
        source=source,
        domain=domain,
        subject_id=subject_id,
        fields=fields,
        description=description,
        evidence_payload=evidence,
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
        evidence_payload={
            "rows": payload.get("rows", []),
            "listing_name": payload.get("listing_name"),
        },
    )
