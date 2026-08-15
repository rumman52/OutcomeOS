from __future__ import annotations

import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from outcomeos_api.config import Settings, get_settings
from outcomeos_api.db import create_database_engine, create_session_factory
from outcomeos_api.migrations import EXPECTED_MIGRATION_HEAD


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime = settings or get_settings()
    application = FastAPI(title="OutcomeOS API", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[runtime.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "If-Match",
            "X-OutcomeOS-Timestamp",
            "X-OutcomeOS-Signature",
            "X-OutcomeOS-Tenant",
        ],
    )

    @application.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/healthz", tags=["operations"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "environment": runtime.app_env}

    @application.get("/ready", tags=["operations"])
    def ready(response: Response) -> dict[str, Any]:
        if runtime.persistence_backend == "json_sandbox":
            from outcomeos_api.mvp import store

            ok = store.path.exists()
            response.status_code = 200 if ok else 503
            return {"status": "ready" if ok else "unavailable", "database": "json-sandbox"}
        try:
            engine = create_database_engine(runtime.database_url)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one_or_none()
            engine.dispose()
            ok = revision == EXPECTED_MIGRATION_HEAD
            response.status_code = 200 if ok else 503
            return {
                "status": "ready" if ok else "unavailable",
                "database": "postgresql",
                "migration": revision or "missing",
            }
        except SQLAlchemyError:
            response.status_code = 503
            return {"status": "unavailable", "database": "postgresql"}

    @application.get("/worker-health", tags=["operations"])
    def worker_health(response: Response) -> dict[str, str]:
        if runtime.persistence_backend != "postgresql":
            response.status_code = 503
            return {"status": "unavailable", "worker": "unavailable"}
        try:
            engine = create_database_engine(runtime.database_url)
            with engine.connect() as connection:
                row = (
                    connection.execute(
                        text("""SELECT observed_at,status FROM worker_heartbeats
                    ORDER BY observed_at DESC LIMIT 1""")
                    )
                    .mappings()
                    .one_or_none()
                )
            engine.dispose()
            fresh = row is not None and row["observed_at"] >= (
                datetime.now(UTC) - timedelta(seconds=runtime.worker_health_freshness_seconds)
            )
            state = "missing" if row is None else (str(row["status"]) if fresh else "stale")
            healthy = fresh and state == "healthy"
            response.status_code = 200 if fresh else 503
            if not healthy:
                response.status_code = 503
            return {
                "status": "healthy" if healthy else state,
                "worker": "available" if healthy else "unavailable",
            }
        except SQLAlchemyError:
            response.status_code = 503
            return {"status": "unavailable", "worker": "unavailable"}

    if runtime.persistence_backend == "json_sandbox":
        if runtime.app_env not in {"development", "test"}:
            raise RuntimeError("JSON sandbox can only be mounted in development or test")
        _mount_sandbox(application, runtime)
    elif runtime.integration_keyring and runtime.integration_active_key_id:
        from outcomeos_api.contracts.api import contracts_router
        from outcomeos_api.events.operations import operations_router
        from outcomeos_api.imports.api import csv_import_router
        from outcomeos_api.ingestion.api import public_webhook_router
        from outcomeos_api.integrations.api import management_router
        from outcomeos_api.storage import S3ObjectStorage

        write_engine = create_database_engine(runtime.database_url)
        ingress_engine = create_database_engine(
            runtime.ingress_database_url or runtime.database_url
        )
        write_sessions = create_session_factory(write_engine)
        ingress_sessions = create_session_factory(ingress_engine)
        storage = S3ObjectStorage(
            bucket=runtime.s3_bucket,
            endpoint_url=runtime.s3_endpoint_url,
            access_key_id=runtime.s3_access_key_id,
            secret_access_key=runtime.s3_secret_access_key,
            max_bytes=runtime.s3_max_object_bytes,
        )
        application.include_router(management_router(runtime, write_sessions))
        application.include_router(contracts_router(runtime, write_sessions))
        application.include_router(operations_router(runtime, write_sessions))
        application.include_router(csv_import_router(runtime, write_sessions, storage))
        application.include_router(
            public_webhook_router(runtime, ingress_sessions, write_sessions, storage)
        )
    return application


