# Debugging: Why Recommendations Look the Same

## Quick Checklist

If recommendations look identical across different settings, check:

1. **Are you looking at the right fields?**
   - `action` and `severity` stay the same (by design - deterministic source of truth)
   - **Look for differences in**: `rationale`, `draft_message`, `citations`, `confidence`
   - Check `tool_results.llm_enhanced` flag

2. **Is LLM actually being called?**
   - Check `OPENAI_API_KEY` is set: `echo $env:OPENAI_API_KEY` (PowerShell)
   - Check `LLM_ENABLED=1` if not explicitly requesting in UI
   - Look for `tool_results.llm_enhanced: true` in the response
   - Look for `tool_results.llm_model` field

3. **Are RAG citations being added?**
   - Check `citations` array (should have document IDs)
   - Check `tool_results.citation_hits` (should have titles/sources)
   - Ensure documents are ingested: `python scripts/ingest_mock_documents.py`

4. **Is the frontend showing the latest run?**
   - After running analyze, check `runResult` state (not `latest_run` summary)
   - Refresh the page - it should fetch full run details automatically

## Using the Diagnostic Script

Run the diagnostic script to compare runs:

```powershell
# Get an issue ID first
$issues = curl "http://127.0.0.1:8000/issues" | ConvertFrom-Json
$issueId = $issues[0].issue_id

# Run diagnostics
python scripts/diagnose_recommendations.py $issueId
```

This will:
- Show what's different between runs
- Check if LLM is enabled
- Check if documents exist
- Compare rationale, draft_message, citations

## Manual Testing

### Test 1: Check LLM is Working

```powershell
# Set environment variables
$env:LLM_ENABLED="1"
$env:OPENAI_API_KEY="sk-..."  # Your key

# Create issue
$issue = curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{"source":"edit_check","domain":"AE","subject_id":"TEST","fields":["AESTDTC"],"description":"AE end date is before start date.","evidence_payload":{}}' | ConvertFrom-Json

# Run WITHOUT LLM
$run1 = curl -X POST "http://127.0.0.1:8000/issues/$($issue.issue_id)/analyze" `
  -H "Content-Type: application/json" `
  -d '{"use_llm": false}' | ConvertFrom-Json

# Run WITH LLM
$run2 = curl -X POST "http://127.0.0.1:8000/issues/$($issue.issue_id)/analyze" `
  -H "Content-Type: application/json" `
  -d '{"use_llm": true}' | ConvertFrom-Json

# Compare
Write-Host "Run 1 LLM Enhanced: $($run1.recommendation.tool_results.llm_enhanced)"
Write-Host "Run 2 LLM Enhanced: $($run2.recommendation.tool_results.llm_enhanced)"
Write-Host "Run 1 Rationale: $($run1.recommendation.rationale)"
Write-Host "Run 2 Rationale: $($run2.recommendation.rationale)"
```

**Expected**:
- Run 1: `llm_enhanced: false`, shorter rationale
- Run 2: `llm_enhanced: true`, enhanced rationale, `llm_model` present

### Test 2: Check RAG Citations

```powershell
# Ensure documents are ingested
python scripts/ingest_mock_documents.py

# Analyze issue
$run = curl -X POST "http://127.0.0.1:8000/issues/$($issue.issue_id)/analyze" | ConvertFrom-Json

# Check citations
$run.recommendation.citations
$run.recommendation.tool_results.citation_hits
$run.recommendation.tool_results.rag_method
```

**Expected**:
- `citations`: Array of document IDs (may be empty if no matches)
- `citation_hits`: Array with `title`, `source`, `score`
- `rag_method`: "keyword" or "semantic"

### Test 3: Check Frontend Display

1. Open browser DevTools (F12)
2. Go to Network tab
3. Run analyze on an issue
4. Check the response:
   - Look for `recommendation.rationale`
   - Look for `recommendation.tool_results.llm_enhanced`
   - Look for `recommendation.citations`

5. In the UI, check:
   - Rationale text (should be different with LLM)
   - Draft message (should be different with LLM)
   - Citations section (should show document titles)
   - RAG/LLM indicators at bottom

## Common Issues

### Issue: LLM not enhancing

**Symptoms**: `llm_enhanced: false` even when `use_llm: true`

**Causes**:
1. `OPENAI_API_KEY` not set
2. API key invalid or expired
3. Network error calling OpenAI
4. LLM returned empty/null values

**Fix**:
- Check API key: `echo $env:OPENAI_API_KEY`
- Check API server logs for errors
- Verify API key has credits
- Try the diagnostic script

### Issue: Citations empty

**Symptoms**: `citations: []` even after ingesting documents

**Causes**:
1. Documents not ingested
2. Query doesn't match documents
3. Domain mismatch

**Fix**:
- Ingest documents: `python scripts/ingest_mock_documents.py`
- Check documents exist: `curl "http://127.0.0.1:8000/documents/search?q=AE"`
- Try semantic RAG: `{"use_semantic_rag": true}`

### Issue: Frontend shows empty rationale

**Symptoms**: Rationale is empty or same as before

**Causes**:
1. Frontend showing `latest_run` summary (no rationale)
2. Not fetching full run details
3. State not updating

**Fix**:
- Refresh the page (should auto-fetch full run)
- Check browser console for errors
- Verify API endpoint `/issues/{id}/runs/{run_id}` works

## What Should Change

### With LLM Enhancement:
- ✅ `rationale` - More detailed, context-aware
- ✅ `draft_message` - Improved query text
- ✅ `confidence` - May be adjusted
- ✅ `tool_results.llm_enhanced` - Set to `true`
- ✅ `tool_results.llm_model` - Model version
- ❌ `action` - Stays same (deterministic)
- ❌ `severity` - Stays same (deterministic)

### With RAG:
- ✅ `citations` - Document IDs added
- ✅ `tool_results.citation_hits` - Document metadata
- ✅ `tool_results.rag_method` - "keyword" or "semantic"
- ❌ `action` - Stays same
- ❌ `severity` - Stays same
- ❌ `rationale` - Stays same (unless LLM also used)

### With Semantic RAG:
- ✅ `tool_results.rag_method` - "semantic"
- ✅ `citation_hits[].score` - Similarity scores (0.0-1.0)
- ✅ Better document matches (usually)

## Summary

**Key Point**: `action` and `severity` are **intentionally** the same - they come from deterministic rules (source of truth). LLM and RAG enhance other fields:
- **LLM**: Enhances `rationale`, `draft_message`, `confidence`
- **RAG**: Adds `citations` and document metadata

If you're not seeing differences, check:
1. LLM is actually being called (`llm_enhanced: true`)
2. RAG citations are present (`citations` array)
3. You're comparing `rationale` and `draft_message`, not just `action`/`severity`
4. Frontend is showing the full run, not just the summary
