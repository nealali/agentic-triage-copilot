# Quick Start Guide (developer workflow)

This guide is the fastest way to verify the repo is healthy on your machine.
For deeper explanations (what pytest is, how to interpret failures), see `TESTING_GUIDE.md`.

## Option 1: One-command test run (recommended)

```powershell
.\run_tests.ps1
```

What it does:
- Creates/uses `.venv`
- Installs dependencies
- Runs `pytest`

## Option 2: Manual setup (PowerShell)

### 1) Create + activate a virtual environment

```powershell
cd c:\dev\agentic-triage-copilot
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2) Install dependencies (match CI)

```powershell
pip install -r requirements.txt -r requirements-dev.txt
```

### 3) Run quality checks (what CI runs)

Run lint and format, then tests (same as CI):

```powershell
ruff check .
black --check .
python -m pytest -q
```

To auto-fix lint/format before committing:

```powershell
ruff check . --fix
black .
python -m pytest -q
```

## What tests exist today (high level)
- **API workflow tests**: issues → analyze → decisions → audit → eval
- **Document tests (RAG-lite)**: ingest docs, keyword search, citations added during analyze
- **Excel ingest tests**: normalizer `from_excel_row` and **POST `/ingest/issues`** (upload fixture Excel, assert created count and GET /issues).
- **Auth tests (optional feature flag)**: API-key auth on mutations, reviewer spoof prevention
- **Postgres backend tests**:
  - unit round-trip via SQLite
  - CI job runs the suite against a real Postgres container

## Optional: Excel ingestion and full app
- **Ingest script**: from repo root, `python scripts/ingest_from_excel.py` (default: `data/seed/rave_export_demo.xlsx`). Use `--dry-run` to validate without POSTing. See README “Excel ingestion” for column schema and API upload.
- **Full app (React)**: optional UI in `frontend/`. See README “Full app (React)” for `npm install`, `npm run dev`, and `VITE_API_BASE_URL`.

## Optional: run tests against Postgres locally
1) Start Postgres (Docker):

```powershell
docker compose -f .\infra\docker-compose.yml up -d
```

2) Enable Postgres backend and run tests:

```powershell
$env:STORAGE_BACKEND="postgres"
$env:DATABASE_URL="postgresql+psycopg://app:app@localhost:5432/triage"
$env:AUTO_CREATE_SCHEMA="1"
python -m pytest -q
```

## Troubleshooting (fast fixes)
- **`pytest` not found**: activate `.venv`
- **`ModuleNotFoundError`**: reinstall deps with `pip install -r requirements.txt -r requirements-dev.txt`
- **Black/ruff fails in CI**: run `black .` and `ruff check . --fix` locally, then re-check with `--check`
