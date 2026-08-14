from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from outcomeos_api.config import Settings
from outcomeos_api.events.schemas import CanonicalEvent, PublicEventInput
from outcomeos_api.ingestion.signatures import SignatureError, authenticate
from outcomeos_api.integrations.endpoints import token_digest
from outcomeos_api.integrations.secrets import EncryptedSecret, SecretCipher
from outcomeos_api.storage import ObjectStorage

AUTH_ERROR = "invalid webhook authentication"


async def _bounded_raw_body(request: Request, maximum: int) -> bytes:
    chunks: list[bytes] = []
    length = 0
    async for chunk in request.stream():
        length += len(chunk)
        if length > maximum:
            raise HTTPException(413, "webhook body is too large")
        chunks.append(chunk)
    return b"".join(chunks)


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def public_webhook_router(
    settings: Settings, ingress_sessions: Any, write_sessions: Any, storage: ObjectStorage
) -> APIRouter:
    router = APIRouter(tags=["webhooks"])
    cipher = SecretCipher(
        settings.parsed_integration_keyring(), settings.integration_active_key_id or ""
    )

    def resolve(token: str) -> list[Any]:
        with ingress_sessions() as session, session.begin():
            if session.bind is not None and session.bind.dialect.name == "postgresql":
                session.execute(text("SET LOCAL ROLE outcomeos_ingress"))
            return list(
                session.execute(
                    text("SELECT * FROM public.resolve_integration_endpoint(:digest)"),
                    {"digest": token_digest(token)},
                )
                .mappings()
                .all()
            )

    @router.post("/api/v1/webhooks/{public_token}", status_code=202)
    async def receive(public_token: str, request: Request) -> dict[str, Any]:
        body = await _bounded_raw_body(request, settings.webhook_max_body_bytes)
        timestamp_values = request.headers.getlist("X-OutcomeOS-Timestamp")
        signature_values = request.headers.getlist("X-OutcomeOS-Signature")
        if len(timestamp_values) != 1:
            raise HTTPException(401, AUTH_ERROR)
        try:
            resolved = resolve(public_token)
            if not resolved:
                raise SignatureError(AUTH_ERROR)
            tenant_id = UUID(str(resolved[0]["tenant_id"]))
            endpoint_id = UUID(str(resolved[0]["endpoint_id"]))
            secrets = [
                cipher.decrypt(
                    EncryptedSecret(row["key_id"], bytes(row["nonce"]), bytes(row["ciphertext"])),
                    tenant_id=tenant_id,
                    endpoint_id=endpoint_id,
                    version=int(row["version"]),
                )
                for row in resolved
            ]
            authenticate(
                secrets=secrets,
                timestamp_header=timestamp_values[0].encode("ascii"),
                signature_headers=signature_values,
                body=body,
                replay_window_seconds=settings.webhook_replay_window_seconds,
            )
        except (SignatureError, UnicodeEncodeError, SQLAlchemyError, ValueError) as error:
            raise HTTPException(401, AUTH_ERROR) from error

        try:
            decoded = json.loads(body)
            if not isinstance(decoded, dict):
                raise ValueError
            incoming = PublicEventInput.model_validate(decoded)
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, ValueError) as error:
            raise HTTPException(422, "invalid webhook event") from error

        raw_digest = hashlib.sha256(body).digest()
        now = datetime.now(UTC)
        event_id, receipt_id, job_id = uuid4(), uuid4(), uuid4()
        canonical = CanonicalEvent(
            event_id=event_id,
            tenant_id=tenant_id,
            provider=str(resolved[0]["provider"]),
            source_type="public_webhook",
            provider_event_id=incoming.provider_event_id,
            payload_digest="0" * 64,
            event_type=incoming.event_type,
            occurred_at=incoming.occurred_at,
            received_at=now,
            subject_type=incoming.subject_type,
            subject_id=incoming.subject_id,
            references=incoming.references,
            attribution=incoming.attribution,
            money=incoming.money,
            consent=incoming.consent,
            payload=incoming.payload,
            raw_payload_digest=raw_digest.hex(),
        )
        canonical_data = canonical.model_dump(mode="json")
        canonical_data["payload_digest"] = hashlib.sha256(
            _canonical_json(
                {
                    key: value
                    for key, value in canonical_data.items()
                    if key not in {"event_id", "received_at", "payload_digest", "raw_object_key"}
                }
            )
        ).hexdigest()
        identity_digest = hashlib.sha256(incoming.provider_event_id.encode()).hexdigest()
        object_key = f"webhooks/{endpoint_id}/{identity_digest}.json"
        canonical_data["raw_object_key"] = object_key

        session: Session = write_sessions()
        uploaded = False
        try:
            with session.begin():
                session.execute(
                    text("SELECT set_config('app.tenant_id', :tenant, true)"),
                    {"tenant": str(tenant_id)},
                )
                # Serialize the provider identity before checking or creating any durable resource.
                session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                    {"key": f"{tenant_id}:{endpoint_id}:{incoming.provider_event_id}"},
                )
                existing = (
                    session.execute(
                        text("""SELECT r.id receipt_id, e.id event_id, j.id job_id,
                    r.payload_digest FROM webhook_receipts r
                    JOIN canonical_events e ON e.tenant_id=r.tenant_id AND e.receipt_id=r.id
                    JOIN outbox_jobs j ON j.tenant_id=e.tenant_id AND j.event_id=e.id
                    WHERE r.tenant_id=:tenant AND r.endpoint_id=:endpoint
                      AND r.provider_event_id=:provider_event_id"""),
                        {
                            "tenant": tenant_id,
                            "endpoint": endpoint_id,
                            "provider_event_id": incoming.provider_event_id,
                        },
                    )
                    .mappings()
                    .one_or_none()
                )
                if existing is not None:
                    if bytes(existing["payload_digest"]) != raw_digest:
                        raise HTTPException(
                            409, "provider event identity conflicts with prior payload"
                        )
                    return {
                        "receipt_id": existing["receipt_id"],
                        "event_id": existing["event_id"],
                        "job_id": existing["job_id"],
                        "duplicate": True,
                    }
                storage.put_if_absent(tenant_id, object_key, body, raw_digest.hex())
                uploaded = True
                session.execute(
                    text("""INSERT INTO webhook_receipts
                    (id,created_at,tenant_id,endpoint_id,provider_event_id,payload_digest,object_key,received_at)
                    VALUES (:id,:now,:tenant,:endpoint,:provider_event_id,:digest,:key,:now)"""),
                    {
                        "id": receipt_id,
                        "now": now,
                        "tenant": tenant_id,
                        "endpoint": endpoint_id,
                        "provider_event_id": incoming.provider_event_id,
                        "digest": raw_digest,
                        "key": object_key,
                    },
                )
                session.execute(
                    text("""INSERT INTO canonical_events
                    (id,created_at,tenant_id,receipt_id,event_type,event_version,
                     occurred_at,payload,payload_digest)
                    VALUES
                    (:id,:now,:tenant,:receipt,:event_type,1,:occurred_at,
                     CAST(:payload AS jsonb),:digest)"""),
                    {
                        "id": event_id,
                        "now": now,
                        "tenant": tenant_id,
                        "receipt": receipt_id,
                        "event_type": incoming.event_type,
                        "occurred_at": incoming.occurred_at,
                        "payload": json.dumps(canonical_data, separators=(",", ":")),
                        "digest": bytes.fromhex(canonical_data["payload_digest"]),
                    },
                )
                session.execute(
                    text("""INSERT INTO outbox_jobs
                    (id,created_at,tenant_id,event_id,kind,state,available_at,attempt_count)
                    VALUES (:id,:now,:tenant,:event,:kind,'pending',:now,0)"""),
                    {
                        "id": job_id,
                        "now": now,
                        "tenant": tenant_id,
                        "event": event_id,
                        "kind": settings.ingestion_job_kind,
                    },
                )
            return {
                "receipt_id": receipt_id,
                "event_id": event_id,
                "job_id": job_id,
                "duplicate": False,
            }
        except HTTPException:
            raise
        except Exception:
            if uploaded:
                storage.delete(tenant_id, object_key)
            raise
        finally:
            session.close()

    return router
