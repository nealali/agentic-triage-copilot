# Agentic Triage Copilot

**Enterprise GenAI Agent for Clinical & Commercial Data Issue Triage and Insight Generation**

Agentic Triage Copilot is an **issue triage and decision layer** built for **pharma/biotech** workflows where data quality, traceability, and consistent decision-making matter (Clinical Data Management, Statistical Programming, Medical Review, Commercial Analytics).

It is designed to sit **downstream of your existing edit checks, QC programs, and validation tools** and standardize how issues are **captured**, **contextualized**, **reviewed**, and **documented**.

## Overview
When QC outputs flag issues (AE date inconsistencies, SDTM compliance findings, out-of-window visits, missingness, duplicates), teams often repeat the same work:
- interpret listings
- pull supporting records
- apply known checks
- write rationales and queries
- track decisions in emails or SAS logs

Agentic Triage Copilot reduces that friction by acting as a **triage and decision layer**:
- it captures issues in a consistent schema
- assembles evidence payloads
- applies deterministic checks you define
- produces a structured recommendation with a rationale
- keeps humans in control of final decisions
- builds a searchable institutional memory of how similar issues were handled

## Where it fits in the clinical data lifecycle
This system is intended to integrate with the tools you already use (not replace them):
- **Upstream**: edit checks, SDTM/ADaM validation, QC listings, reconciliation programs
- **This system**: triage + recommendation + human decision + audit trail
- **Downstream**: standardized queries/messages, documented rationales, inspection-ready evidence

## Key capabilities (enterprise-style)
### Deterministic-first “facts” layer
Anything that must be correct and reproducible (ranges, date logic, duplicates, joins, thresholds) should be computed by deterministic tools (rules/SQL/pandas), then summarized.

### Evidence-grounded reasoning (RAG)
Recommendations should be grounded in enterprise documentation (Data Review Plan, edit check specs, query writing guides). The goal is: **no policy claims without citations**.

### Human-in-the-loop decisions
The system should support approve/override/edit workflows with required rationale for overrides and a clear record of “model suggestion vs human decision.”

### Auditability and replay
For every recommendation, it should be possible to answer:
“What evidence did we use, what rules fired, what prompt/version ran, what model was used, and who approved the final action?”

## Current implementation status (what exists in this repo today)
This repository currently includes an MVP foundation:
- **FastAPI API** (`apps/api/main.py`) with a global `app`
- **Issue contracts** (Pydantic v2) in `agent/schemas/issue.py`
- **Recommendation contracts** (Pydantic v2) in `agent/schemas/recommendation.py`
- **Agent run contracts** (Pydantic v2) in `agent/schemas/run.py`
- **Decision contracts** (Pydantic v2) in `agent/schemas/decision.py`
- **Audit event contracts** (Pydantic v2) in `agent/schemas/audit.py`
- **Document contracts** (Pydantic v2) in `agent/schemas/document.py` (RAG-lite guidance ingestion)
- **Analyze request contract** (Pydantic v2) in `agent/schemas/analyze.py` (rules_version + replay linkage)
- **UI view models** (Pydantic v2) in `agent/schemas/views.py` (combined responses for frontends)
- **Swappable storage backend** (`apps/api/storage.py`):
  - Default: in-memory (fast MVP iteration)
  - Optional: Postgres persistence via `PostgresStorageBackend` (enabled by env vars)
  - Uses SQLAlchemy Core (not ORM) for a simple, explicit storage layer
  - UUIDs are stored as native UUIDs on Postgres; SQLite tests store UUIDs as strings for portability
- **Deterministic analyzer** (`agent/analyze/deterministic.py`) to produce structured recommendations (no LLM)
- **Ingestion normalizers** (`agent/ingest/normalizers.py`) to convert source-specific payloads into `IssueCreate`
- **API routers**:
  - `apps/api/routes/issues.py`
  - `apps/api/routes/ingest.py` (Excel file upload)
  - `apps/api/routes/analyze.py`
  - `apps/api/routes/decisions.py`
  - `apps/api/routes/audit.py`
  - `apps/api/routes/documents.py`
  - `apps/api/routes/eval.py`
- **Correlation IDs + structured request logging**:
  - Every response includes an `X-Correlation-ID` header
  - Audit events include `correlation_id` to trace “what happened during one request”
- **Automated tests**:
  - API workflow tests (in-memory backend) with test isolation
  - Storage round-trip tests for `PostgresStorageBackend` using SQLite (no external DB required)
