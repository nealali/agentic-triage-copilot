# Workflow Fixes - Status and Recommendation Changes

**See also**: [DEBUGGING_RECOMMENDATIONS.md](DEBUGGING_RECOMMENDATIONS.md) for detailed troubleshooting guide.

## Issues Fixed

### 1. Issue Status Only Changes When Decision is Recorded ✅

**Problem**: Issue status was being set to `triaged` immediately after running analyze, even without recording a decision.

**Fix**: Removed status update from `/issues/{issue_id}/analyze` endpoint. Status now only changes when a decision is recorded via `/issues/{issue_id}/decisions`.

**Workflow**:
- `OPEN` → Issue created
- `OPEN` → After running analyze (status remains open)
- `TRIAGED` → After recording a decision (approve/override)
- `CLOSED` → After recording a decision with `IGNORE` action

### 2. Understanding Recommendation Changes with RAG/LLM

**Important Notes**:

#### RAG (Document Retrieval)
- **Always runs** for all issues (deterministic and LLM-required)
- Adds `citations` (document IDs) to recommendations
- Adds `citation_hits` metadata (title, source, score)
- Sets `rag_method` to "keyword" (default) or "semantic" (if enabled)
- **What changes**: Citations are added to the recommendation
- **What stays the same**: Action, severity, confidence (from deterministic analysis)

#### LLM Enhancement
- **Only runs** if:
  - Explicitly requested: `{"use_llm": true}` in request body, OR
  - Globally enabled: `LLM_ENABLED=1` environment variable, OR
  - Issue is classified as `llm_required` (automatic)
- **What changes**:
  - `rationale` - Enhanced with more context-aware explanation
  - `draft_message` - Improved query/message text (if action is QUERY_SITE)
  - `confidence` - May be adjusted based on LLM analysis
  - `tool_results.llm_enhanced` - Set to `true`
  - `tool_results.llm_model` - Model version used
- **What stays the same**: Action and severity (deterministic source of truth)

## Testing the Changes

### Test 1: Status Remains OPEN After Analyze

```powershell
# Create issue
$issue = curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{"source":"edit_check","domain":"AE","subject_id":"SUBJ-001","fields":["AESTDTC"],"description":"AE end date is before start date.","evidence_payload":{}}' | ConvertFrom-Json

# Check initial status (should be "open")
curl "http://127.0.0.1:8000/issues/$($issue.issue_id)" | ConvertFrom-Json | Select-Object status

# Run analyze
curl -X POST "http://127.0.0.1:8000/issues/$($issue.issue_id)/analyze"

# Check status again (should still be "open")
curl "http://127.0.0.1:8000/issues/$($issue.issue_id)" | ConvertFrom-Json | Select-Object status

# Record a decision
$run = curl -X POST "http://127.0.0.1:8000/issues/$($issue.issue_id)/analyze" | ConvertFrom-Json
curl -X POST "http://127.0.0.1:8000/issues/$($issue.issue_id)/decisions" `
  -H "Content-Type: application/json" `
  -d "{\"run_id\":\"$($run.run_id)\",\"decision_type\":\"APPROVE\",\"final_action\":\"QUERY_SITE\",\"final_text\":\"Send query\",\"reviewer\":\"tester\"}"

# Check status (should now be "triaged")
curl "http://127.0.0.1:8000/issues/$($issue.issue_id)" | ConvertFrom-Json | Select-Object status
```

### Test 2: See RAG Citations

```powershell
# Ensure documents are ingested
python scripts/ingest_mock_documents.py

# Create and analyze issue
$issue = curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{"source":"edit_check","domain":"AE","subject_id":"SUBJ-002","fields":["AESTDTC","AEENDTC"],"description":"AE end date is before start date.","evidence_payload":{}}' | ConvertFrom-Json

$run = curl -X POST "http://127.0.0.1:8000/issues/$($issue.issue_id)/analyze" | ConvertFrom-Json

# Check for citations
$run.recommendation.citations
$run.recommendation.tool_results.citation_hits
$run.recommendation.tool_results.rag_method
```

### Test 3: See LLM Enhancement Differences

```powershell
# Set environment variable
$env:LLM_ENABLED="1"
$env:OPENAI_API_KEY="sk-..."  # Your API key

# Analyze WITHOUT LLM (explicitly disable)
$run1 = curl -X POST "http://127.0.0.1:8000/issues/$($issue.issue_id)/analyze" `
  -H "Content-Type: application/json" `
  -d '{"use_llm": false}' | ConvertFrom-Json

# Analyze WITH LLM (explicitly enable)
$run2 = curl -X POST "http://127.0.0.1:8000/issues/$($issue.issue_id)/analyze" `
  -H "Content-Type: application/json" `
  -d '{"use_llm": true}' | ConvertFrom-Json

# Compare:
# - $run1.recommendation.tool_results.llm_enhanced (should be false)
# - $run2.recommendation.tool_results.llm_enhanced (should be true)
# - $run1.recommendation.rationale vs $run2.recommendation.rationale (should differ)
# - $run1.recommendation.draft_message vs $run2.recommendation.draft_message (should differ)
# - Action and severity should be the same in both
```

## Key Points

1. **Status Workflow**: 
   - Analyze → Status stays `OPEN`
   - Record Decision → Status changes to `TRIAGED` (or `CLOSED` if IGNORE)

2. **RAG Always Runs**:
   - Citations are always added (may be empty if no documents match)
   - Check `citations` and `citation_hits` fields

3. **LLM Enhancement**:
   - Must be explicitly enabled (request body or env var)
   - Changes: rationale, draft_message, confidence
   - Stays same: action, severity (deterministic source of truth)

4. **For Deterministic Issues**:
   - RAG citations should be visible
   - LLM enhancement only if explicitly enabled
   - Action/severity remain from deterministic rules (by design)

## UI Changes Needed

The frontend should:
- Show that status remains `OPEN` after analyze
- Display citations from RAG
- Show `rag_method` (keyword vs semantic)
- Show `llm_enhanced` flag and `llm_model` when LLM is used
- Highlight differences in rationale and draft_message when LLM is enabled
