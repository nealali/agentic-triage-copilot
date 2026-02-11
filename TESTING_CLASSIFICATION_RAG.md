# Testing Guide: Classification, RAG, and LLM Features

This guide covers how to test the recently implemented features:
- **Automatic issue classification** (deterministic vs LLM-required)
- **RAG** (keyword and semantic search)
- **LLM enhancement** (recommendation enhancement)
- **LLM fallback** (for uncertain classifications)

## Table of Contents
1. [Quick Start](#quick-start)
2. [Testing Classification](#testing-classification)
3. [Testing RAG](#testing-rag)
4. [Testing LLM Enhancement](#testing-llm-enhancement)
5. [End-to-End Workflow](#end-to-end-workflow)
6. [Using the UI](#using-the-ui)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites
1. **Start the API server**:
   ```powershell
   cd c:\dev\agentic-triage-copilot
   python -m uvicorn apps.api.main:app --reload --port 8000
   ```

2. **Set up environment variables** (optional, for LLM features):
   ```powershell
   $env:LLM_ENABLED="1"
   $env:OPENAI_API_KEY="sk-..."  # Your OpenAI API key
   $env:RAG_SEMANTIC="1"  # Enable semantic RAG
   $env:CLASSIFIER_USE_LLM_FALLBACK="1"  # Enable LLM fallback for uncertain classifications
   ```

3. **Ingest mock documents** (for RAG testing):
   ```powershell
   python scripts/ingest_mock_documents.py
   ```

---

## Testing Classification

### Test 1: Rule-Based Classification (Deterministic)

**Test deterministic issues** - these should be classified as `deterministic`:

```powershell
# Test 1a: Simple date inconsistency (should be deterministic)
curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{
    "source": "edit_check",
    "domain": "AE",
    "subject_id": "SUBJ-TEST-001",
    "fields": ["AESTDTC", "AEENDTC"],
    "description": "AE end date is before start date.",
    "evidence_payload": {"start_date": "2024-01-15", "end_date": "2024-01-10"}
  }'

# Check the issue_type in the response - should be "deterministic"
```

```powershell
# Test 1b: Missing field (should be deterministic)
curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{
    "source": "edit_check",
    "domain": "AE",
    "subject_id": "SUBJ-TEST-002",
    "fields": ["AESER"],
    "description": "Missing required field AESER for serious AE.",
    "evidence_payload": {}
  }'
```

```powershell
# Test 1c: Out of range (should be deterministic)
curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{
    "source": "listing",
    "domain": "LB",
    "subject_id": "SUBJ-TEST-003",
    "fields": ["LBORRES"],
    "description": "Lab value out of range: hemoglobin.",
    "evidence_payload": {"value": "4.2", "normal_range": "12-17 g/dL"}
  }'
```

### Test 2: Rule-Based Classification (LLM-Required)

**Test complex issues** - these should be classified as `llm_required`:

```powershell
# Test 2a: Complex AE with multiple conditions
curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{
    "source": "listing",
    "domain": "AE",
    "subject_id": "SUBJ-TEST-004",
    "fields": ["AETERM", "AESEV", "AESER"],
    "description": "Complex adverse event with multiple related conditions. Requires medical review to determine if single or multiple events.",
    "evidence_payload": {"symptoms": ["Headache", "Nausea", "Dizziness"]}
  }'

# Check the issue_type in the response - should be "llm_required"
```

```powershell
# Test 2b: Lab discrepancy with clinical significance
curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{
    "source": "listing",
    "domain": "LB",
    "subject_id": "SUBJ-TEST-005",
    "fields": ["LBORRES", "LBCLSIG"],
    "description": "Discrepancy vs central lab: EDC value differs from external. Clinical significance unclear.",
    "evidence_payload": {"edc_value": "12.5", "central_lab": "11.8"}
  }'
```

```powershell
# Test 2c: Ambiguous timeline
curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{
    "source": "edit_check",
    "domain": "AE",
    "subject_id": "SUBJ-TEST-006",
    "fields": ["AESTDTC", "AEENDTC"],
    "description": "Serious adverse event with ambiguous timeline. Start date conflicts with hospitalization records.",
    "evidence_payload": {"start_date": "2024-05-01", "hospitalization": "2024-05-03"}
  }'
```

### Test 3: LLM Fallback (Uncertain Cases)

**Test cases that trigger LLM fallback** (requires `CLASSIFIER_USE_LLM_FALLBACK=1`):

```powershell
# Test 3a: Ambiguous description (low confidence)
curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{
    "source": "listing",
    "domain": "DM",
    "subject_id": "SUBJ-TEST-007",
    "fields": ["DMWEIGHT"],
    "description": "Some issue with no clear pattern that needs review.",
    "evidence_payload": {}
  }'

# This should trigger LLM fallback if CLASSIFIER_USE_LLM_FALLBACK=1
# Check the issue_type - LLM will classify based on context
```

### Test 4: Excel Ingestion with Classification

**Test classification during Excel upload**:

```powershell
# Upload the seed Excel file (contains mix of deterministic and LLM-required issues)
curl -X POST "http://127.0.0.1:8000/ingest/issues" `
  -F "file=@data/seed/rave_export_demo.xlsx"

# Check the response - all issues should be automatically classified
# Verify by listing issues and checking issue_type field
curl "http://127.0.0.1:8000/issues"
```

---

## Testing RAG

### Test 1: Keyword RAG (Default)

**Test keyword-based document retrieval**:

```powershell
# Step 1: Ensure documents are ingested
python scripts/ingest_mock_documents.py

# Step 2: Create an issue that matches document keywords
curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{
    "source": "edit_check",
    "domain": "AE",
    "subject_id": "SUBJ-RAG-001",
    "fields": ["AESTDTC", "AEENDTC"],
    "description": "AE end date is before start date.",
    "evidence_payload": {}
  }'

# Step 3: Analyze the issue (save the issue_id from step 2)
curl -X POST "http://127.0.0.1:8000/issues/<ISSUE_ID>/analyze"

# Step 4: Check the response
# - recommendation.citations should contain document IDs
# - recommendation.tool_results.rag_method should be "keyword"
# - recommendation.tool_results.citation_hits should have document metadata
```

**Expected RAG behavior**:
- `rag_method: "keyword"` (default)
- `citations`: Array of document IDs
- `citation_hits`: Array with `doc_id`, `title`, `source`, `score`

### Test 2: Semantic RAG

**Test embedding-based document retrieval** (requires `RAG_SEMANTIC=1`):

```powershell
# Step 1: Set environment variable
$env:RAG_SEMANTIC="1"

# Step 2: Restart API server (or it will pick up on next request)

# Step 3: Create and analyze an issue
curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{
    "source": "edit_check",
    "domain": "AE",
    "subject_id": "SUBJ-RAG-002",
    "fields": ["AESTDTC", "AEENDTC"],
    "description": "Adverse event date inconsistency detected.",
    "evidence_payload": {}
  }'

# Step 4: Analyze (save issue_id from step 3)
curl -X POST "http://127.0.0.1:8000/issues/<ISSUE_ID>/analyze"

# Step 5: Check the response
# - recommendation.tool_results.rag_method should be "semantic"
# - citation_hits should have similarity scores (0.0-1.0)
```

**Expected semantic RAG behavior**:
- `rag_method: "semantic"`
- `citation_hits[].score`: Similarity score (higher = more relevant)
- First run downloads embedding model (~90MB)

### Test 3: RAG with Different Domains

**Test RAG retrieval for different issue domains**:

```powershell
# Test AE domain (should retrieve AE-related documents)
curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{"source": "edit_check", "domain": "AE", "subject_id": "SUBJ-001", "fields": ["AESTDTC"], "description": "AE date issue", "evidence_payload": {}}'

# Test LB domain (should retrieve lab-related documents)
curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{"source": "listing", "domain": "LB", "subject_id": "SUBJ-002", "fields": ["LBORRES"], "description": "Lab value out of range", "evidence_payload": {}}'

# Analyze both and compare citation_hits
```

---

## Testing LLM Enhancement

### Test 1: LLM Enhancement (Basic)

**Test LLM-powered recommendation enhancement** (requires `LLM_ENABLED=1` and `OPENAI_API_KEY`):

```powershell
# Step 1: Set environment variables
$env:LLM_ENABLED="1"
$env:OPENAI_API_KEY="sk-..."  # Your API key

# Step 2: Create an issue
curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{
    "source": "edit_check",
    "domain": "AE",
    "subject_id": "SUBJ-LLM-001",
    "fields": ["AESTDTC", "AEENDTC"],
    "description": "AE end date is before start date.",
    "evidence_payload": {}
  }'

# Step 3: Analyze with LLM (save issue_id from step 2)
curl -X POST "http://127.0.0.1:8000/issues/<ISSUE_ID>/analyze" `
  -H "Content-Type: application/json" `
  -d '{"use_llm": true}'

# Step 4: Check the response
# - recommendation.tool_results.llm_enhanced should be true
# - recommendation.tool_results.llm_model should be present (e.g., "gpt-4o-mini")
# - recommendation.rationale should be enhanced
# - recommendation.draft_message should be improved
```

**Expected LLM enhancement**:
- `llm_enhanced: true`
- `llm_model: "gpt-4o-mini"` (or configured model)
- Enhanced `rationale` (more detailed, context-aware)
- Improved `draft_message` (if action is QUERY_SITE)

### Test 2: LLM Enhancement for LLM-Required Issues

**Test automatic LLM enhancement for LLM-required issues**:

```powershell
# Step 1: Create an LLM-required issue (complex description)
curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{
    "source": "listing",
    "domain": "AE",
    "subject_id": "SUBJ-LLM-002",
    "fields": ["AETERM"],
    "description": "Complex adverse event with multiple related conditions. Requires medical review to determine if single or multiple events.",
    "evidence_payload": {}
  }'

# Step 2: Check issue_type (should be "llm_required")
# GET /issues/<ISSUE_ID>

# Step 3: Analyze (should automatically use LLM)
curl -X POST "http://127.0.0.1:8000/issues/<ISSUE_ID>/analyze"

# Step 4: Verify LLM was used automatically
# - recommendation.tool_results.llm_enhanced should be true
# - recommendation.tool_results.rag_method should be "semantic" (if RAG_SEMANTIC=1)
```

### Test 3: LLM Enhancement Override

**Test request-level LLM override**:

```powershell
# Create a deterministic issue
curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{
    "source": "edit_check",
    "domain": "AE",
    "subject_id": "SUBJ-LLM-003",
    "fields": ["AESTDTC"],
    "description": "Missing end date for ongoing AE.",
    "evidence_payload": {}
  }'

# Analyze with LLM override (even though it's deterministic)
curl -X POST "http://127.0.0.1:8000/issues/<ISSUE_ID>/analyze" `
  -H "Content-Type: application/json" `
  -d '{"use_llm": true, "use_semantic_rag": true}'

# Verify LLM was used despite deterministic classification
```

---

## End-to-End Workflow

### Complete Test Scenario

**Test the full workflow: Classification → RAG → LLM → Decision**:

```powershell
# Step 1: Ingest documents
python scripts/ingest_mock_documents.py

# Step 2: Upload Excel file (contains mix of issue types)
curl -X POST "http://127.0.0.1:8000/ingest/issues" `
  -F "file=@data/seed/rave_export_demo.xlsx"

# Step 3: List issues and verify classifications
curl "http://127.0.0.1:8000/issues" | ConvertFrom-Json | Select-Object issue_id, domain, description, issue_type

# Step 4: Analyze a deterministic issue
$deterministicIssue = (curl "http://127.0.0.1:8000/issues" | ConvertFrom-Json | Where-Object { $_.issue_type -eq "deterministic" } | Select-Object -First 1)
curl -X POST "http://127.0.0.1:8000/issues/$($deterministicIssue.issue_id)/analyze"

# Step 5: Analyze an LLM-required issue
$llmIssue = (curl "http://127.0.0.1:8000/issues" | ConvertFrom-Json | Where-Object { $_.issue_type -eq "llm_required" } | Select-Object -First 1)
$run = curl -X POST "http://127.0.0.1:8000/issues/$($llmIssue.issue_id)/analyze" | ConvertFrom-Json

# Step 6: Verify LLM-required issue used LLM+RAG
# Check: $run.recommendation.tool_results.llm_enhanced should be true
# Check: $run.recommendation.tool_results.rag_method should be "semantic" (if enabled)
# Check: $run.recommendation.citations should have document IDs

# Step 7: Record a decision
curl -X POST "http://127.0.0.1:8000/issues/$($llmIssue.issue_id)/decisions" `
  -H "Content-Type: application/json" `
  -d "{
    \"run_id\": \"$($run.run_id)\",
    \"decision_type\": \"APPROVE\",
    \"final_action\": \"QUERY_SITE\",
    \"final_text\": \"Send query to site for clarification.\",
    \"reviewer\": \"tester\"
  }"

# Step 8: Check audit log
curl "http://127.0.0.1:8000/audit?issue_id=$($llmIssue.issue_id)"
```

---

## Using the UI

### Test via React Frontend

1. **Start the frontend**:
   ```powershell
   cd frontend
   npm run dev
   ```

2. **Access the UI**: `http://localhost:5173`

3. **Test Classification**:
   - Upload Excel file via Upload page
   - Go to Issues page
   - Check the "Type" column - should show "Rule" (deterministic) or "LLM" (llm_required)

4. **Test RAG**:
   - Click on an issue
   - Click "Run analyze"
   - Check "Recommendation" section:
     - Should show citations (document IDs)
     - Should show `rag_method` (keyword or semantic)
     - Should show citation hits with titles/sources

5. **Test LLM Enhancement**:
   - For LLM-required issues, checkboxes should be auto-enabled
   - Check "Use LLM enhancement" and "Use semantic RAG"
   - Click "Run analyze"
   - Check recommendation details:
     - Should show `llm_model`
     - Should show enhanced rationale
     - Should show improved draft_message

---

## Troubleshooting

### Classification Issues

**Issue**: All issues classified as deterministic
- **Check**: Description doesn't contain LLM-required keywords
- **Solution**: Use descriptions with keywords like "complex", "ambiguous", "clinical significance"

**Issue**: LLM fallback not working
- **Check**: `CLASSIFIER_USE_LLM_FALLBACK=1` is set
- **Check**: `LLM_ENABLED=1` and `OPENAI_API_KEY` are set
- **Check**: Rule-based classifier confidence is "low" (use ambiguous descriptions)

### RAG Issues

**Issue**: No citations returned
- **Check**: Documents are ingested (`python scripts/ingest_mock_documents.py`)
- **Check**: Issue domain matches document domains
- **Solution**: Verify documents exist: `curl "http://127.0.0.1:8000/documents/search?q=AE"`

**Issue**: Semantic RAG not working
- **Check**: `RAG_SEMANTIC=1` is set
- **Check**: First run downloads model (~90MB download)
- **Check**: `sentence-transformers` is installed: `pip install sentence-transformers`

### LLM Issues

**Issue**: LLM enhancement not working
- **Check**: `LLM_ENABLED=1` is set
- **Check**: `OPENAI_API_KEY` is valid
- **Check**: API key has credits/quota
- **Check**: Network connectivity to OpenAI API

**Issue**: LLM fallback not triggering
- **Check**: Issue description is ambiguous (no clear keywords)
- **Check**: `CLASSIFIER_USE_LLM_FALLBACK=1` is set
- **Solution**: Use descriptions like "Some issue with no clear pattern that needs review"

### General Debugging

**Check API logs**:
```powershell
# API server logs show:
# - Classification results
# - RAG method used
# - LLM calls (if enabled)
# - Errors
```

**Check issue details**:
```powershell
curl "http://127.0.0.1:8000/issues/<ISSUE_ID>"
# Verify issue_type field
```

**Check analysis results**:
```powershell
curl "http://127.0.0.1:8000/issues/<ISSUE_ID>/runs"
# Check tool_results for classification, RAG, LLM metadata
```

---

## Python Script Testing

### Test Classification Programmatically

```python
from agent.classify.classifier import classify_issue, _classify_rule_based
from agent.schemas.issue import IssueCreate, IssueDomain, IssueSource

# Test deterministic
ic = IssueCreate(
    source=IssueSource.EDIT_CHECK,
    domain=IssueDomain.AE,
    subject_id="TEST",
    fields=["AESTDTC"],
    description="AE end date is before start date.",
    evidence_payload={}
)
result = _classify_rule_based(ic)
print(f"Type: {result.issue_type.value}, Confidence: {result.confidence}")

# Test LLM-required
ic2 = IssueCreate(
    source=IssueSource.LISTING,
    domain=IssueDomain.AE,
    subject_id="TEST",
    fields=["AETERM"],
    description="Complex adverse event with multiple related conditions.",
    evidence_payload={}
)
result2 = _classify_rule_based(ic2)
print(f"Type: {result2.issue_type.value}, Confidence: {result2.confidence}")
```

---

## Summary

This guide covers:
- ✅ Testing rule-based classification (deterministic vs LLM-required)
- ✅ Testing LLM fallback for uncertain cases
- ✅ Testing keyword RAG (default)
- ✅ Testing semantic RAG (embedding-based)
- ✅ Testing LLM enhancement (recommendation improvement)
- ✅ End-to-end workflow testing
- ✅ UI-based testing
- ✅ Troubleshooting common issues

For more details, see:
- `README.md` - General documentation
- `TESTING_GUIDE.md` - Basic testing guide
- `QUICK_START.md` - Quick setup guide
