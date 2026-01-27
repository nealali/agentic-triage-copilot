from fastapi import FastAPI

app = FastAPI(title="Agentic Triage Copilot")


@app.get("/health")
def health():
    return {"status": "ok"}
