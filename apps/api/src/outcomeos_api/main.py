from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from fastapi import FastAPI, Response, status

from outcomeos_api.config import get_settings

settings = get_settings()
app = FastAPI(title="OutcomeOS API", version="0.1.0")


@contextmanager
def database_connection() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """Open the short-lived connection used by the readiness probe."""
    with psycopg.connect(settings.database_url, connect_timeout=2) as connection:
        yield connection


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


@app.get("/ready", tags=["operations"])
def ready(response: Response) -> dict[str, object]:
    try:
        with database_connection() as connection:
            connection.execute("SELECT 1")
    except psycopg.Error:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not ready", "dependencies": {"postgres": "unavailable"}}
    return {"status": "ready", "dependencies": {"postgres": "ok"}}
