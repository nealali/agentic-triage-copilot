"""
Document (RAG-lite) API tests.

These tests validate that:
- documents can be ingested
- documents can be searched
- analyze can attach citation IDs when guidance exists
"""

from fastapi.testclient import TestClient

from apps.api.main import app


def test_ingest_get_and_search_documents() -> None:
    client = TestClient(app)

    doc_payload = {
        "title": "AE Date Consistency Guidance",
        "source": "SOP",
        "tags": ["AE", "queries"],
        "content": (
            "If AE end date is before AE start date, treat as an AE date inconsistency. "
            "Query site to confirm correct dates and update EDC as needed."
        ),
    }
    create_res = client.post("/documents", json=doc_payload)
    assert create_res.status_code == 200
    created = create_res.json()
    assert "doc_id" in created

    doc_id = created["doc_id"]

    get_res = client.get(f"/documents/{doc_id}")
    assert get_res.status_code == 200
    fetched = get_res.json()
    assert fetched["doc_id"] == doc_id
    assert fetched["title"] == doc_payload["title"]

    search_res = client.get("/documents/search", params={"q": "AE end date inconsistency"})
    assert search_res.status_code == 200
    hits = search_res.json()
    assert any(h["doc_id"] == doc_id for h in hits)


def test_analyze_includes_citations_when_guidance_exists() -> None:
    client = TestClient(app)

    doc_res = client.post(
        "/documents",
        json={
            "title": "AE Date Checks Guidance",
            "source": "DRP",
            "tags": ["AE"],
            "content": "AE date start end inconsistency: query site for confirmation.",
        },
    )
    assert doc_res.status_code == 200
    doc_id = doc_res.json()["doc_id"]

    issue_res = client.post(
        "/issues",
        json={
            "source": "manual",
            "domain": "AE",
            "subject_id": "SUBJ-100",
            "fields": ["AESTDTC", "AEENDTC"],
            "description": "AE end date is before start date.",
            "evidence_payload": {"start_date": "2024-01-10", "end_date": "2024-01-01"},
        },
    )
    assert issue_res.status_code == 200
    issue_id = issue_res.json()["issue_id"]

    run_res = client.post(f"/issues/{issue_id}/analyze")
    assert run_res.status_code == 200
    run = run_res.json()

    citations = run["recommendation"]["citations"]
    assert isinstance(citations, list)
    assert doc_id in citations
