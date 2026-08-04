from fastapi import FastAPI

from outcomeos_api.config import get_settings

settings = get_settings()
app = FastAPI(title="OutcomeOS API", version="0.1.0")


@app.get("/healthz", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


@app.get("/health", tags=["operations"])
def health_alias() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["operations"])
def readiness() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/worker-health", tags=["operations"])
def worker_health() -> dict[str, str]:
    return {"status": "ok", "queue": "connected"}
