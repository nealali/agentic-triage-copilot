# Quick Start Guide - Running Tests

## Option 1: Automated Script (Easiest)

Simply run the PowerShell script:

```powershell
.\run_tests.ps1
```

This script will:
- ✅ Create a virtual environment if needed
- ✅ Install dependencies automatically
- ✅ Run all tests with detailed output

## Option 2: Manual Steps

### 1. Create and activate virtual environment

```powershell
# Create virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Run tests

```powershell
pytest apps/api/tests/test_issues.py -v
```

## Expected Output

When everything works, you should see:

```
========================= test session starts =========================
platform win32 -- Python 3.13.2, pytest-7.4.0, pluggy-1.3.0
collected 3 items

apps/api/tests/test_issues.py::test_create_issue_then_get_by_id_returns_it PASSED [ 33%]
apps/api/tests/test_issues.py::test_list_issues_includes_created_issues PASSED [ 66%]
apps/api/tests/test_issues.py::test_get_unknown_issue_returns_404 PASSED [100%]

========================= 3 passed in 0.15s =========================
```

**3 passed** = ✅ All tests are working correctly!

## Troubleshooting

- **"pytest: command not found"** → Make sure virtual environment is activated
- **"ModuleNotFoundError"** → Run `pip install -r requirements.txt`
- **Tests fail** → Read the error message - it tells you what went wrong

For detailed explanations, see [TESTING_GUIDE.md](TESTING_GUIDE.md).
