## Database migration path (optional for MVP)

The application currently runs on an **in-memory store** (no database required).

This folder contains an **Alembic** migration setup to support the next step:
moving to **Postgres** for persistence and inspection-ready auditability.

### Why migrations matter
- They make database changes **repeatable** and **reviewable**.
- They let you evolve schema over time safely.
- They support enterprise practices (controlled releases, traceability).

### How to run Postgres locally (Docker)

From the repo root:

```powershell
docker compose -f .\infra\docker-compose.yml up --build
```

### How to run migrations (future)

Once you have Postgres running and `DATABASE_URL` set, you can run:

```powershell
$env:DATABASE_URL="postgresql+psycopg://app:app@localhost:5432/triage"
alembic upgrade head
```

Note: The current FastAPI MVP does not use the database yet; this is an enterprise-ready path forward.

