from __future__ import annotations

import base64
import hashlib
import json
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import boto3
import pytest
from alembic import command
from alembic.config import Config
from botocore.exceptions import ClientError
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from outcomeos_api.auth.api_keys import ApiKeyHasher
from outcomeos_api.config import Settings
from outcomeos_api.ingestion.api import public_webhook_router
from outcomeos_api.ingestion.signatures import sign
from outcomeos_api.integrations.api import management_router
from outcomeos_api.storage import S3ObjectStorage

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def infrastructure() -> Iterator[tuple[Engine, Any, S3ObjectStorage, str]]:
    database_url = os.getenv("INTEGRATION_DATABASE_URL")
    endpoint = os.getenv("INTEGRATION_S3_ENDPOINT_URL")
    access = os.getenv("INTEGRATION_S3_ACCESS_KEY_ID")
    secret = os.getenv("INTEGRATION_S3_SECRET_ACCESS_KEY")
    bucket = os.getenv("INTEGRATION_S3_BUCKET")
    if not database_url:
        pytest.fail("INTEGRATION_DATABASE_URL is required", pytrace=False)
    if not all((endpoint, access, secret, bucket)):
        pytest.fail("all INTEGRATION_S3_* settings are required", pytrace=False)
    assert endpoint is not None and access is not None and secret is not None and bucket is not None
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(database_url, pool_pre_ping=True)
    s3 = boto3.client(
        "s3", endpoint_url=endpoint, aws_access_key_id=access, aws_secret_access_key=secret
    )
    try:
        s3.create_bucket(Bucket=bucket)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") not in {
            "BucketAlreadyOwnedByYou",
            "BucketAlreadyExists",
        }:
            raise
    storage = S3ObjectStorage(
        bucket=bucket,
        endpoint_url=endpoint,
        access_key_id=access,
        secret_access_key=secret,
        max_bytes=100_000,
        client=s3,
    )
    yield engine, s3, storage, bucket
    engine.dispose()


@pytest.fixture(scope="module")
def settings() -> Settings:
    key = base64.b64encode(b"k" * 32).decode()
    return Settings(
        app_env="test",
        integration_keyring=f"current:{key}",
        integration_active_key_id="current",
        api_key_pepper="fixture-pepper-long-enough",  # pragma: allowlist secret
        integration_secret_overlap_seconds=2,
        integration_secret_lifetime_seconds=120,
        webhook_replay_window_seconds=300,
        webhook_max_body_bytes=100_000,
    )


def _provision_api_key(engine: Engine, settings: Settings) -> tuple[UUID, str]:
    tenant_id, user_id, membership_id, key_id = uuid4(), uuid4(), uuid4(), uuid4()
    generated = ApiKeyHasher(settings.api_key_pepper).generate(tenant_id)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO tenants (id,created_at,name) VALUES (:id,now(),:name)"),
            {"id": tenant_id, "name": f"tenant-{tenant_id.hex[:8]}"},
        )
        connection.execute(
            text("INSERT INTO users (id,created_at,email) VALUES (:id,now(),:email)"),
            {"id": user_id, "email": f"{user_id.hex}@example.test"},
        )
        connection.execute(
            text(
                "INSERT INTO memberships "
                "(id,created_at,tenant_id,user_id,role,status) "
                "VALUES (:id,now(),:tenant,:user,'owner','active')"
            ),
            {"id": membership_id, "tenant": tenant_id, "user": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO api_keys "
                "(id,created_at,tenant_id,name,prefix,key_digest,scopes) "
                "VALUES (:id,now(),:tenant,'integration',:prefix,:digest,CAST(:scopes AS jsonb))"
            ),
            {
                "id": key_id,
                "tenant": tenant_id,
                "prefix": generated.prefix,
                "digest": generated.digest,
                "scopes": json.dumps(["integration:manage"]),
            },
        )
    return tenant_id, generated.plaintext


def _management_client(engine: Engine, settings: Settings) -> TestClient:
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(management_router(settings, sessions))
    return TestClient(app)


