"""
Workflow-level API tests.

These tests exercise the "canonical workflow":
- create issue
- analyze -> run created + issue status updated + audit event
- list runs history
- create decision tied to run_id (approve/override/edit)
- audit and eval exports

We use FastAPI TestClient to run the app in-memory (no real server process needed).
"""

from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.main import app


def _create_issue(client: TestClient, *, description: str, evidence_payload: dict) -> dict:
    """
    Helper to create an issue via API and return the JSON response.

    Keeping this as a helper reduces repetition across tests.
    """

    payload = {
        "source": "manual",
        "domain": "AE",
        "subject_id": "SUBJ-100",
        "fields": ["AESTDTC", "AEENDTC"],
        "description": description,
        "evidence_payload": evidence_payload,
    }
    res = client.post("/issues", json=payload)
    assert res.status_code == 200
    return res.json()


def test_analyze_existing_issue_creates_run_and_triages_issue() -> None:
    client = TestClient(app)

    # Create an issue that should trigger AE date inconsistency.
    issue = _create_issue(
        client,
        description="AE end date is before start date.",
        evidence_payload={"start_date": "2024-01-10", "end_date": "2024-01-01"},
    )
    issue_id = issue["issue_id"]

    # Analyze it
    res = client.post(f"/issues/{issue_id}/analyze")
    assert res.status_code == 200
    assert "X-Correlation-ID" in res.headers
    run = res.json()

    # Run contains recommendation info
    assert run["issue_id"] == issue_id
    assert run["rules_version"] == "v0.1"
    assert run["recommendation"]["action"] in {"QUERY_SITE", "DATA_FIX", "MEDICAL_REVIEW", "IGNORE"}
    assert run["recommendation"]["severity"] in {"LOW", "MEDIUM", "HIGH"}
    assert 0.0 <= run["recommendation"]["confidence"] <= 1.0
    assert run["recommendation"]["tool_results"]["rule_fired"] == "AE_DATE_INCONSISTENCY"

    # Issue status becomes triaged
    issue_res = client.get(f"/issues/{issue_id}")
    assert issue_res.status_code == 200
    assert issue_res.json()["status"] == "triaged"


def test_analyze_missing_issue_returns_404() -> None:
    client = TestClient(app)

    res = client.post(f"/issues/{uuid4()}/analyze")
    assert res.status_code == 404


def test_runs_history_returns_summaries() -> None:
    client = TestClient(app)

    issue = _create_issue(
        client,
        description="AE end before start.",
        evidence_payload={"start_date": "2024-02-10", "end_date": "2024-02-01"},
    )
    issue_id = issue["issue_id"]

    # Create two runs
    assert client.post(f"/issues/{issue_id}/analyze").status_code == 200
    assert client.post(f"/issues/{issue_id}/analyze").status_code == 200

    # History should contain summaries (not full payload)
    res = client.get(f"/issues/{issue_id}/runs")
    assert res.status_code == 200
    summaries = res.json()
    assert isinstance(summaries, list)
    assert len(summaries) == 2
    assert {"run_id", "created_at", "severity", "action", "confidence"} <= set(summaries[0].keys())


def test_post_decision_approve_is_stored_and_status_updated() -> None:
    client = TestClient(app)

    issue = _create_issue(
        client,
        description="Duplicate record suspected.",
        evidence_payload={"note": "duplicate"},
    )
    issue_id = issue["issue_id"]

    run_res = client.post(f"/issues/{issue_id}/analyze")
    assert run_res.status_code == 200
    run = run_res.json()

    # Approve decision for this run
    decision_payload = {
        "run_id": run["run_id"],
        "decision_type": "APPROVE",
        "final_action": "DATA_FIX",
        "final_text": "Proceed with de-duplication according to spec.",
        "reviewer": "jdoe",
        "reason": None,
    }
    dec_res = client.post(f"/issues/{issue_id}/decisions", json=decision_payload)
    assert dec_res.status_code == 200
    assert "X-Correlation-ID" in dec_res.headers
    decision = dec_res.json()
    assert decision["issue_id"] == issue_id
    assert decision["run_id"] == run["run_id"]
    assert decision["decision_type"] == "APPROVE"

    # Status rule: not IGNORE -> triaged
    issue_res = client.get(f"/issues/{issue_id}")
    assert issue_res.status_code == 200
    assert issue_res.json()["status"] == "triaged"


def test_post_decision_override_without_reason_fails_validation_422() -> None:
    client = TestClient(app)

    issue = _create_issue(
        client,
        description="Missing critical field.",
        evidence_payload={"field_x": None},
    )
    issue_id = issue["issue_id"]

    run_res = client.post(f"/issues/{issue_id}/analyze")
    assert run_res.status_code == 200
    run = run_res.json()

    # OVERRIDE without reason should fail (Pydantic validation -> 422)
    decision_payload = {
        "run_id": run["run_id"],
        "decision_type": "OVERRIDE",
        "final_action": "IGNORE",
        "final_text": "Acceptable; do not query.",
        "reviewer": "jdoe",
        # reason intentionally missing
    }
    dec_res = client.post(f"/issues/{issue_id}/decisions", json=decision_payload)
    assert dec_res.status_code == 422


def test_audit_endpoint_returns_events_after_analyze_and_decision() -> None:
    client = TestClient(app)

    issue = _create_issue(
        client,
        description="AE end before start.",
        evidence_payload={"start_date": "2024-03-10", "end_date": "2024-03-01"},
    )
    issue_id = issue["issue_id"]

    run = client.post(f"/issues/{issue_id}/analyze").json()

    decision_payload = {
        "run_id": run["run_id"],
        "decision_type": "APPROVE",
        "final_action": "QUERY_SITE",
        "final_text": "Send site query.",
        "reviewer": "reviewer1",
        "reason": None,
    }
    assert client.post(f"/issues/{issue_id}/decisions", json=decision_payload).status_code == 200

    # Audit should include events for this issue
    audit_res = client.get(f"/audit?issue_id={issue_id}")
    assert audit_res.status_code == 200
    assert "X-Correlation-ID" in audit_res.headers
    events = audit_res.json()
    assert isinstance(events, list)
    assert any(e["event_type"] == "ANALYZE_RUN_CREATED" for e in events)
    assert any(e["event_type"] == "DECISION_RECORDED" for e in events)
    # Correlation ID should be present on events created via API requests.
    assert any(e.get("correlation_id") for e in events)

    # Audit filtered by run_id should find the analyze/decision events
    audit_run_res = client.get(f"/audit?run_id={run['run_id']}")
    assert audit_run_res.status_code == 200
    run_events = audit_run_res.json()
    assert all(e.get("run_id") == run["run_id"] for e in run_events if e.get("run_id") is not None)


def test_eval_scorecard_returns_rows_including_rule_fired() -> None:
    client = TestClient(app)

    issue = _create_issue(
        client,
        description="AE end before start.",
        evidence_payload={"start_date": "2024-04-10", "end_date": "2024-04-01"},
    )
    issue_id = issue["issue_id"]

    run_res = client.post(f"/issues/{issue_id}/analyze")
    assert run_res.status_code == 200

    score_res = client.get("/eval/scorecard")
    assert score_res.status_code == 200
    rows = score_res.json()

    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert {"issue_id", "run_id", "created_at", "severity", "action", "confidence", "rule_fired"} <= set(rows[0].keys())
    assert any(r["issue_id"] == issue_id and r["rule_fired"] for r in rows)

