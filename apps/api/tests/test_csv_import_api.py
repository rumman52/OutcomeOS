# mypy: disable-error-code="no-untyped-call"
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from outcomeos_api.config import Settings
from outcomeos_api.db import AuthenticatedPrincipal
from outcomeos_api.imports import CSV_V1_HEADERS
from outcomeos_api.imports.api import csv_import_router
from outcomeos_api.storage import ObjectHead


class Result:
    def __init__(self, value=None):  # type: ignore[no-untyped-def]
        self.value = value

    def mappings(self) -> "Result":
        return self

    def one_or_none(self):  # type: ignore[no-untyped-def]
        return self.value


class Session:
    bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    def __init__(self, values: list[object]) -> None:
        self.values = values
        self.info: dict[str, object] = {}
        self.closed = False

    def begin(self):  # type: ignore[no-untyped-def]
        return nullcontext()

    def in_transaction(self) -> bool:
        return False

    def execute(self, _query, _params=None):  # type: ignore[no-untyped-def]
        return Result(self.values.pop(0) if self.values else None)

    def close(self) -> None:
        self.closed = True

    def rollback(self) -> None:
        return None


class Storage:
    def __init__(self) -> None:
        self.puts: list[tuple[UUID, str, bytes, str]] = []
        self.deletes: list[str] = []

    def put_if_absent(self, tenant_id: UUID, key: str, body: bytes, sha256: str) -> ObjectHead:
        self.puts.append((tenant_id, key, body, sha256))
        return ObjectHead(len(body), sha256)

    def delete(self, _tenant_id: UUID, key: str) -> None:
        self.deletes.append(key)

    def read(self, _tenant_id: UUID, _key: str) -> bytes:
        raise NotImplementedError

    def head(self, _tenant_id: UUID, _key: str) -> ObjectHead:
        raise NotImplementedError


def csv() -> bytes:
    row = (
        "evt-1,order.created,2026-08-15T00:00:00Z,order,ord-1,true,false,"
        'purpose,{},{},100,USD,"{""safe"":true}"\n'
    )
    return ((",".join(CSV_V1_HEADERS)) + "\n" + row).encode()


def client_for(session: Session, storage: Storage) -> TestClient:
    app = FastAPI()
    app.include_router(csv_import_router(Settings(app_env="test"), lambda: session, storage))
    principal = AuthenticatedPrincipal(uuid4(), uuid4(), uuid4())
    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        if dependant and dependant.dependencies:
            app.dependency_overrides[dependant.dependencies[0].call] = lambda: (session, principal)
    return TestClient(app)


def test_csv_upload_persists_encrypted_object_control_event_and_job() -> None:
    session, storage = Session([None]), Storage()
    response = client_for(session, storage).post(
        "/api/v1/imports/csv",
        content=csv(),
        headers={"Content-Type": "text/csv", "Idempotency-Key": "csv-1"},
    )
    assert response.status_code == 202
    assert response.json()["duplicate"] is False
    assert storage.puts[0][2] == csv()
    assert session.closed


def test_csv_upload_rejects_content_type_and_invalid_csv() -> None:
    wrong = client_for(Session([]), Storage()).post(
        "/api/v1/imports/csv",
        content=csv(),
        headers={"Content-Type": "application/json", "Idempotency-Key": "csv-1"},
    )
    assert wrong.status_code == 415
    invalid = client_for(Session([]), Storage()).post(
        "/api/v1/imports/csv",
        content=b"bad",
        headers={"Content-Type": "text/csv", "Idempotency-Key": "csv-2"},
    )
    assert invalid.status_code == 422


def test_csv_status_is_tenant_scoped() -> None:
    import_id = uuid4()
    row = {
        "id": import_id,
        "state": "completed",
        "total_rows": 2,
        "accepted_rows": 1,
        "rejected_rows": 1,
    }
    assert (
        client_for(Session([row]), Storage())
        .get(f"/api/v1/imports/csv/{import_id}")
        .json()["accepted_rows"]
        == 1
    )
    assert (
        client_for(Session([None]), Storage()).get(f"/api/v1/imports/csv/{uuid4()}").status_code
        == 404
    )


def test_csv_api_authenticates_import_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    session, storage = Session([None]), Storage()
    principal = AuthenticatedPrincipal(uuid4(), uuid4(), uuid4())
    monkeypatch.setattr(
        "outcomeos_api.imports.api.principal_for_api_key", lambda *_args, **_kwargs: principal
    )
    app = FastAPI()
    app.include_router(csv_import_router(Settings(app_env="test"), lambda: session, storage))
    response = TestClient(app).post(
        "/api/v1/imports/csv",
        content=csv(),
        headers={
            "Authorization": "Bearer import-key",
            "Content-Type": "text/csv",
            "Idempotency-Key": "authenticated-import",
        },
    )
    assert response.status_code == 202
