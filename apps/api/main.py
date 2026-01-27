from fastapi import FastAPI

from apps.api.routes.issues import router as issues_router

app = FastAPI(title="Agentic Triage Copilot")

app.include_router(issues_router)


@app.get("/health")
def health():
    return {"status": "ok"}
