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
Our tests verify that the **Issues API** works correctly:
1. **Creating an issue** - Can we POST a new issue and get it back?
2. **Listing issues** - Can we GET all issues and see the ones we created?
3. **Error handling** - Do we get a 404 error when requesting a non-existent issue?

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

You should see something like `Python 3.13.2`. If you get an error, install Python from [python.org](https://www.python.org/downloads/).

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
pip install -r requirements.txt
```

**What this does**: Reads `requirements.txt` and installs all listed packages (fastapi, pytest, etc.) into your virtual environment.

**Expected output**: You'll see packages being downloaded and installed. It may take 30-60 seconds.

**What each package does**:
- `fastapi` - The web framework for building APIs
- `uvicorn` - The server that runs FastAPI applications
- `pytest` - The testing framework
- `httpx` - HTTP client library (used by FastAPI's TestClient)
- `pydantic` - Data validation library
- `python-dotenv` - For loading `.env` files

### Step 5: Verify Installation

Check that pytest is installed correctly:

```powershell
pytest --version
```

You should see something like `pytest 7.4.0` or similar.

---

## Running the Tests

### Basic Test Run

Run all tests in the test file:

```powershell
pytest apps/api/tests/test_issues.py
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

### What Each Test Verifies

#### Test 1: `test_create_issue_then_get_by_id_returns_it`
**What it tests**: Can we create an issue and then retrieve it?

**Steps the test performs**:
1. Creates a test HTTP client
2. Sends a POST request to `/issues` with issue data
3. Verifies the response is 200 (success)
4. Extracts the `issue_id` from the response
5. Sends a GET request to `/issues/{issue_id}`
6. Verifies we get back the same issue with matching data

**What "passing" means**: 
- ✅ The API can create issues
- ✅ The API can retrieve issues by ID
- ✅ Data is stored correctly

#### Test 2: `test_list_issues_includes_created_issues`
**What it tests**: Can we list all issues and see the ones we created?

**Steps the test performs**:
1. Creates two different issues
2. Gets their IDs
3. Requests all issues via GET `/issues`
4. Verifies both created issues appear in the list

**What "passing" means**:
- ✅ The API can list all issues
- ✅ Created issues appear in the list
- ✅ Multiple issues can coexist

#### Test 3: `test_get_unknown_issue_returns_404`
**What it tests**: Does the API handle missing issues correctly?

**Steps the test performs**:
1. Generates a random UUID (that doesn't exist)
2. Tries to GET that issue
3. Verifies we get a 404 (Not Found) error

**What "passing" means**:
- ✅ The API handles errors correctly
- ✅ Users get appropriate error messages
- ✅ The system doesn't crash on invalid requests

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
2. Installed dependencies (`pip install -r requirements.txt`)

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
2. **Set up CI/CD** to run tests automatically
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
pip install -r requirements.txt

# Run tests (every time you make changes)
pytest apps/api/tests/test_issues.py -v
```

Happy testing! 🧪
