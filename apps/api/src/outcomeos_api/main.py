from __future__ import annotations

import json
import time
from typing import Any

from fastapi import Cookie, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from outcomeos_api.config import get_settings
from outcomeos_api.mvp import TENANT, USER, profit, sign, store

settings = get_settings()
app = FastAPI(title="OutcomeOS API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Problem(BaseModel):
    detail: str


def active_tenant(outcomeos_session: str | None = Cookie(default=None)) -> str:
    if outcomeos_session != USER:
        raise HTTPException(401, "demo sign-in required")
    return TENANT


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/healthz", tags=["operations"])
def healthz() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


@app.get("/ready", tags=["operations"])
def ready(response: Response) -> dict[str, Any]:
    ok = store.path.exists()
    response.status_code = 200 if ok else 503
    return {
        "status": "ready" if ok else "unavailable",
        "database": "json-demo-persistent",
        "redis": "not_required_for_demo",
    }


@app.get("/worker-health", tags=["operations"])
def worker(response: Response) -> dict[str, Any]:
    response.status_code = 503
    return {
        "status": "degraded",
        "worker": "no heartbeat",
        "queue": "outbox persisted; run make dev-worker",
    }


@app.post("/api/v1/demo/reset")
def reset() -> dict[str, Any]:
    if settings.app_env == "production":
        raise HTTPException(403, "demo reset disabled in production")
    store.reset()
    return {"status": "seeded", "tenant_id": TENANT}


@app.post("/api/v1/demo/sign-in")
def signin(response: Response) -> dict[str, Any]:
    if settings.app_env == "production":
        raise HTTPException(403, "demo sign-in disabled in production")
    response.set_cookie(
        "outcomeos_session", USER, httponly=True, samesite="lax", secure=False
    )
    return {
        "user": {"id": USER, "email": "demo@outcomeos.local"},
        "tenant": {"id": TENANT, "name": store.tenant(TENANT)["name"]},
        "label": "Sandbox / Demo",
    }


@app.get("/api/v1/me")
def me(
    tid: str = Header(default=TENANT, alias="X-Tenant-Id"),
    active: str = Cookie(default=None, alias="outcomeos_session"),
) -> dict[str, Any]:
    if active != USER or tid != TENANT:
        raise HTTPException(403, "active tenant membership required")
    return {"user_id": USER, "tenant_id": TENANT, "role": "admin"}


@app.get("/api/v1/dashboard")
def dashboard(tid: str = Header(default=TENANT, alias="X-Tenant-Id")) -> dict[str, Any]:
    if tid != TENANT:
        raise HTTPException(403, "active tenant membership required")
    t = store.tenant(tid)
    return {
        "tenant": t["name"],
        "campaigns": t["campaigns"],
        "ads": t["ads"],
        "profit": profit(t),
        "funnel": {
            "conversations": len(t["conversations"]),
            "leads": len(t["leads"]),
            "orders": len(t["orders"]),
            "outcomes": len(t["outcomes"]),
            "disputes": len(t["disputes"]),
        },
    }


@app.get("/api/v1/conversations")
def conversations(
    tid: str = Header(default=TENANT, alias="X-Tenant-Id")
) -> list[dict[str, Any]]:
    if tid != TENANT:
        raise HTTPException(403, "active tenant membership required")
    return store.tenant(tid)["conversations"]


@app.post("/api/v1/ai/proposals/{conversation_id}/approve")
def approve(
    conversation_id: str,
    idempotency_key: str = Header(default="demo-approval", alias="Idempotency-Key"),
    tid: str = Header(default=TENANT, alias="X-Tenant-Id"),
) -> dict[str, Any]:
    t = store.tenant(tid)
    if conversation_id not in {c["id"] for c in t["conversations"]}:
        raise HTTPException(404, "conversation not found")
    return store.approve_proposal(tid, idempotency_key)


@app.get("/api/v1/evidence")
def evidence(tid: str = Header(default=TENANT, alias="X-Tenant-Id")) -> dict[str, Any]:
    if tid != TENANT:
        raise HTTPException(403, "active tenant membership required")
    t = store.tenant(tid)
    return {
        k: t[k]
        for k in [
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
        ]
    }


@app.post("/api/v1/sandbox/webhooks/{kind}")
def webhook(
    kind: str,
    payload: dict[str, Any],
    x_outcomeos_timestamp: int = Header(alias="X-OutcomeOS-Timestamp"),
    x_outcomeos_signature: str = Header(alias="X-OutcomeOS-Signature"),
    tid: str = Header(default=TENANT, alias="X-Tenant-Id"),
) -> dict[str, Any]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if (
        abs(time.time() - x_outcomeos_timestamp) > 300
        or sign(settings.webhook_sandbox_secret, body, x_outcomeos_timestamp)
        != x_outcomeos_signature
    ):
        raise HTTPException(401, "invalid sandbox webhook signature")
    if tid != TENANT:
        raise HTTPException(403, "active tenant membership required")
    event_id = str(payload.get("event_id", kind))
    mapped = "delivery" if kind in {"delivery", "shipment.delivered"} else "cod"
    return store.record_evidence(tid, mapped, event_id)


@app.post("/api/v1/leads/verify")
def verify_lead(
    tid: str = Header(default=TENANT, alias="X-Tenant-Id")
) -> dict[str, Any]:
    if tid != TENANT:
        raise HTTPException(403, "active tenant membership required")
    return store.complete_verification(tid)


@app.post("/api/v1/disputes/reverse")
def reverse(tid: str = Header(default=TENANT, alias="X-Tenant-Id")) -> dict[str, Any]:
    if tid != TENANT:
        raise HTTPException(403, "active tenant membership required")
    return store.dispute_reverse(tid)
