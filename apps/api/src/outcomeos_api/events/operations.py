# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from outcomeos_api.auth.api_keys import ApiKeyHasher
from outcomeos_api.auth.service import principal_for_api_key
from outcomeos_api.config import Settings
from outcomeos_api.db import AuthenticatedPrincipal, TenantAccessError, tenant_transaction


class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=500)


class ReconciliationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(default="durable_pipeline.v1", pattern=r"^[a-z0-9_.-]{1,80}$")


def operations_router(settings: Settings, sessions: Any) -> APIRouter:
    router = APIRouter(tags=["pipeline-operations"])

    def authenticate(scope: str, authorization: str | None) -> tuple[Any, AuthenticatedPrincipal]:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(403, "operation permission required")
        session = sessions()
        try:
            principal = principal_for_api_key(
                session,
                plaintext=authorization[7:],
                required_scope=scope,
                hasher=ApiKeyHasher(settings.api_key_pepper),
            )
            session.rollback()
            return session, principal
        except TenantAccessError as error:
            session.close()
            raise HTTPException(403, "operation permission required") from error

    def replay_auth(
        authorization: Annotated[str | None, Header()] = None,
    ) -> tuple[Any, AuthenticatedPrincipal]:
        return authenticate("events:replay", authorization)

    def reconciliation_auth(
        authorization: Annotated[str | None, Header()] = None,
    ) -> tuple[Any, AuthenticatedPrincipal]:
        return authenticate("reconciliation:write", authorization)

    @router.post("/api/v1/events/{event_id}/replays", status_code=201)
    def replay(
        event_id: UUID,
        body: ReplayRequest,
        idempotency_key: Annotated[
            str, Header(alias="Idempotency-Key", min_length=1, max_length=255)
        ],
        auth: tuple[Any, AuthenticatedPrincipal] = Depends(replay_auth),
    ) -> dict[str, Any]:
        session, actor = auth
        digest = hashlib.sha256(f"{event_id}:{body.reason}".encode()).digest()
        now, replay_id, lineage_id, job_id = datetime.now(UTC), uuid4(), uuid4(), uuid4()
        try:
            with tenant_transaction(session, actor):
                existing = (
                    session.execute(
                        text(
                            "SELECT replay_event_id,request_digest FROM event_replays WHERE tenant_id=:t AND idempotency_key=:k"
                        ),
                        {"t": actor.tenant_id, "k": idempotency_key},
                    )
                    .mappings()
                    .one_or_none()
                )
                if existing:
                    if bytes(existing["request_digest"]) != digest:
                        raise HTTPException(409, "idempotency key conflicts with prior request")
                    return {"event_id": existing["replay_event_id"], "duplicate": True}
                source = (
                    session.execute(
                        text(
                            "SELECT event_type,event_version,occurred_at,payload,payload_digest FROM canonical_events WHERE tenant_id=:t AND id=:e"
                        ),
                        {"t": actor.tenant_id, "e": event_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if source is None:
                    raise HTTPException(404, "event not found")
                payload = dict(source["payload"])
                payload["replay_source_event_id"] = str(event_id)
                encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
                event_digest = hashlib.sha256(encoded.encode()).digest()
                session.execute(
                    text(
                        "INSERT INTO canonical_events(id,created_at,tenant_id,event_type,event_version,occurred_at,payload,payload_digest) VALUES(:id,:n,:t,:type,:v,:o,CAST(:p AS jsonb),:d)"
                    ),
                    {
                        "id": replay_id,
                        "n": now,
                        "t": actor.tenant_id,
                        "type": source["event_type"],
                        "v": source["event_version"],
                        "o": source["occurred_at"],
                        "p": encoded,
                        "d": event_digest,
                    },
                )
                session.execute(
                    text(
                        "INSERT INTO event_replays(id,created_at,tenant_id,source_event_id,replay_event_id,requested_by_user_id,reason,idempotency_key,request_digest) VALUES(:id,:n,:t,:source,:replay,:user,:reason,:key,:digest)"
                    ),
                    {
                        "id": lineage_id,
                        "n": now,
                        "t": actor.tenant_id,
                        "source": event_id,
                        "replay": replay_id,
                        "user": actor.user_id,
                        "reason": body.reason,
                        "key": idempotency_key,
                        "digest": digest,
                    },
                )
                session.execute(
                    text(
                        "INSERT INTO outbox_jobs(id,created_at,tenant_id,event_id,kind,state,available_at,attempt_count) VALUES(:id,:n,:t,:e,:kind,'pending',:n,0)"
                    ),
                    {
                        "id": job_id,
                        "n": now,
                        "t": actor.tenant_id,
                        "e": replay_id,
                        "kind": settings.ingestion_job_kind,
                    },
                )
                session.execute(
                    text(
                        "INSERT INTO audit_events(id,created_at,tenant_id,actor_user_id,action,resource_type,resource_id,correlation_id,details) VALUES(:id,:n,:t,:u,'event.replay','canonical_event',:r,:c,'{}'::jsonb)"
                    ),
                    {
                        "id": uuid4(),
                        "n": now,
                        "t": actor.tenant_id,
                        "u": actor.user_id,
                        "r": replay_id,
                        "c": idempotency_key,
                    },
                )
            return {"event_id": replay_id, "duplicate": False}
        finally:
            session.close()

    @router.post("/api/v1/reconciliation-runs", status_code=202)
    def start_reconciliation(
        body: ReconciliationRequest,
        idempotency_key: Annotated[
            str, Header(alias="Idempotency-Key", min_length=1, max_length=255)
        ],
        auth: tuple[Any, AuthenticatedPrincipal] = Depends(reconciliation_auth),
    ) -> dict[str, Any]:
        session, actor = auth
        digest = hashlib.sha256(body.kind.encode()).digest()
        now, run_id, event_id = datetime.now(UTC), uuid4(), uuid4()
        try:
            with tenant_transaction(session, actor):
                old = (
                    session.execute(
                        text(
                            "SELECT id,request_digest FROM reconciliation_runs WHERE tenant_id=:t AND idempotency_key=:k"
                        ),
                        {"t": actor.tenant_id, "k": idempotency_key},
                    )
                    .mappings()
                    .one_or_none()
                )
                if old:
                    if bytes(old["request_digest"]) != digest:
                        raise HTTPException(409, "idempotency key conflicts with prior request")
                    return {"run_id": old["id"], "duplicate": True}
                payload = json.dumps(
                    {"run_id": str(run_id), "kind": body.kind}, separators=(",", ":")
                )
                session.execute(
                    text(
                        "INSERT INTO reconciliation_runs(id,created_at,tenant_id,kind,state,started_at,summary,idempotency_key,request_digest) VALUES(:id,:n,:t,:kind,'running',:n,'{}'::jsonb,:key,:digest)"
                    ),
                    {
                        "id": run_id,
                        "n": now,
                        "t": actor.tenant_id,
                        "kind": body.kind,
                        "key": idempotency_key,
                        "digest": digest,
                    },
                )
                session.execute(
                    text(
                        "INSERT INTO canonical_events(id,created_at,tenant_id,event_type,event_version,occurred_at,payload,payload_digest) VALUES(:id,:n,:t,'outcomeos.reconciliation.requested',1,:n,CAST(:p AS jsonb),:d)"
                    ),
                    {
                        "id": event_id,
                        "n": now,
                        "t": actor.tenant_id,
                        "p": payload,
                        "d": hashlib.sha256(payload.encode()).digest(),
                    },
                )
                session.execute(
                    text(
                        "INSERT INTO outbox_jobs(id,created_at,tenant_id,event_id,kind,state,available_at,attempt_count) VALUES(:id,:n,:t,:e,'reconcile.tenant.v1','pending',:n,0)"
                    ),
                    {"id": uuid4(), "n": now, "t": actor.tenant_id, "e": event_id},
                )
            return {"run_id": run_id, "duplicate": False}
        finally:
            session.close()

    @router.get("/api/v1/reconciliation-runs/{run_id}")
    def get_reconciliation(
        run_id: UUID, auth: tuple[Any, AuthenticatedPrincipal] = Depends(reconciliation_auth)
    ) -> dict[str, Any]:
        session, actor = auth
        try:
            with tenant_transaction(session, actor):
                row = (
                    session.execute(
                        text(
                            "SELECT id,kind,state,started_at,finished_at,summary FROM reconciliation_runs WHERE tenant_id=:t AND id=:id"
                        ),
                        {"t": actor.tenant_id, "id": run_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise HTTPException(404, "reconciliation run not found")
                return dict(row)
        finally:
            session.close()

    return router
