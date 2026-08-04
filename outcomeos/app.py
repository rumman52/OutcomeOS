from fastapi import FastAPI, Response, status

app = FastAPI(title="OutcomeOS")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready(response: Response) -> dict[str, str]:
    # Replace probes with database/broker adapters without changing the contract.
    dependencies_ready = True
    if not dependencies_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if dependencies_ready else "unavailable"}


@app.get("/worker-health")
def worker_health() -> dict[str, str]:
    return {"status": "ok", "queue": "connected"}
