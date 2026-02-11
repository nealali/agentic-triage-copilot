# Professional Testing Guide for Agentic Triage Copilot

This guide will walk you through setting up and running tests for the API in a professional, reproducible way.

## Table of Contents
1. [Understanding What We're Testing](#understanding-what-were-testing)
2. [Prerequisites](#prerequisites)
3. [Step-by-Step Setup](#step-by-step-setup)
4. [Running the Tests](#running-the-tests)
5. [Understanding Test Results](#understanding-test-results)
6. [Verifying System Behavior](#verifying-system-behavior)
7. [Troubleshooting](#troubleshooting)

---

## Understanding What We're Testing

### What is a Test?
A **test** is code that verifies your application works correctly. Think of it like a quality check:
- You write code that does something (like creating an issue)
- You write a test that checks if it works as expected
- If the test passes ✅, your code is working correctly
- If the test fails ❌, something is broken

### What Are We Testing?
This repo started with simple “issues” tests and now includes a more realistic workflow suite:

1. **Issues API**
   - Create issues
   - List issues
   - Retrieve by ID (404 behavior)
2. **Analyze workflow**
   - Deterministic analysis creates an `AgentRun`
   - Issue status transitions to `triaged`
   - Audit events are created and correlation IDs are propagated
   - Analyze supports `rules_version` and `replay_of_run_id` metadata
3. **Human decisions**
   - Decisions are tied to a `run_id` (auditability)
   - Overrides require a reason (schema validation)
4. **Audit + evaluation exports**
   - Audit query filters by issue_id and run_id
   - Scorecard export returns structured rows for evaluation/QA
5. **Documents (RAG-lite)**
   - Ingest guidance documents
   - Keyword search guidance docs
   - Analyzer attaches citation doc IDs to recommendations
6. **Excel ingestion**
   - Normalizer `from_excel_row` maps Excel columns to `IssueCreate` and `evidence_payload`
7. **Automatic issue classification**
   - Issues are automatically classified as `deterministic` or `llm_required` during ingestion
   - **General rules first** (domain-agnostic keywords/patterns), then **domain-specific refinements**, with **scoring**
   - Optional LLM fallback for uncertain cases (`CLASSIFIER_USE_LLM_FALLBACK=1`)
   - In the UI, **deterministic** issues default to no LLM and no semantic RAG; **llm_required** issues force both on
8. **RAG (Retrieval-Augmented Generation)**
   - Keyword-based document retrieval (default)
   - Semantic search using embeddings (optional, `RAG_SEMANTIC=1`)
   - Citations attached to recommendations
9. **LLM enhancement**
   - Optional LLM-powered recommendation enhancement (`LLM_ENABLED=1`)
   - Automatic LLM usage for `llm_required` issues
   - Request-level override support
   - **POST `/ingest/issues`** accepts an `.xlsx` file and creates issues; test uploads fixture and asserts created count and that GET /issues includes new IDs (`apps/api/tests/test_excel_ingest.py`)
7. **Optional API-key auth (feature-flagged)**
   - When enabled, mutation endpoints require `X-API-Key`
   - Reviewer spoofing is prevented on decisions
8. **Storage backends**
   - Default in-memory backend (fast MVP)
   - Postgres backend tested in CI against a real Postgres container

### Why Use pytest?
**pytest** is a professional testing framework used by millions of Python developers. It:
- Provides clear, readable test output
- Makes it easy to write and organize tests
- Can run tests in parallel (faster)
- Integrates with CI/CD systems (for automated testing)

---

## Prerequisites

Before starting, ensure you have:
- **Python 3.8+** installed (check with `python --version`)
- **pip** (Python package installer, comes with Python)
- **A terminal/command prompt** (PowerShell on Windows, Terminal on Mac/Linux)

### Check Your Python Installation

Open your terminal and run:

```powershell
python --version
```

You should see a Python version string. This repo also includes a `.python-version` file as a recommended version pin.

---

## Step-by-Step Setup

### Step 1: Navigate to Your Project Directory

Open PowerShell (or your terminal) and navigate to your project:

```powershell
cd c:\dev\agentic-triage-copilot
```

**What this does**: Changes your current directory to the project folder so all commands run in the right place.

### Step 2: Create a Virtual Environment

A **virtual environment** is an isolated Python environment for your project. This prevents conflicts between different projects' dependencies.

```powershell
python -m venv .venv
```

**What this does**: Creates a folder called `.venv` containing a fresh Python environment.

**Why it's important**: 
- Keeps your project's dependencies separate from other projects
- Makes your setup reproducible
- Prevents version conflicts

### Step 3: Activate the Virtual Environment

**On Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**On Windows (Command Prompt):**
```cmd
.venv\Scripts\activate.bat
```

**On Mac/Linux:**
```bash
source .venv/bin/activate
```

**What this does**: Activates the virtual environment. You'll notice `(.venv)` appears at the start of your command prompt.

**How to know it worked**: Your prompt should look like:
```
(.venv) PS C:\dev\agentic-triage-copilot>
```

**Important**: You must activate the virtual environment every time you open a new terminal session.

### Step 4: Install Dependencies

Install all required packages:

```powershell
pip install -r requirements.txt -r requirements-dev.txt
```

**What this does**: Installs runtime + dev tooling so your local runs match CI.

**Expected output**: You'll see packages being downloaded and installed. It may take 30-60 seconds.

**What each package does**:
- `fastapi` - The web framework for building APIs
- `uvicorn` - The server that runs FastAPI applications
- `pytest` - The testing framework
- `httpx` - HTTP client library (used by FastAPI's TestClient)
- `pydantic` - Data validation library
- `python-dotenv` - For loading `.env` files
- `ruff` - Fast linter (CI lint step)
- `black` - Formatter (CI format check step)
- `SQLAlchemy` / `psycopg` / `alembic` - DB/persistence path + Postgres backend support

### Step 5: Verify Installation

Check that pytest is installed correctly:

```powershell
pytest --version
```

You should see something like `pytest 7.4.0` or similar.

---

## Running the Tests

### Recommended (match CI)

Run the same checks CI runs:

```powershell
ruff check .
black --check .
pytest -q
```

**What this does**: 
- Finds all test functions (functions starting with `test_`)
- Runs each test
- Reports which passed and which failed

### Verbose Output (Recommended)

See more detailed information:

```powershell
pytest apps/api/tests/test_issues.py -v
```

The `-v` flag stands for "verbose" - it shows each test name as it runs.

### Even More Detail

See print statements and detailed output:

```powershell
pytest apps/api/tests/test_issues.py -v -s
```

The `-s` flag shows print statements and other output.

### Run All Tests in the Project

If you have tests in multiple locations:

```powershell
pytest
```

This searches for all `test_*.py` files and runs them.

---

## Understanding Test Results

### Successful Test Run

When all tests pass, you'll see:

```
========================= test session starts =========================
platform win32 -- Python 3.13.2, pytest-7.4.0, pluggy-1.3.0
collected 3 items

apps/api/tests/test_issues.py::test_create_issue_then_get_by_id_returns_it PASSED [ 33%]
apps/api/tests/test_issues.py::test_list_issues_includes_created_issues PASSED [ 66%]
apps/api/tests/test_issues.py::test_get_unknown_issue_returns_404 PASSED [100%]

========================= 3 passed in 0.15s =========================
```

**What this means**:
- ✅ **3 tests collected** - pytest found 3 test functions
- ✅ **3 passed** - All tests succeeded
- ✅ **0.15s** - Tests completed in 0.15 seconds
- Each test name is shown with `PASSED` status

### Failed Test Run

If a test fails, you'll see:

```
========================= test session starts =========================
platform win32 -- Python 3.13.2, pytest-7.4.0, pluggy-1.3.0
collected 3 items

apps/api/tests/test_issues.py::test_create_issue_then_get_by_id_returns_it FAILED [ 33%]
apps/api/tests/test_issues.py::test_list_issues_includes_created_issues PASSED [ 66%]
apps/api/tests/test_issues.py::test_get_unknown_issue_returns_404 PASSED [100%]

========================= FAILURES =========================
FAILED apps/api/tests/test_issues.py::test_create_issue_then_get_by_id_returns_it
...
AssertionError: assert 404 == 200
```

**What this means**:
- ❌ **1 failed** - One test didn't pass
- The error message shows what went wrong
- Other tests still passed (they're independent)

### Understanding Test Output Sections

1. **Test session starts** - Shows Python/pytest versions
2. **collected X items** - Number of tests found
3. **Test names** - Each `test_*` function is listed
4. **Status** - `PASSED`, `FAILED`, `SKIPPED`, etc.
5. **Summary** - Total passed/failed and time taken

---

## Verifying System Behavior

### What the workflow tests verify (why they matter)
The workflow suite (for example, `apps/api/tests/test_workflow.py`) is closer to how the system is used in real
clinical programming / data management workflows:
- **Create → Analyze → Decide → Audit → Eval**
- Ensures the system is not only “up”, but **behaves correctly as a decision workflow**

The document tests (for example, `apps/api/tests/test_documents.py`) verify the “RAG-lite” path:
- ingest guidance documents
- search guidance deterministically
- attach citations during analysis

### Manual Verification (Optional)

You can also test the API manually:

1. **Start the server**:
   ```powershell
   uvicorn apps.api.main:app --reload
   ```

2. **Open your browser** to `http://localhost:8000/docs`
   - This shows FastAPI's automatic API documentation
   - You can test endpoints interactively

3. **Or use curl** (in another terminal):
   ```powershell
   # Create an issue
   curl -X POST "http://localhost:8000/issues" -H "Content-Type: application/json" -d '{\"source\":\"manual\",\"domain\":\"DM\",\"subject_id\":\"TEST-1\",\"fields\":[\"field1\"],\"description\":\"Test issue\",\"evidence_payload\":{}}'
   
   # List all issues
   curl http://localhost:8000/issues
   ```

---

## Troubleshooting

### Problem: "pytest: command not found"

**Solution**: Make sure you:
1. Activated your virtual environment (see Step 3)
2. Installed dependencies (`pip install -r requirements.txt -r requirements-dev.txt`)

### Problem: "ModuleNotFoundError: No module named 'fastapi'"

**Solution**: 
1. Check that your virtual environment is activated (you should see `(.venv)` in your prompt)
2. Reinstall dependencies: `pip install -r requirements.txt`

### Problem: "ImportError: cannot import name 'app'"

**Solution**: Make sure you're running tests from the project root directory:
```powershell
cd c:\dev\agentic-triage-copilot
pytest apps/api/tests/test_issues.py
```

### Problem: Tests pass but you want to see what's happening

**Solution**: Use verbose mode with output:
```powershell
pytest apps/api/tests/test_issues.py -v -s
```

### Problem: “CI Postgres job fails but local tests pass”
**Why it happens**: SQLite and Postgres differ (types, JSON behavior, query semantics).

**Solution**: run the suite locally against Postgres:

```powershell
docker compose -f .\infra\docker-compose.yml up -d
$env:STORAGE_BACKEND="postgres"
$env:DATABASE_URL="postgresql+psycopg://app:app@localhost:5432/triage"
$env:AUTO_CREATE_SCHEMA="1"
pytest -q
```

### Problem: One test fails but others pass

**Solution**: This is normal! Tests are independent. Read the error message to understand what went wrong. The test output will show:
- Which assertion failed
- What value was expected vs. what was received
- The line number where it failed

### Problem: All tests fail immediately

**Solution**: Check that:
1. Your virtual environment is activated
2. All dependencies are installed
3. You're in the correct directory
4. The API code hasn't been modified incorrectly

---

## Best Practices

### 1. Run Tests Frequently
- Run tests after making changes to verify nothing broke
- Run tests before committing code
- Run tests before deploying

### 2. Keep Tests Independent
- Each test should work on its own
- Tests shouldn't depend on each other
- Our `autouse` fixture ensures clean state for each test

### 3. Write Clear Test Names
- Test names should describe what they're testing
- Use descriptive docstrings
- Future you (and teammates) will thank you!

### 4. Test Edge Cases
- Test normal cases (happy path)
- Test error cases (404, invalid data)
- Test boundary cases (empty lists, null values)

---

## Next Steps

Once your tests are passing:

1. **Add more tests** as you add features
2. **Keep CI green** (ruff + black + pytest, plus the Postgres-backed job)
3. **Add test coverage reporting** to see which code is tested
4. **Write integration tests** for full workflows
5. **Add performance tests** for load testing

---

## Summary

Running tests professionally means:
- ✅ Using a virtual environment (isolation)
- ✅ Installing dependencies from `requirements.txt` (reproducibility)
- ✅ Running tests with pytest (professional tooling)
- ✅ Understanding test output (knowing what's working)
- ✅ Fixing failures promptly (maintaining quality)

**Quick Reference**:
```powershell
# Setup (one time)
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt

# Lint and format (fix before committing)
ruff check . --fix
black .

# Run tests (every time you make changes)
ruff check .
black --check .
pytest -q
```

Happy testing! 🧪
