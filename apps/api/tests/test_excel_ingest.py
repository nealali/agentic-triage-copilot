"""
Tests for Excel row normalizer (from_excel_row) and ingest behavior.

Validates mapping from Excel column dict to IssueCreate and evidence_payload.
"""

from __future__ import annotations

from agent.ingest.normalizers import from_excel_row
from agent.schemas.issue import IssueDomain, IssueSource


def test_from_excel_row_ae_date_issue() -> None:
    row = {
        "Source": "edit_check",
        "Domain": "AE",
        "Subject_ID": "SUBJ-1001",
        "Fields": "AESTDTC, AEENDTC",
        "Description": "AE end date is before start date.",
        "Start_Date": "2024-01-15",
        "End_Date": "2024-01-10",
        "Reference": "AE_DATE_001",
        "Notes": "RAVE edit check",
    }
    out = from_excel_row(row)
    assert out.source == IssueSource.EDIT_CHECK
    assert out.domain == IssueDomain.AE
    assert out.subject_id == "SUBJ-1001"
    assert out.fields == ["AESTDTC", "AEENDTC"]
    assert "start_date" in out.evidence_payload
    assert out.evidence_payload["start_date"] == "2024-01-15"
    assert out.evidence_payload["end_date"] == "2024-01-10"
    assert out.evidence_payload["reference"] == "AE_DATE_001"


def test_from_excel_row_listing_lab_out_of_range() -> None:
    row = {
        "source": "listing",
        "domain": "LB",
        "subject_id": "SUBJ-1003",
        "fields": "LBORRES, LBSTRESN",
        "description": "Lab value out of range: hemoglobin.",
        "variable": "LBORRES",
        "value": "4.2",
        "reference": "Normal 12-17 g/dL",
    }
    out = from_excel_row(row)
    assert out.source == IssueSource.LISTING
    assert out.domain == IssueDomain.LB
    assert out.evidence_payload["variable"] == "LBORRES"
    assert out.evidence_payload["value"] == "4.2"


def test_from_excel_row_default_source_and_description() -> None:
    row = {
        "Domain": "AE",
        "Subject_ID": "SUBJ-X",
        "Fields": "AETERM",
        "Description": "",
    }
    out = from_excel_row(row)
    assert out.source == IssueSource.EDIT_CHECK
    assert out.description == "No description"


def test_ingest_api_accepts_excel_and_creates_issues() -> None:
    from pathlib import Path

    from fastapi.testclient import TestClient

    from apps.api.main import app

    seed_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "seed" / "rave_export_demo.xlsx"
    if not seed_path.is_file():
        return  # skip if seed not generated
    client = TestClient(app)
    with open(seed_path, "rb") as f:
        content = f.read()
    r = client.post(
        "/ingest/issues",
        files={"file": ("rave_export_demo.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] >= 1
    assert len(data["issue_ids"]) == data["created"]
    # GET /issues should include the created ids
    list_r = client.get("/issues")
    assert list_r.status_code == 200
    ids = {i["issue_id"] for i in list_r.json()}
    for iid in data["issue_ids"]:
        assert iid in ids
