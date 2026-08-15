# ruff: noqa: E501
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from outcomeos_api.config import Settings
from outcomeos_api.main import create_app


@pytest.mark.parametrize(
    "row,expected,status",
    [
        ({"observed_at": datetime.now(UTC), "status": "healthy"}, "healthy", 200),
        ({"observed_at": datetime.now(UTC), "status": "draining"}, "draining", 503),
        (
            {"observed_at": datetime.now(UTC) - timedelta(hours=1), "status": "healthy"},
            "stale",
            503,
        ),
        (None, "missing", 503),
    ],
)
def test_worker_health_fails_closed_without_fresh_healthy_heartbeat(
    monkeypatch: pytest.MonkeyPatch,
    row: dict[str, object] | None,
    expected: str,
    status: int,
) -> None:
    result = MagicMock()
    result.mappings.return_value.one_or_none.return_value = row
    connection = MagicMock()
    connection.execute.return_value = result
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr("outcomeos_api.main.create_database_engine", lambda _url: engine)
    response = TestClient(create_app(Settings(app_env="test"))).get("/worker-health")
    assert response.status_code == status
    assert response.json()["status"] == expected


def test_worker_health_reports_database_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy.exc import OperationalError

    def unavailable(_url: str) -> None:
        raise OperationalError("connect", {}, Exception("offline"))

    monkeypatch.setattr("outcomeos_api.main.create_database_engine", unavailable)
    response = TestClient(create_app(Settings(app_env="test"))).get("/worker-health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "worker": "unavailable"}


@pytest.mark.parametrize(
    "revision,status",
    [("20260815_0009", 200), ("20260815_0008", 503), (None, 503)],
)
def test_readiness_requires_exact_migration_head(
    monkeypatch: pytest.MonkeyPatch, revision: str | None, status: int
) -> None:
    connection = MagicMock()
    ping, migration = MagicMock(), MagicMock()
    migration.scalar_one_or_none.return_value = revision
    connection.execute.side_effect = [ping, migration]
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr("outcomeos_api.main.create_database_engine", lambda _url: engine)
    response = TestClient(create_app(Settings(app_env="test"))).get("/ready")
    assert response.status_code == status
    assert response.json()["migration"] == (revision or "missing")


def test_readiness_fails_closed_when_database_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy.exc import OperationalError

    engine = MagicMock()
    engine.connect.side_effect = OperationalError("connect", {}, Exception("offline"))
    monkeypatch.setattr("outcomeos_api.main.create_database_engine", lambda _url: engine)
    response = TestClient(create_app(Settings(app_env="test"))).get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


def test_sandbox_readiness_reports_explicit_local_backend() -> None:
    response = TestClient(
        create_app(
            Settings(app_env="test", persistence_backend="json_sandbox", demo_auth_enabled=True)
        )
    ).get("/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "json-sandbox"
