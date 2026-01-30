# PowerShell script to run tests
# Usage: .\run_tests.ps1

Write-Host "Running tests for Agentic Triage Copilot..." -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path ".venv")) {
    Write-Host "Virtual environment not found. Creating one..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "Virtual environment created!" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& .venv\Scripts\Activate.ps1

# Check if requirements are installed
Write-Host "Checking dependencies..." -ForegroundColor Cyan
$pytestInstalled = python -c "import pytest" 2>$null
if (-not $pytestInstalled) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
    Write-Host "Dependencies installed!" -ForegroundColor Green
}

Write-Host ""
Write-Host "Running tests..." -ForegroundColor Cyan
Write-Host ""

# Run tests with verbose output
pytest apps/api/tests/test_issues.py -v

Write-Host ""
Write-Host "Tests completed!" -ForegroundColor Cyan
