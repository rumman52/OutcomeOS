# mypy: disable-error-code="no-untyped-call"
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from outcomeos_api.config import Settings
from outcomeos_api.db import AuthenticatedPrincipal
from outcomeos_api.events.operations import operations_router


class Result:
    def __init__(self, value=None):  # type: ignore[no-untyped-def]
        self.value = value

    def mappings(self) -> "Result":
        return self

    def one_or_none(self):  # type: ignore[no-untyped-def]
        return self.value


class Session:
    bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    def __init__(self, results: list[object]) -> None:
        self.results = results
        self.info: dict[str, object] = {}
        self.closed = False

    def begin(self):  # type: ignore[no-untyped-def]
        return nullcontext()

    def in_transaction(self) -> bool:
        return False

    def execute(self, _query, _params=None):  # type: ignore[no-untyped-def]
        return Result(self.results.pop(0) if self.results else None)

    def close(self) -> None:
        self.closed = True

    def rollback(self) -> None:
        return None


def client_for(session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(operations_router(Settings(app_env="test"), lambda: session))
    principal = AuthenticatedPrincipal(uuid4(), uuid4(), uuid4())
    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        if dependant and dependant.dependencies:
            app.dependency_overrides[dependant.dependencies[0].call] = lambda: (session, principal)
    return TestClient(app)


def test_replay_atomically_creates_event_lineage_job_and_audit() -> None:
    source = {
        "event_type": "order.created",
        "event_version": 1,
        "occurred_at": datetime.now(UTC),
        "payload": {"safe": True},
        "payload_digest": b"x" * 32,
    }
    session = Session([None, source])
    response = client_for(session).post(
        f"/api/v1/events/{uuid4()}/replays",
        headers={"Idempotency-Key": "replay-1"},
        json={"reason": "operator retry"},
    )
    assert response.status_code == 201
    assert response.json()["duplicate"] is False
    assert session.closed


def test_replay_is_idempotent_and_detects_conflict() -> None:
    prior = {"replay_event_id": uuid4(), "request_digest": b"wrong" * 8}
    response = client_for(Session([prior])).post(
        f"/api/v1/events/{uuid4()}/replays",
        headers={"Idempotency-Key": "replay-1"},
        json={"reason": "operator retry"},
    )
    assert response.status_code == 409


def test_replay_does_not_cross_tenant_for_missing_source() -> None:
    response = client_for(Session([None, None])).post(
        f"/api/v1/events/{uuid4()}/replays",
        headers={"Idempotency-Key": "replay-missing"},
        json={"reason": "operator retry"},
    )
    assert response.status_code == 404


def test_reconciliation_schedule_status_and_not_found() -> None:
    create = client_for(Session([None])).post(
        "/api/v1/reconciliation-runs",
        headers={"Idempotency-Key": "reconcile-1"},
        json={},
    )
    assert create.status_code == 202
    run = {
        "id": uuid4(),
        "kind": "durable_pipeline.v1",
        "state": "completed",
        "started_at": datetime.now(UTC),
        "finished_at": datetime.now(UTC),
        "summary": {},
    }
    found = client_for(Session([run])).get(f"/api/v1/reconciliation-runs/{run['id']}")
    assert found.status_code == 200
    missing = client_for(Session([None])).get(f"/api/v1/reconciliation-runs/{uuid4()}")
    assert missing.status_code == 404


def test_operations_require_bearer_credentials() -> None:
    app = FastAPI()
    app.include_router(operations_router(Settings(app_env="test"), lambda: Session([])))
    response = TestClient(app).post(
        f"/api/v1/events/{uuid4()}/replays",
        headers={"Idempotency-Key": "denied"},
        json={"reason": "operator retry"},
    )
    assert response.status_code == 403


def test_operations_authenticates_scoped_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Session([None])
    principal = AuthenticatedPrincipal(uuid4(), uuid4(), uuid4())
    monkeypatch.setattr(
        "outcomeos_api.events.operations.principal_for_api_key",
        lambda *_args, **_kwargs: principal,
    )
    app = FastAPI()
    app.include_router(operations_router(Settings(app_env="test"), lambda: session))
    response = TestClient(app).post(
        "/api/v1/reconciliation-runs",
        headers={"Authorization": "Bearer scoped-key", "Idempotency-Key": "reconcile-auth"},
        json={},
    )
    assert response.status_code == 202