def _create_endpoint(client: TestClient, api_key: str, name: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/integration-endpoints",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"provider": "neutral", "name": name},
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def _ingress_client(engine: Engine, settings: Settings, storage: S3ObjectStorage) -> TestClient:
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(public_webhook_router(settings, sessions, sessions, storage))
    return TestClient(app)


def _body(event_id: str, answer: int = 42) -> bytes:
    return json.dumps(
        {
            "provider_event_id": event_id,
            "event_type": "order.created",
            "occurred_at": "2026-08-14T00:00:00Z",
            "subject_type": "order",
            "subject_id": "ord-1",
            "consent": {"processing_permitted": True, "purpose": "order"},
            "payload": {"answer": answer},
        },
        separators=(",", ":"),
    ).encode()


def _headers(secret: str, body: bytes) -> dict[str, str]:
    timestamp = str(int(datetime.now(UTC).timestamp()))
    return {
        "X-OutcomeOS-Timestamp": timestamp,
        "X-OutcomeOS-Signature": f"v1={sign(secret.encode(), timestamp.encode(), body)}",
        "Content-Type": "application/json",
    }


def test_real_endpoint_lifecycle_and_cross_tenant_denial(
    infrastructure: tuple[Engine, Any, S3ObjectStorage, str], settings: Settings
) -> None:
    engine = infrastructure[0]
    tenant_a, key_a = _provision_api_key(engine, settings)
    tenant_b, key_b = _provision_api_key(engine, settings)
    client = _management_client(engine, settings)
    endpoint = _create_endpoint(client, key_a, "lifecycle")
    endpoint_id = endpoint["id"]
    headers_a = {"Authorization": f"Bearer {key_a}"}
    headers_b = {"Authorization": f"Bearer {key_b}"}

    listed = client.get("/api/v1/integration-endpoints", headers=headers_a)
    assert listed.status_code == 200 and [item["id"] for item in listed.json()] == [endpoint_id]
    assert (
        client.get(f"/api/v1/integration-endpoints/{endpoint_id}", headers=headers_a).status_code
        == 200
    )
    assert (
        client.get(f"/api/v1/integration-endpoints/{endpoint_id}", headers=headers_b).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/integration-endpoints/{endpoint_id}/rotate", headers=headers_b
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/integration-endpoints/{endpoint_id}/status",
            headers=headers_b,
            json={"action": "disable"},
        ).status_code
        == 404
    )
    assert client.get("/api/v1/integration-endpoints", headers=headers_b).json() == []

    rotated = client.post(f"/api/v1/integration-endpoints/{endpoint_id}/rotate", headers=headers_a)
    assert rotated.status_code == 200 and rotated.json()["version"] == 2
    disabled = client.post(
        f"/api/v1/integration-endpoints/{endpoint_id}/status",
        headers=headers_a,
        json={"action": "disable"},
    )
    assert disabled.status_code == 200 and disabled.json()["status"] == "disabled"
    revoked_endpoint = _create_endpoint(client, key_a, "revoke")
    revoked = client.post(
        f"/api/v1/integration-endpoints/{revoked_endpoint['id']}/status",
        headers=headers_a,
        json={"action": "revoke"},
    )
    assert revoked.status_code == 200 and revoked.json()["status"] == "revoked"
    assert revoked.json()["revoked_at"] is not None
    assert tenant_a != tenant_b


def test_ingress_role_can_only_execute_restricted_resolver(
    infrastructure: tuple[Engine, Any, S3ObjectStorage, str], settings: Settings
) -> None:
    engine = infrastructure[0]
    _, api_key = _provision_api_key(engine, settings)
    endpoint = _create_endpoint(_management_client(engine, settings), api_key, "resolver")
    digest = hashlib.sha256(endpoint["public_token"].encode()).digest()
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text("SET LOCAL ROLE outcomeos_ingress"))
        rows = (
            connection.execute(
                text("SELECT * FROM public.resolve_integration_endpoint(:digest)"),
                {"digest": digest},
            )
            .mappings()
            .all()
        )
        assert len(rows) == 1 and str(rows[0]["endpoint_id"]) == endpoint["id"]
        with pytest.raises(DBAPIError, match="permission denied"):
            connection.execute(text("SELECT * FROM integration_endpoints"))
        transaction.rollback()


