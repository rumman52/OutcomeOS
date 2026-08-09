from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID


def object_key(tenant_id: UUID, *parts: str) -> str:
    """Build an object-store key whose first namespace is the tenant."""
    clean = [str(PurePosixPath(part)) for part in parts]
    if any(part.startswith("/") or ".." in PurePosixPath(part).parts for part in clean):
        raise ValueError("unsafe object key component")
    return "/".join(("tenants", str(tenant_id), *clean))


def cache_key(tenant_id: UUID, namespace: str, identifier: str) -> str:
    return f"tenant:{tenant_id}:{namespace}:{identifier}"


@dataclass(frozen=True)
class JobTenantContext:
    tenant_id: UUID
    membership_id: UUID
    expires_at: int


def sign_job_context(context: JobTenantContext, secret: bytes) -> str:
    payload = json.dumps(
        {
            "tenant_id": str(context.tenant_id),
            "membership_id": str(context.membership_id),
            "exp": context.expires_at,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    signature = hmac.new(secret, payload, hashlib.sha256).digest()
    return (
        base64.urlsafe_b64encode(payload).rstrip(b"=")
        + b"."
        + base64.urlsafe_b64encode(signature).rstrip(b"=")
    ).decode()


def verify_job_context(token: str, secret: bytes, *, now: int | None = None) -> JobTenantContext:
    try:
        encoded_payload, encoded_signature = token.encode().split(b".", 1)
        payload = base64.urlsafe_b64decode(encoded_payload + b"=" * (-len(encoded_payload) % 4))
        signature = base64.urlsafe_b64decode(
            encoded_signature + b"=" * (-len(encoded_signature) % 4)
        )
        if not hmac.compare_digest(signature, hmac.new(secret, payload, hashlib.sha256).digest()):
            raise ValueError("invalid job context signature")
        data: dict[str, Any] = json.loads(payload)
        context = JobTenantContext(
            UUID(data["tenant_id"]), UUID(data["membership_id"]), int(data["exp"])
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid job context") from exc
    if context.expires_at < (int(time.time()) if now is None else now):
        raise ValueError("expired job context")
    return context
