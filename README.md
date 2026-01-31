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
- **In-memory issue store** (`apps/api/storage.py`) for fast iteration (resets on restart)
- **Deterministic analyzer** (`agent/analyze/deterministic.py`) to produce structured recommendations (no LLM)
- **API routers**:
  - `apps/api/routes/issues.py`
  - `apps/api/routes/analyze.py`
  - `apps/api/routes/decisions.py`
  - `apps/api/routes/audit.py`
  - `apps/api/routes/eval.py`
- **Automated tests** (`apps/api/tests/test_issues.py`) that clear the in-memory store between tests
- **Tooling baseline**: Ruff + Black config (`pyproject.toml`), test/run docs, `requirements.txt`

## API (MVP)
### Endpoints
- **GET `/health`**: service health check
- **POST `/issues`**: create an issue
- **GET `/issues`**: list issues
- **GET `/issues/{issue_id}`**: fetch a single issue (404 if not found)
- **POST `/issues/{issue_id}/analyze`**: run deterministic analysis and create an AgentRun
- **GET `/issues/{issue_id}/runs`**: list analysis runs (summary)
- **POST `/issues/{issue_id}/decisions`**: record a human decision tied to a run_id
- **GET `/issues/{issue_id}/decisions`**: list decisions (most recent first)
- **GET `/audit`**: query audit events (optional `issue_id`, `run_id`)
- **GET `/eval/scorecard`**: export scorecard rows for runs

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
### 1) Create a virtual environment and install dependencies

```powershell
cd c:\dev\agentic-triage-copilot
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2) Run the API

```powershell
uvicorn apps.api.main:app --reload
```

Open the interactive API docs at `http://127.0.0.1:8000/docs`.

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

## Important operational note (MVP)
The current store is a global in-memory dictionary (`ISSUES`):
- it **resets on server restart**
- tests must clear it to remain independent (the test suite does this)

This is intentional for early iteration; the roadmap includes Postgres for persistence and audit trails.

## Repository structure

```
agentic-triage-copilot/
  apps/
    api/                 # FastAPI service
  agent/
    schemas/             # Pydantic models (IO contracts)
    tools/               # deterministic checks (planned)
    prompts/             # versioned prompts (planned)
    retrieval/           # RAG ingest + search (planned)
  data/
    seed/                # synthetic seed tables + docs (planned)
    goldenset/           # labeled evaluation cases (planned)
  infra/                 # docker / db / migrations (planned)
  eval/                  # evaluation harness (planned)
```

## Roadmap (production target)
- **Contracts**: refine contracts as the workflow grows (e.g., audit event taxonomy, decision types)
- **Persistence**: Postgres + migrations; store issues, runs, decisions, audit events, documents/chunks
- **Deterministic tools**: rules engine + pandas/SQL checks (small structured outputs)
- **Retrieval (RAG)**: ingest SOP/spec docs; retrieve top-k evidence; require citations
- **Agent workflow**: step-based execution (graph/state machine), retries/fallbacks, replayability
- **Evaluation**: gold set + business-aligned metrics (override rate, hallucination rate, latency, cost)

