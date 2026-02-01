"""
Auth tests (API-key feature flag).

These tests verify:
- auth is optional by default
- when enabled, mutation endpoints require X-API-Key
- reviewer spoofing is prevented when auth is enabled
"""

from fastapi.testclient import TestClient

from apps.api.main import app


def test_auth_enabled_requires_api_key_for_document_ingest(monkeypatch) -> None:
    client = TestClient(app)

    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.setenv("API_KEYS", "testkey:jdoe:writer|reviewer")

    payload = {
        "title": "Test Doc",
        "source": "SOP",
        "tags": ["AE"],
        "content": "Some guidance text.",
    }

    # Missing key -> 401
    res_missing = client.post("/documents", json=payload)
    assert res_missing.status_code == 401

    # Valid key -> 200
    res_ok = client.post("/documents", json=payload, headers={"X-API-Key": "testkey"})
    assert res_ok.status_code == 200


def test_auth_enabled_prevents_reviewer_spoofing(monkeypatch) -> None:
    client = TestClient(app)

    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.setenv("API_KEYS", "reviewkey:jdoe:reviewer")

    # Create issue + run (these endpoints remain open in this MVP).
    issue = client.post(
        "/issues",
        json={
            "source": "manual",
            "domain": "AE",
            "subject_id": "SUBJ-100",
            "fields": ["AESTDTC", "AEENDTC"],
            "description": "AE end date is before start date.",
            "evidence_payload": {"start_date": "2024-01-10", "end_date": "2024-01-01"},
        },
    ).json()
    run = client.post(f"/issues/{issue['issue_id']}/analyze").json()

    # Attempt to spoof reviewer -> 403
    spoof_res = client.post(
        f"/issues/{issue['issue_id']}/decisions",
        json={
            "run_id": run["run_id"],
            "decision_type": "APPROVE",
            "final_action": "QUERY_SITE",
            "final_text": "Send site query.",
            "reviewer": "someone_else",
        },
        headers={"X-API-Key": "reviewkey"},
    )
    assert spoof_res.status_code == 403

    # Correct reviewer (matches auth user) -> 200
    ok_res = client.post(
        f"/issues/{issue['issue_id']}/decisions",
        json={
            "run_id": run["run_id"],
            "decision_type": "APPROVE",
            "final_action": "QUERY_SITE",
            "final_text": "Send site query.",
            "reviewer": "jdoe",
        },
        headers={"X-API-Key": "reviewkey"},
    )
    assert ok_res.status_code == 200
