import importlib.util

import pytest

if importlib.util.find_spec("httpx") is None:
    pytest.skip("httpx is unavailable in this execution environment", allow_module_level=True)

from fastapi.testclient import TestClient

from outcomeos_api.main import app


def test_health() -> None:
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
