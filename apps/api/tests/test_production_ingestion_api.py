import base64
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from outcomeos_api.config import Settings
from outcomeos_api.db import AuthenticatedPrincipal
from outcomeos_api.ingestion.api import public_webhook_router
from outcomeos_api.ingestion.signatures import sign
from outcomeos_api.integrations.api import management_router
from outcomeos_api.integrations.secrets import SecretCipher


def configured() -> Settings:
    key = base64.b64encode(b"k" * 32).decode()
    return Settings(
        app_env="test",
        integration_keyring=f"current:{key}",
        integration_active_key_id="current",
        api_key_pepper="fixture-pepper-long-enough",  # pragma: allowlist secret
        webhook_max_body_bytes=1000,
    )


class Result:
    def __init__(self, rows: list[dict[str, Any]] | None = None, rowcount: int = 1) -> None:
        self.rows = rows or []
        self.rowcount = rowcount

    def mappings(self) -> "Result":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self.rows

    def one_or_none(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class Bind:
    class Dialect:
        name = "postgresql"

    dialect = Dialect()


class FakeSession:
    bind = Bind()

    def __init__(self, endpoint: dict[str, Any] | None = None) -> None:
        self.endpoint = endpoint
        self.closed = False
        self.info: dict[str, Any] = {}
        self.version = 1

    def execute(self, statement: Any, values: dict[str, Any] | None = None) -> Result:
        sql = str(statement)
        if "SELECT id, provider" in sql:
            return Result([self.endpoint] if self.endpoint else [])
        if "SELECT version, expires_at" in sql:
            return Result([{"version": self.version, "expires_at": datetime.now(UTC)}])
        if "UPDATE integration_endpoints" in sql:
            if self.endpoint:
                assert values is not None
                self.endpoint["status"] = values["status"]
                self.endpoint["revoked_at"] = (
                    values["now"] if values["status"] == "revoked" else None
                )
            return Result(rowcount=1 if self.endpoint else 0)
        return Result()

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


def test_management_http_routes_and_authorization(monkeypatch: Any) -> None:
    import outcomeos_api.integrations.api as module

    tenant, user, membership = uuid4(), uuid4(), uuid4()
    principal = AuthenticatedPrincipal(user, tenant, membership)
    endpoint = {
        "id": uuid4(),
        "provider": "neutral",
        "name": "Orders",
        "status": "active",
        "created_at": datetime.now(UTC),
        "revoked_at": None,
    }
    sessions: list[FakeSession] = []

    def factory() -> FakeSession:
        session = FakeSession(endpoint)
        sessions.append(session)
        return session

    monkeypatch.setattr(module, "principal_for_api_key", lambda *args, **kwargs: principal)

    @contextmanager
    def transaction(session: FakeSession, actor: AuthenticatedPrincipal) -> Any:
        yield session

    monkeypatch.setattr(module, "tenant_transaction", transaction)
    app = FastAPI()
    app.include_router(management_router(configured(), factory))
    client = TestClient(app)
    assert client.get("/api/v1/integration-endpoints").status_code == 403
    headers = {"Authorization": "Bearer fixture"}
    assert client.get("/api/v1/integration-endpoints", headers=headers).status_code == 200
    assert (
        client.get(f"/api/v1/integration-endpoints/{endpoint['id']}", headers=headers).status_code
        == 200
    )
    created = client.post(
        "/api/v1/integration-endpoints",
        headers=headers,
        json={"provider": "neutral", "name": "New"},
    )
    assert created.status_code == 201
    assert set(created.json()) >= {"public_token", "signing_secret"}
    rotated = client.post(f"/api/v1/integration-endpoints/{endpoint['id']}/rotate", headers=headers)
    assert rotated.status_code == 200 and rotated.json()["version"] == 2
    disabled = client.post(
        f"/api/v1/integration-endpoints/{endpoint['id']}/status",
        headers=headers,
        json={"action": "revoke"},
    )
    assert disabled.status_code == 200 and disabled.json()["status"] == "revoked"
    # Management representations never expose persisted cryptographic material.
    assert not ({"key_id", "nonce", "ciphertext", "public_token_digest"} & disabled.json().keys())


class ContextSession:
    bind = Bind()

    def __init__(self, rows: list[dict[str, Any]], existing: dict[str, Any] | None = None) -> None:
        self.rows, self.existing = rows, existing

    def __enter__(self) -> "ContextSession":
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def begin(self) -> "ContextSession":
        return self

    def execute(self, statement: Any, values: dict[str, Any] | None = None) -> Result:
        sql = str(statement)
        if "resolve_integration_endpoint" in sql:
            return Result(self.rows)
        if "SELECT r.id receipt_id" in sql:
            return Result([self.existing] if self.existing else [])
        return Result()

    def close(self) -> None:
        pass


class Storage:
    def __init__(self) -> None:
        self.objects: dict[tuple[Any, str], bytes] = {}

    def put_if_absent(self, tenant_id: Any, key: str, body: bytes, sha256: str) -> Any:
        self.objects[(tenant_id, key)] = body

    def delete(self, tenant_id: Any, key: str) -> None:
        self.objects.pop((tenant_id, key), None)

    def read(self, tenant_id: Any, key: str) -> bytes:
        return self.objects[(tenant_id, key)]

    def head(self, tenant_id: Any, key: str) -> Any:
        raise NotImplementedError


def test_public_webhook_exact_bytes_validation_and_persistence() -> None:
    settings = configured()
    tenant, endpoint = uuid4(), uuid4()
    plaintext = b"signing-secret"
    cipher = SecretCipher(settings.parsed_integration_keyring(), "current")
    encrypted = cipher.encrypt(plaintext, tenant_id=tenant, endpoint_id=endpoint, version=1)
    row = {
        "tenant_id": tenant,
        "endpoint_id": endpoint,
        "provider": "neutral",
        "version": 1,
        "key_id": encrypted.key_id,
        "nonce": encrypted.nonce,
        "ciphertext": encrypted.ciphertext,
        "not_before": datetime.now(UTC) - timedelta(1),
        "expires_at": datetime.now(UTC) + timedelta(1),
    }
    storage = Storage()

    def ingress() -> ContextSession:
        return ContextSession([row])

    def writes() -> ContextSession:
        return ContextSession([])

    app = FastAPI()
    app.include_router(public_webhook_router(settings, ingress, writes, storage))
    client = TestClient(app)
    body = (
        b'{"provider_event_id":"evt_1","event_type":"order.created",'
        b'"occurred_at":"2026-08-14T00:00:00Z","subject_type":"order",'
        b'"subject_id":"ord_1","consent":{"processing_permitted":true,'
        b'"purpose":"order"},"payload":{"answer":42}}'
    )
    timestamp = str(int(datetime.now(UTC).timestamp()))
    headers = {
        "X-OutcomeOS-Timestamp": timestamp,
        "X-OutcomeOS-Signature": f"v1={sign(plaintext, timestamp.encode(), body)}",
    }
    response = client.post("/api/v1/webhooks/token", content=body, headers=headers)
    assert response.status_code == 202 and response.json()["duplicate"] is False
    assert next(iter(storage.objects.values())) == body
    assert (
        client.post("/api/v1/webhooks/token", content=body + b" ", headers=headers).status_code
        == 401
    )
    assert client.post("/api/v1/webhooks/token", content=b"{", headers=headers).status_code == 401


def test_public_webhook_unknown_headers_schema_and_size() -> None:
    settings = configured()
    app = FastAPI()
    app.include_router(
        public_webhook_router(
            settings, lambda: ContextSession([]), lambda: ContextSession([]), Storage()
        )
    )
    client = TestClient(app)
    assert client.post("/api/v1/webhooks/unknown", content=b"{}").status_code == 401
    assert client.post("/api/v1/webhooks/unknown", content=b"x" * 1001).status_code == 413
