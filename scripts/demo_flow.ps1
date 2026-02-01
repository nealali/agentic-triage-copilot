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

function Invoke-ApiJson {
  <#
  .SYNOPSIS
    Call the API and parse JSON response.

  .DESCRIPTION
    We use Invoke-WebRequest (PowerShell-native) because it:
    - sends JSON reliably (no quoting/escaping issues)
    - lets us read response headers (like X-Correlation-ID)
    - returns friendly errors when something fails
  #>

  param(
    [Parameter(Mandatory = $true)][ValidateSet("GET", "POST")][string]$Method,
    [Parameter(Mandatory = $true)][string]$Url,
    [Parameter(Mandatory = $false)][object]$BodyObject
  )

  $headers = @{ Accept = "application/json" }

  if ($null -ne $BodyObject) {
    $jsonBody = $BodyObject | ConvertTo-Json -Depth 10
    $resp = Invoke-WebRequest -Method $Method -Uri $Url -Headers $headers -ContentType "application/json" -Body $jsonBody
  } else {
    $resp = Invoke-WebRequest -Method $Method -Uri $Url -Headers $headers
  }

  $correlationId = $resp.Headers["X-Correlation-ID"]
  $data = $resp.Content | ConvertFrom-Json

  return [pscustomobject]@{
    StatusCode    = $resp.StatusCode
    CorrelationId = $correlationId
    Data          = $data
  }
}

# Quick health check so we fail fast with a friendly message.
Write-Host "`n[1/5] Checking /health..." -ForegroundColor Cyan
try {
  $healthResp = Invoke-ApiJson -Method "GET" -Url "$BaseUrl/health"
} catch {
  throw "API is not reachable at $BaseUrl. Start it with: uvicorn apps.api.main:app --reload"
}
Write-Host "Health: $($healthResp.Data.status) (X-Correlation-ID: $($healthResp.CorrelationId))"

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
}

$issueResp = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/issues" -BodyObject $issuePayload
$issueId = $issueResp.Data.issue_id
Write-Host "Created issue_id: $issueId (X-Correlation-ID: $($issueResp.CorrelationId))"

# 2) Analyze the issue
Write-Host "`n[3/5] Analyzing issue (POST /issues/$issueId/analyze)..." -ForegroundColor Cyan
$runResp = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/issues/$issueId/analyze"
$runId = $runResp.Data.run_id
Write-Host "Created run_id: $runId (X-Correlation-ID: $($runResp.CorrelationId))"
Write-Host "Rule fired: $($runResp.Data.recommendation.tool_results.rule_fired)"
Write-Host ("Recommendation: action={0} severity={1} confidence={2}" -f `
  $runResp.Data.recommendation.action, `
  $runResp.Data.recommendation.severity, `
  $runResp.Data.recommendation.confidence)

# 3) Record a human decision tied to the run
Write-Host "`n[4/5] Recording decision (POST /issues/$issueId/decisions)..." -ForegroundColor Cyan
$decisionPayload = @{
  run_id = $runId
  decision_type = "APPROVE"
  final_action = "QUERY_SITE"
  final_text = "Please confirm AE start/end dates and correct if needed."
  reviewer = "demo_user"
}

$decisionResp = Invoke-ApiJson -Method "POST" -Url "$BaseUrl/issues/$issueId/decisions" -BodyObject $decisionPayload
Write-Host "Decision recorded. decision_id: $($decisionResp.Data.decision_id) (X-Correlation-ID: $($decisionResp.CorrelationId))"

# 4) Audit query
Write-Host "`n[5/5] Fetching audit events (GET /audit?issue_id=...)..." -ForegroundColor Cyan
$auditResp = Invoke-ApiJson -Method "GET" -Url "$BaseUrl/audit?issue_id=$issueId"
$audit = $auditResp.Data
Write-Host "Audit events found: $($audit.Count) (X-Correlation-ID: $($auditResp.CorrelationId))"
$audit | Select-Object event_type, actor, created_at, issue_id, run_id, correlation_id | Format-Table -AutoSize

# 5) Scorecard export
Write-Host "`n[extra] Fetching scorecard rows (GET /eval/scorecard)..." -ForegroundColor Cyan
$scoreResp = Invoke-ApiJson -Method "GET" -Url "$BaseUrl/eval/scorecard"
$scorecard = $scoreResp.Data
Write-Host "Scorecard rows: $($scorecard.Count) (X-Correlation-ID: $($scoreResp.CorrelationId))"

# Show only rows related to our demo issue first (clearer output).
$scorecardForIssue = $scorecard | Where-Object { $_.issue_id -eq $issueId }
Write-Host ("Scorecard rows for issue_id={0}: {1}" -f $issueId, $scorecardForIssue.Count)
$scorecardForIssue | Select-Object issue_id, run_id, severity, action, confidence, rule_fired | Format-Table -AutoSize

Write-Host "`nFull scorecard (first 10 rows):"
$scorecard | Select-Object -First 10 issue_id, run_id, severity, action, confidence, rule_fired | Format-Table -AutoSize

Write-Host "`nDemo flow complete." -ForegroundColor Green