def test_exact_bytes_rotation_expiration_atomic_persistence_and_encrypted_evidence(
    infrastructure: tuple[Engine, Any, S3ObjectStorage, str], settings: Settings
) -> None:
    engine, s3, storage, bucket = infrastructure
    tenant_id, api_key = _provision_api_key(engine, settings)
    management = _management_client(engine, settings)
    endpoint = _create_endpoint(management, api_key, "authenticated-ingress")
    ingress = _ingress_client(engine, settings, storage)
    body = _body(f"exact-{uuid4()}")

    accepted = ingress.post(
        f"/api/v1/webhooks/{endpoint['public_token']}",
        content=body,
        headers=_headers(endpoint["signing_secret"], body),
    )
    assert accepted.status_code == 202 and accepted.json()["duplicate"] is False
    altered = body + b" "
    assert (
        ingress.post(
            f"/api/v1/webhooks/{endpoint['public_token']}",
            content=altered,
            headers=_headers(endpoint["signing_secret"], body),
        ).status_code
        == 401
    )

    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    "SELECT r.object_key,r.payload_digest,e.payload,j.kind "
                    "FROM webhook_receipts r JOIN canonical_events e "
                    "ON e.tenant_id=r.tenant_id AND e.receipt_id=r.id "
                    "JOIN outbox_jobs j ON j.tenant_id=e.tenant_id AND j.event_id=e.id "
                    "WHERE r.tenant_id=:tenant AND r.id=:receipt"
                ),
                {"tenant": tenant_id, "receipt": accepted.json()["receipt_id"]},
            )
            .mappings()
            .one()
        )
    assert bytes(row["payload_digest"]) == hashlib.sha256(body).digest()
    assert row["payload"]["raw_payload_digest"] == hashlib.sha256(body).hexdigest()
    assert row["kind"] == settings.ingestion_job_kind
    assert storage.read(tenant_id, row["object_key"]) == body
    object_metadata = s3.head_object(Bucket=bucket, Key=f"tenants/{tenant_id}/{row['object_key']}")
    assert object_metadata["ServerSideEncryption"] == "AES256"

    rotation = management.post(
        f"/api/v1/integration-endpoints/{endpoint['id']}/rotate",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert rotation.status_code == 200
    overlap_body = _body(f"overlap-{uuid4()}")
    assert (
        ingress.post(
            f"/api/v1/webhooks/{endpoint['public_token']}",
            content=overlap_body,
            headers=_headers(endpoint["signing_secret"], overlap_body),
        ).status_code
        == 202
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE integration_secret_versions SET expires_at=now() "
                "WHERE tenant_id=:tenant AND endpoint_id=:endpoint AND version=1"
            ),
            {"tenant": tenant_id, "endpoint": endpoint["id"]},
        )
    expired_body = _body(f"expired-{uuid4()}")
    assert (
        ingress.post(
            f"/api/v1/webhooks/{endpoint['public_token']}",
            content=expired_body,
            headers=_headers(endpoint["signing_secret"], expired_body),
        ).status_code
        == 401
    )
    assert (
        ingress.post(
            f"/api/v1/webhooks/{endpoint['public_token']}",
            content=expired_body,
            headers=_headers(rotation.json()["signing_secret"], expired_body),
        ).status_code
        == 202
    )


def test_identical_conflicting_and_concurrent_deliveries(
    infrastructure: tuple[Engine, Any, S3ObjectStorage, str], settings: Settings
) -> None:
    engine, _, storage, _ = infrastructure
    _, api_key = _provision_api_key(engine, settings)
    endpoint = _create_endpoint(_management_client(engine, settings), api_key, "idempotency")
    ingress = _ingress_client(engine, settings, storage)
    body = _body(f"duplicate-{uuid4()}")
    url = f"/api/v1/webhooks/{endpoint['public_token']}"
    first = ingress.post(url, content=body, headers=_headers(endpoint["signing_secret"], body))
    duplicate = ingress.post(url, content=body, headers=_headers(endpoint["signing_secret"], body))
    assert first.status_code == duplicate.status_code == 202
    assert duplicate.json() == {**first.json(), "duplicate": True}
    conflicting = _body(json.loads(body)["provider_event_id"], answer=99)
    assert (
        ingress.post(
            url,
            content=conflicting,
            headers=_headers(endpoint["signing_secret"], conflicting),
        ).status_code
        == 409
    )

    concurrent = _body(f"concurrent-{uuid4()}")
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: ingress.post(
                    url,
                    content=concurrent,
                    headers=_headers(endpoint["signing_secret"], concurrent),
                ),
                range(2),
            )
        )
    assert [response.status_code for response in responses] == [202, 202]
    assert sorted(response.json()["duplicate"] for response in responses) == [False, True]
    identities = {
        (response.json()["receipt_id"], response.json()["event_id"], response.json()["job_id"])
        for response in responses
    }
    assert len(identities) == 1


def test_database_rollback_removes_s3_object(
    infrastructure: tuple[Engine, Any, S3ObjectStorage, str], settings: Settings
) -> None:
    engine, _, storage, _ = infrastructure
    tenant_id, api_key = _provision_api_key(engine, settings)
    endpoint = _create_endpoint(_management_client(engine, settings), api_key, "rollback")
    invalid_settings = settings.model_copy(update={"ingestion_job_kind": "x" * 81})
    ingress = _ingress_client(engine, invalid_settings, storage)
    provider_event_id = f"rollback-{uuid4()}"
    body = _body(provider_event_id)
    with pytest.raises(DBAPIError):
        ingress.post(
            f"/api/v1/webhooks/{endpoint['public_token']}",
            content=body,
            headers=_headers(endpoint["signing_secret"], body),
        )
    identity_digest = hashlib.sha256(provider_event_id.encode()).hexdigest()
    object_key = f"webhooks/{endpoint['id']}/{identity_digest}.json"
    with pytest.raises(ClientError):
        storage.head(tenant_id, object_key)
    with engine.connect() as connection:
        counts = (
            connection.execute(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM webhook_receipts WHERE tenant_id=:tenant) receipts,"
                    "(SELECT count(*) FROM canonical_events WHERE tenant_id=:tenant) events,"
                    "(SELECT count(*) FROM outbox_jobs WHERE tenant_id=:tenant) jobs"
                ),
                {"tenant": tenant_id},
            )
            .mappings()
            .one()
        )
    assert dict(counts) == {"receipts": 0, "events": 0, "jobs": 0}