- **Tooling baseline**: Ruff + Black config (`pyproject.toml`), test/run docs, `requirements.txt`, `requirements-dev.txt`
- **CI**: GitHub Actions workflow in `.github/workflows/ci.yml`:
  - Lint + tests (default in-memory backend)
  - Tests against a real Postgres service (backend switch via env vars)
- **Demo automation**: `scripts/demo_flow.ps1`
- **Excel ingestion**: seed file `data/seed/rave_export_demo.xlsx`, CLI script `scripts/ingest_from_excel.py`, and **POST `/ingest/issues`** for UI upload (see [Excel ingestion](#excel-ingestion) below).
- **Full app (React)**: optional multi-page UI in `frontend/` for upload, issues list, issue detail, run analyze, record decision, and audit (see [Full app (React)](#full-app-react) below).
- **Optional persistence path**:
  - Enable Postgres backend via environment variables (see below)
  - `infra/docker-compose.yml` (Postgres + API)
  - `alembic.ini` + `infra/migrations/` (migrations scaffold)

## API (MVP)
### Endpoints
- **GET `/health`**: service health check
- **POST `/issues`**: create an issue
- **GET `/issues`**: list issues
- **GET `/issues/{issue_id}`**: fetch a single issue (404 if not found)
- **GET `/issues/{issue_id}/overview`**: UI-friendly “one call” view (issue + latest run/decision + recent audit)
- **POST `/issues/{issue_id}/analyze`**: run deterministic analysis and create an AgentRun
  - Supports an optional JSON body: `{"rules_version": "v0.1", "replay_of_run_id": "<RUN_ID>"}` for versioning/replay linkage
- **GET `/issues/{issue_id}/runs`**: list analysis runs (summary)
- **POST `/issues/{issue_id}/decisions`**: record a human decision tied to a run_id
- **GET `/issues/{issue_id}/decisions`**: list decisions (most recent first)
- **POST `/documents`**: ingest a guidance document (RAG-lite)
- **GET `/documents/search?q=...`**: keyword search guidance documents
  - Search is **term-based** (query is split into keywords; it does not require the whole phrase to match as one substring)
- **GET `/documents/{doc_id}`**: fetch a guidance document by ID
- **POST `/ingest/issues`**: upload a single `.xlsx` file (RAVE/QC export style); creates issues via the same normalizer as the CLI script. Returns `{ "created", "issue_ids", "errors" }`. Limits: 200 rows per file, 5 MB. Accepts only `.xlsx`.
- **GET `/audit`**: query audit events (optional `issue_id`, `run_id`)
- **GET `/eval/scorecard`**: export scorecard rows for runs

### Guidance documents + citations (RAG-lite)
This repo now supports a small, explainable “RAG-lite” loop:

- You ingest guidance as **documents** (`POST /documents`)
- The analyzer runs deterministic rules and then does a keyword lookup over documents
- The recommendation includes:
  - `recommendation.citations`: a list of **document IDs** supporting the recommendation
  - `recommendation.tool_results.citation_hits`: small metadata about retrieved docs (title/source/score)

This is intentionally simple (no embeddings yet), but it demonstrates the enterprise idea:
**“no guidance claims without a citation trail.”**

### Excel ingestion
You can load issues from an Excel file in two ways.

1. **Seed file**  
   - Location: `data/seed/rave_export_demo.xlsx` (10 example rows).  
   - Column schema (case-insensitive, with underscores): **Source**, **Domain**, **Subject_ID**, **Fields**, **Description** (required); optional: **Start_Date**, **End_Date**, **Variable**, **Value**, **Reference**, **Notes** (mapped into `evidence_payload`). Source must be `edit_check` or `listing` (default `edit_check`).

2. **CLI script**  
   - Run from repo root:  
     `python scripts/ingest_from_excel.py [path_to.xlsx] [--base-url URL]`  
   - Default path: `data/seed/rave_export_demo.xlsx`.  
   - Use `--dry-run` to validate and print payloads without POSTing.

3. **API upload**  
   - **POST `/ingest/issues`**: `multipart/form-data` with a single file (`file`). Accepts `.xlsx` only. Returns `{ "created", "issue_ids", "errors" }`. Max 200 rows per file, 5 MB. Invalid rows are skipped and reported in `errors`.

### Full app (React)
An optional multi-page UI uses the FastAPI backend for the full triage workflow.

- **Location**: `frontend/` (Vite + React 18 + TypeScript + React Router + Tailwind).
- **Prerequisites**: Node.js 18+ and npm (or equivalent).
- **Run**:
  ```powershell
  cd frontend
  npm install
  npm run dev
  ```
  Opens at `http://localhost:5173`. Set `VITE_API_BASE_URL` in `frontend/.env` if the API is not at `http://localhost:8000` (e.g. `VITE_API_BASE_URL=http://localhost:8000`).
- **Pages**: Upload (Excel file → POST `/ingest/issues`), Issues list (filter by status), Issue detail (overview, Run analyze, Record decision), Audit log. When the backend has **AUTH_ENABLED=1**, use the “API key” control in the nav to set `X-API-Key` (stored in session only).
- **CORS**: The API allows the React dev server by default (`http://localhost:5173`, `http://127.0.0.1:5173`). Override with env: `CORS_ORIGINS` (comma-separated list).

### Issue data contract (MVP)
An issue represents a triage unit of work tied to a subject and domain (DM/VS/LB/AE/Commercial/Medical).

- **`source`**: `manual | edit_check | listing`
- **`domain`**: `DM | VS | LB | AE | COMMERCIAL | MEDICAL`
- **`subject_id`**: subject identifier (synthetic or real, depending on environment)
- **`fields`**: list of impacted variables (e.g., `AESTDTC`, `AEENDTC`)
- **`description`**: human-readable summary of the issue
- **`evidence_payload`**: small structured JSON containing the relevant values/rows (not entire tables)
- **`issue_id` / `created_at` / `status`**: system-managed metadata

## Security & governance posture (how this becomes “enterprise-ready”)
### Secrets management
- **Never commit `.env`**. This repo ignores it via `.gitignore`.
- In production, API keys should live in a secrets manager (e.g., Vault, AWS Secrets Manager, Azure Key Vault) and be injected at runtime.

### Data handling
- The intent is to pass **minimal necessary evidence** into LLM calls (summaries + small structured payloads), not bulk datasets.
- In regulated settings, you would apply environment controls (network egress rules, logging policy, access controls) appropriate to PHI/PII and study governance.

### Compliance note
This repository demonstrates **enterprise patterns** (contracts, testing, audit-first design). Actual GxP / 21 CFR Part 11 compliance depends on controls and validation in the deployment environment and is not claimed by this repo alone.

## Quick start (local development)
### Python version
This repo pins a recommended local Python version in `.python-version` (useful with tools like pyenv).

### 1) Create a virtual environment and install dependencies

```powershell
cd c:\dev\agentic-triage-copilot
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
```

### 2) Run the API

```powershell
uvicorn apps.api.main:app --reload
```

Open the interactive API docs at `http://127.0.0.1:8000/docs`.

### 2.0) Notes on observability (correlation IDs)
Every API response includes an `X-Correlation-ID` header. This helps you trace:
- the request that created a run/decision
- the audit events produced by that request

### 2.0) Run a full demo flow script
With the API running, you can exercise the full workflow in one command:

```powershell
.\scripts\demo_flow.ps1
```

Optional:
- Demonstrate persistence across restarts (useful with Postgres backend):

```powershell
.\scripts\demo_flow.ps1 -PauseForRestart
```

- If API-key auth is enabled, pass a key:

```powershell
.\scripts\demo_flow.ps1 -ApiKey "devkey"
```

### 2.1) Example curl commands (Windows-friendly)

Create an issue:

```powershell
curl -X POST "http://127.0.0.1:8000/issues" `
  -H "Content-Type: application/json" `
  -d '{\"source\":\"manual\",\"domain\":\"AE\",\"subject_id\":\"SUBJ-100\",\"fields\":[\"AESTDTC\",\"AEENDTC\"],\"description\":\"AE end date is before start date.\",\"evidence_payload\":{\"start_date\":\"2024-01-10\",\"end_date\":\"2024-01-01\"}}'
```

Analyze an issue (replace `<ISSUE_ID>`):

```powershell
curl -X POST "http://127.0.0.1:8000/issues/<ISSUE_ID>/analyze"
```

Record a decision (replace `<ISSUE_ID>` and `<RUN_ID>`):

```powershell
curl -X POST "http://127.0.0.1:8000/issues/<ISSUE_ID>/decisions" `
  -H "Content-Type: application/json" `
  -d '{\"run_id\":\"<RUN_ID>\",\"decision_type\":\"APPROVE\",\"final_action\":\"QUERY_SITE\",\"final_text\":\"Send site query.\",\"reviewer\":\"jdoe\"}'
```

### 3) Run tests
Recommended:

```powershell
.\run_tests.ps1
```

Or:

```powershell
python -m pytest -q
```

### 4) Lint and formatting checks (what CI runs)
Locally, you can run the same checks as GitHub Actions:

```powershell
ruff check .
black --check .
python -m pytest -q
```

## Optional: API-key auth (basic, default OFF)
This repo includes a minimal API-key auth layer suitable for demos and learning.

- **Default**: auth is disabled (no keys required).
- **Enable**:

```powershell
$env:AUTH_ENABLED="1"
$env:API_KEYS="devkey:jdoe:reviewer|writer,adminkey:admin:admin"
```

When auth is enabled:
- Mutation endpoints like **POST `/documents`** and **POST `/issues/{issue_id}/decisions`** require `X-API-Key`.
- Decision recording prevents “reviewer spoofing” by enforcing `reviewer` matches the authenticated user.

## CI: tests against Postgres (production realism)
In addition to the standard lint + unit tests, CI runs a second job that executes the test suite
against a real Postgres container:
- Sets `STORAGE_BACKEND=postgres`
- Sets `DATABASE_URL=postgresql+psycopg://...`
- Uses `AUTO_CREATE_SCHEMA=1` so tables are created during the job

This matters because Postgres behaves differently than SQLite in important ways (types, JSON,
case-insensitive search), and we want those differences caught automatically.

## Optional: Docker + Postgres + migrations (persistence path)
The application runs without a database by default, but the repo includes a clean path to persistence.

### Enable the Postgres storage backend (env vars)
By default the API uses in-memory storage. To persist issues/runs/decisions/audit events, set:

```powershell
$env:STORAGE_BACKEND="postgres"
$env:DATABASE_URL="postgresql+psycopg://app:app@localhost:5432/triage"
```

Optional:
- `AUTO_CREATE_SCHEMA=1` will auto-create tables at startup (handy for demos).
- For production-style workflows, prefer **Alembic migrations** (below).

### Start Postgres + API via Docker Compose

```powershell
docker compose -f .\infra\docker-compose.yml up --build
```

### Migrations (Alembic)
Migrations are scaffolded under `infra/migrations/`. When you’re ready to apply them:

```powershell
$env:DATABASE_URL="postgresql+psycopg://app:app@localhost:5432/triage"
alembic upgrade head
```

Notes:
- `0001_initial_tables` creates issues/runs/decisions/audit tables
- `0002_documents_table` adds the `documents` table used by the RAG-lite layer

## Important operational note (MVP)
By default, the store is a global in-memory dictionary (`ISSUES`):
- it **resets on server restart**
- tests must clear it to remain independent (the test suite does this)

When you switch to `STORAGE_BACKEND=postgres`, the same API routes write to Postgres instead, so runs,
decisions, and audit events survive restarts.

## Repository structure

```
agentic-triage-copilot/
  .github/workflows/      # CI pipeline (lint + tests)
  apps/
    api/                 # FastAPI service (routes: issues, ingest, analyze, decisions, audit, documents, eval)
  agent/
    analyze/             # deterministic analyzer (current MVP)
    ingest/              # ingestion/normalization adapters (Excel normalizer, etc.)
    schemas/             # Pydantic models (IO contracts)
    tools/               # deterministic checks (planned)
    prompts/             # versioned prompts (planned)
    retrieval/           # RAG ingest + search (planned)
  data/
    seed/                # Excel seed file (rave_export_demo.xlsx)
    goldenset/           # labeled evaluation cases (planned)
  frontend/              # React app (optional): upload, issues, detail, audit
  infra/                 # docker / db / migrations (path included)
  eval/                  # evaluation harness (planned)
  scripts/               # demo scripts, ingest_from_excel.py, generate_seed_excel.py
```

## Roadmap (production target)
- **Contracts**: refine contracts as the workflow grows (e.g., audit event taxonomy, decision types)
- **Persistence**: Postgres + migrations; store issues, runs, decisions, audit events, documents/chunks
- **Deterministic tools**: rules engine + pandas/SQL checks (small structured outputs)
- **Retrieval (RAG)**: ingest SOP/spec docs; retrieve top-k evidence; require citations
- **Agent workflow**: step-based execution (graph/state machine), retries/fallbacks, replayability
- **Evaluation**: gold set + business-aligned metrics (override rate, hallucination rate, latency, cost)

