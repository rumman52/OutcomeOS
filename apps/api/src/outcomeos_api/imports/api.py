# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import text

from outcomeos_api.auth.api_keys import ApiKeyHasher
from outcomeos_api.auth.service import principal_for_api_key
from outcomeos_api.config import Settings
from outcomeos_api.db import AuthenticatedPrincipal, TenantAccessError, tenant_transaction
from outcomeos_api.imports.csv import CsvLimits, parse_csv_v1
from outcomeos_api.storage import ObjectStorage


def csv_import_router(settings: Settings, sessions: Any, storage: ObjectStorage) -> APIRouter:
    router = APIRouter(tags=["csv-imports"])

    def authenticate(
        authorization: Annotated[str | None, Header()] = None,
    ) -> tuple[Any, AuthenticatedPrincipal]:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(403, "imports:write permission required")
        session = sessions()
        try:
            principal = principal_for_api_key(
                session,
                plaintext=authorization[7:],
                required_scope="imports:write",
                hasher=ApiKeyHasher(settings.api_key_pepper),
            )
            session.rollback()
            return session, principal
        except TenantAccessError as error:
            session.close()
            raise HTTPException(403, "imports:write permission required") from error

    @router.post("/api/v1/imports/csv", status_code=202)
    async def upload(
        request: Request,
        idempotency_key: Annotated[
            str, Header(alias="Idempotency-Key", min_length=1, max_length=255)
        ],
        auth: tuple[Any, AuthenticatedPrincipal] = Depends(authenticate),
    ) -> dict[str, Any]:
        session, actor = auth
        body = await request.body()
        if request.headers.get("content-type", "").split(";", 1)[0].lower() != "text/csv":
            session.close()
            raise HTTPException(415, "text/csv required")
        limits = CsvLimits(
            settings.csv_max_bytes,
            settings.csv_max_rows,
            settings.csv_max_columns,
            settings.csv_max_field_length,
        )
        try:
            parse_csv_v1(body, limits)
        except ValueError as error:
            session.close()
            raise HTTPException(422, str(error)) from error
        digest = hashlib.sha256(body).digest()
        import_id, event_id, now = uuid4(), uuid4(), datetime.now(UTC)
        object_key = f"imports/csv/{import_id}.csv"
        uploaded = False
        try:
            with tenant_transaction(session, actor):
                old = (
                    session.execute(
                        text(
                            "SELECT id,request_digest FROM csv_imports WHERE tenant_id=:t AND idempotency_key=:k"
                        ),
                        {"t": actor.tenant_id, "k": idempotency_key},
                    )
                    .mappings()
                    .one_or_none()
                )
                if old:
                    if bytes(old["request_digest"]) != digest:
                        raise HTTPException(409, "idempotency key conflicts with prior request")
                    return {"import_id": old["id"], "duplicate": True}
                storage.put_if_absent(actor.tenant_id, object_key, body, digest.hex())
                uploaded = True
                session.execute(
                    text("""INSERT INTO csv_imports
                    (id,created_at,tenant_id,idempotency_key,object_key,object_digest,request_digest,state)
                    VALUES(:id,:n,:t,:key,:object,:digest,:digest,'uploaded')"""),
                    {
                        "id": import_id,
                        "n": now,
                        "t": actor.tenant_id,
                        "key": idempotency_key,
                        "object": object_key,
                        "digest": digest,
                    },
                )
                payload = json.dumps({"import_id": str(import_id)}, separators=(",", ":"))
                session.execute(
                    text("""INSERT INTO canonical_events
                    (id,created_at,tenant_id,event_type,event_version,occurred_at,payload,payload_digest)
                    VALUES(:id,:n,:t,'outcomeos.csv.uploaded',1,:n,CAST(:p AS jsonb),:d)"""),
                    {
                        "id": event_id,
                        "n": now,
                        "t": actor.tenant_id,
                        "p": payload,
                        "d": hashlib.sha256(payload.encode()).digest(),
                    },
                )
                session.execute(
                    text("""INSERT INTO outbox_jobs
                    (id,created_at,tenant_id,event_id,kind,state,available_at,attempt_count)
                    VALUES(:id,:n,:t,:event,'ingest.csv.v1','pending',:n,0)"""),
                    {"id": uuid4(), "n": now, "t": actor.tenant_id, "event": event_id},
                )
            return {"import_id": import_id, "duplicate": False}
        except HTTPException:
            raise
        except Exception:
            if uploaded:
                storage.delete(actor.tenant_id, object_key)
            raise
        finally:
            session.close()

    @router.get("/api/v1/imports/csv/{import_id}")
    def status(
        import_id: UUID,
        auth: tuple[Any, AuthenticatedPrincipal] = Depends(authenticate),
    ) -> dict[str, Any]:
        session, actor = auth
        try:
            with tenant_transaction(session, actor):
                row = (
                    session.execute(
                        text("""SELECT id,state,total_rows,accepted_rows,rejected_rows
                    FROM csv_imports WHERE tenant_id=:t AND id=:id"""),
                        {"t": actor.tenant_id, "id": import_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise HTTPException(404, "CSV import not found")
                return dict(row)
        finally:
            session.close()

    return router