def _mount_sandbox(application: FastAPI, settings: Settings) -> None:
    from outcomeos_api.mvp import TENANT, USER, profit, sign, store

    def sandbox_tenant(
        session: str | None = Cookie(default=None, alias="outcomeos_session"),
    ) -> str:
        if not settings.demo_auth_enabled or session != USER:
            raise HTTPException(401, "sandbox sign-in required")
        return TENANT

    @application.post("/api/v1/demo/reset", tags=["sandbox"])
    def reset() -> dict[str, str]:
        if not settings.demo_auth_enabled:
            raise HTTPException(404, "not found")
        store.reset()
        return {"status": "seeded", "tenant_id": TENANT}

    @application.post("/api/v1/demo/sign-in", tags=["sandbox"])
    def sign_in(response: Response) -> dict[str, object]:
        if not settings.demo_auth_enabled:
            raise HTTPException(404, "not found")
        response.set_cookie(
            "outcomeos_session",
            USER,
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=3600,
        )
        return {"user": {"id": USER}, "tenant": {"id": TENANT}, "label": "Sandbox / Demo"}

    @application.get("/api/v1/me", tags=["sandbox"])
    def me(tenant_id: str = Depends(sandbox_tenant)) -> dict[str, str]:
        return {"user_id": USER, "tenant_id": TENANT, "role": "administrator"}

    @application.get("/api/v1/dashboard", tags=["sandbox"])
    def dashboard(tenant_id: str = Depends(sandbox_tenant)) -> dict[str, Any]:
        tenant = store.tenant(tenant_id)
        return {
            "tenant": tenant["name"],
            "campaigns": tenant["campaigns"],
            "ads": tenant["ads"],
            "profit": profit(tenant),
            "funnel": {
                key: len(tenant[key])
                for key in ("conversations", "leads", "orders", "outcomes", "disputes")
            },
        }

    @application.get("/api/v1/conversations", tags=["sandbox"])
    def conversations(tenant_id: str = Depends(sandbox_tenant)) -> list[dict[str, Any]]:
        return list(store.tenant(tenant_id)["conversations"])

    @application.post("/api/v1/ai/proposals/{conversation_id}/approve", tags=["sandbox"])
    def approve(
        conversation_id: str,
        idempotency_key: str = Header(default="demo-approval", alias="Idempotency-Key"),
        tenant_id: str = Depends(sandbox_tenant),
    ) -> dict[str, Any]:
        tenant = store.tenant(tenant_id)
        if conversation_id not in {item["id"] for item in tenant["conversations"]}:
            raise HTTPException(404, "conversation not found")
        return store.approve_proposal(tenant_id, idempotency_key)

    @application.get("/api/v1/evidence", tags=["sandbox"])
    def evidence(tenant_id: str = Depends(sandbox_tenant)) -> dict[str, Any]:
        tenant = store.tenant(tenant_id)
        keys = (
            "touchpoints",
            "ai_runs",
            "verification_checks",
            "orders",
            "attribution_results",
            "outcomes",
            "contract_versions",
            "billable_results",
            "ledger_entries",
            "audit_events",
            "disputes",
            "shipments",
            "settlement_events",
            "webhook_receipts",
        )
        return {key: tenant[key] for key in keys}

    @application.post("/api/v1/sandbox/webhooks/{kind}", tags=["sandbox"])
    def webhook(
        kind: str,
        payload: dict[str, Any],
        timestamp: int = Header(alias="X-OutcomeOS-Timestamp"),
        signature: str = Header(alias="X-OutcomeOS-Signature"),
        tenant_id: str = Depends(sandbox_tenant),
    ) -> dict[str, Any]:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        if abs(time.time() - timestamp) > 300 or not hmac.compare_digest(
            sign(settings.webhook_sandbox_secret, body, timestamp), signature
        ):
            raise HTTPException(401, "invalid sandbox webhook signature")
        mapped = "delivery" if kind in {"delivery", "shipment.delivered"} else "cod"
        return store.record_evidence(tenant_id, mapped, str(payload.get("event_id", kind)))

    @application.post("/api/v1/leads/verify", tags=["sandbox"])
    def verify_lead(tenant_id: str = Depends(sandbox_tenant)) -> dict[str, Any]:
        return store.complete_verification(tenant_id)

    @application.post("/api/v1/disputes/reverse", tags=["sandbox"])
    def reverse_dispute(tenant_id: str = Depends(sandbox_tenant)) -> dict[str, Any]:
        return store.dispute_reverse(tenant_id)


app = create_app()
