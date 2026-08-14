from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from outcomeos_api.integrations.secrets import EncryptedSecret, SecretCipher


@dataclass(frozen=True)
class NewEndpoint:
    id: UUID
    public_token: str
    public_token_digest: bytes
    signing_secret: str
    encrypted_secret: EncryptedSecret
    not_before: datetime
    expires_at: datetime


def token_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("ascii")).digest()


def create_endpoint_material(
    *,
    tenant_id: UUID,
    cipher: SecretCipher,
    token_bytes: int,
    secret_lifetime_seconds: int,
    now: datetime | None = None,
) -> NewEndpoint:
    if token_bytes < 32 or secret_lifetime_seconds < 1:
        raise ValueError("endpoint cryptographic configuration is invalid")
    endpoint_id = uuid4()
    public_token = secrets.token_urlsafe(token_bytes)
    signing_secret = secrets.token_urlsafe(32)
    starts = now or datetime.now(UTC)
    encrypted = cipher.encrypt(
        signing_secret.encode(), tenant_id=tenant_id, endpoint_id=endpoint_id, version=1
    )
    return NewEndpoint(
        endpoint_id,
        public_token,
        token_digest(public_token),
        signing_secret,
        encrypted,
        starts,
        starts + timedelta(seconds=secret_lifetime_seconds),
    )


def rotation_windows(
    *, now: datetime, lifetime_seconds: int, overlap_seconds: int
) -> tuple[datetime, datetime, datetime]:
    if now.tzinfo is None or lifetime_seconds < 1 or not 0 <= overlap_seconds < lifetime_seconds:
        raise ValueError("invalid rotation window")
    return now, now + timedelta(seconds=lifetime_seconds), now + timedelta(seconds=overlap_seconds)
