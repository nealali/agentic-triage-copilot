<#
.SYNOPSIS
  Runs a realistic end-to-end demo flow against the local API.

.DESCRIPTION
  This script exercises the core workflow:
    1) POST /issues
    2) POST /issues/{id}/analyze
    3) POST /issues/{id}/decisions
    4) GET /audit
    5) GET /eval/scorecard

  Why this matters:
  - Hiring managers love "one command demo" repos.
  - It proves the system behaves end-to-end, not just in unit tests.

  Assumptions:
  - You have the API running locally (recommended command below).
  - curl is available (Windows 10+ includes it).

  Start the API in another terminal:
    uvicorn apps.api.main:app --reload
#>

$ErrorActionPreference = "Stop"

$BaseUrl = "http://127.0.0.1:8000"

Write-Host "=== Agentic Triage Copilot demo flow ===" -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl"

# Quick health check so we fail fast with a friendly message.
Write-Host "`n[1/5] Checking /health..." -ForegroundColor Cyan
try {
  $health = curl "$BaseUrl/health" | ConvertFrom-Json
} catch {
  throw "API is not reachable at $BaseUrl. Start it with: uvicorn apps.api.main:app --reload"
}
Write-Host "Health: $($health.status)"

# 1) Create an issue
Write-Host "`n[2/5] Creating an issue (POST /issues)..." -ForegroundColor Cyan
$issuePayload = @{
  source = "manual"
  domain = "AE"
  subject_id = "SUBJ-DEMO-001"
  fields = @("AESTDTC", "AEENDTC")
  description = "AE end date appears to be before start date."
  evidence_payload = @{
    start_date = "2024-01-10"
    end_date   = "2024-01-01"
  }
} | ConvertTo-Json -Depth 10

$issue = curl -X POST "$BaseUrl/issues" -H "Content-Type: application/json" -d $issuePayload | ConvertFrom-Json
$issueId = $issue.issue_id
Write-Host "Created issue_id: $issueId"

# 2) Analyze the issue
Write-Host "`n[3/5] Analyzing issue (POST /issues/$issueId/analyze)..." -ForegroundColor Cyan
$run = curl -X POST "$BaseUrl/issues/$issueId/analyze" | ConvertFrom-Json
$runId = $run.run_id
Write-Host "Created run_id: $runId"
Write-Host "Rule fired: $($run.recommendation.tool_results.rule_fired)"
Write-Host "Action: $($run.recommendation.action) | Severity: $($run.recommendation.severity) | Confidence: $($run.recommendation.confidence)"

# 3) Record a human decision tied to the run
Write-Host "`n[4/5] Recording decision (POST /issues/$issueId/decisions)..." -ForegroundColor Cyan
$decisionPayload = @{
  run_id = $runId
  decision_type = "APPROVE"
  final_action = "QUERY_SITE"
  final_text = "Please confirm AE start/end dates and correct if needed."
  reviewer = "demo_user"
} | ConvertTo-Json -Depth 10

$decision = curl -X POST "$BaseUrl/issues/$issueId/decisions" -H "Content-Type: application/json" -d $decisionPayload | ConvertFrom-Json
Write-Host "Decision recorded. decision_id: $($decision.decision_id)"

# 4) Audit query
Write-Host "`n[5/5] Fetching audit events (GET /audit?issue_id=...)..." -ForegroundColor Cyan
$audit = curl "$BaseUrl/audit?issue_id=$issueId" | ConvertFrom-Json
Write-Host "Audit events found: $($audit.Count)"
$audit | Select-Object event_type, actor, created_at, issue_id, run_id | Format-Table -AutoSize

# 5) Scorecard export
Write-Host "`n[extra] Fetching scorecard rows (GET /eval/scorecard)..." -ForegroundColor Cyan
$scorecard = curl "$BaseUrl/eval/scorecard" | ConvertFrom-Json
Write-Host "Scorecard rows: $($scorecard.Count)"
$scorecard | Select-Object issue_id, run_id, severity, action, confidence, rule_fired | Format-Table -AutoSize

Write-Host "`nDemo flow complete." -ForegroundColor Green

