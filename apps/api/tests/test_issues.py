from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.main import app


def test_create_issue_then_get_by_id_returns_it() -> None:
    """POST /issues then GET /issues/{id} should return the created issue."""
    client = TestClient(app)

    payload = {
        "source": "manual",
        "domain": "DM",
        "subject_id": "SUBJ-123",
        "fields": ["title", "description"],
        "description": "Something looks off.",
        "evidence_payload": {"note": "example evidence"},
    }

    # Create
    create_res = client.post("/issues", json=payload)
    assert create_res.status_code == 200
    created = create_res.json()
    assert "issue_id" in created

    # Fetch by ID
    get_res = client.get(f"/issues/{created['issue_id']}")
    assert get_res.status_code == 200
    fetched = get_res.json()

    assert fetched["issue_id"] == created["issue_id"]
    assert fetched["subject_id"] == payload["subject_id"]
    assert fetched["source"] == payload["source"]
    assert fetched["domain"] == payload["domain"]


def test_list_issues_includes_created_issues() -> None:
    """GET /issues should return a list including created issues."""
    client = TestClient(app)

    payload1 = {
        "source": "manual",
        "domain": "DM",
        "subject_id": "SUBJ-1",
        "fields": ["field_a"],
        "description": "First issue.",
        "evidence_payload": {"k": 1},
    }
    payload2 = {
        "source": "listing",
        "domain": "VS",
        "subject_id": "SUBJ-2",
        "fields": ["field_b"],
        "description": "Second issue.",
        "evidence_payload": {"k": 2},
    }

    # Create two issues
    res1 = client.post("/issues", json=payload1)
    res2 = client.post("/issues", json=payload2)
    assert res1.status_code == 200
    assert res2.status_code == 200

    created_ids = {res1.json()["issue_id"], res2.json()["issue_id"]}

    # List all issues and ensure our created ones are present
    list_res = client.get("/issues")
    assert list_res.status_code == 200
    issues = list_res.json()

    assert isinstance(issues, list)
    returned_ids = {item["issue_id"] for item in issues}
    assert created_ids.issubset(returned_ids)


def test_get_unknown_issue_returns_404() -> None:
    """GET /issues/{random_uuid} should return 404 when not found."""
    client = TestClient(app)

    missing_id = uuid4()
    res = client.get(f"/issues/{missing_id}")

    assert res.status_code == 404
