from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import Mock

import psycopg
import pytest
from fastapi.testclient import TestClient

from outcomeos_api import main

client = TestClient(main.app)


@pytest.mark.e2e
def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_when_database_responds(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = Mock()

    @contextmanager
    def connected() -> Iterator[Mock]:
        yield connection

    monkeypatch.setattr(main, "database_connection", connected)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "dependencies": {"postgres": "ok"}}
    connection.execute.assert_called_once_with("SELECT 1")


def test_not_ready_when_database_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    @contextmanager
    def disconnected() -> Iterator[Mock]:
        raise psycopg.OperationalError("unavailable")
        yield Mock()

    monkeypatch.setattr(main, "database_connection", disconnected)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["dependencies"]["postgres"] == "unavailable"
