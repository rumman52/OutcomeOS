from fastapi.testclient import TestClient

from outcomeos.app import app


def test_operational_endpoints() -> None:
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}
    assert client.get("/worker-health").json() == {"status": "ok", "queue": "connected"}
