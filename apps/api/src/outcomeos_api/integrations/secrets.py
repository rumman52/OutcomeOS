from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from os import urandom
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass(frozen=True)
class EncryptedSecret:
    """An AES-256-GCM ciphertext whose tenant and endpoint are authenticated."""

    key_id: str
    nonce: bytes
    ciphertext: bytes


def authenticated_context(tenant_id: UUID, endpoint_id: UUID, version: int) -> bytes:
    if version < 1:
        raise ValueError("secret version must be positive")
    return f"outcomeos:integration-secret:v1:{tenant_id}:{endpoint_id}:{version}".encode()


class SecretCipher:
    def __init__(self, keys: dict[str, bytes], active_key_id: str) -> None:
        if active_key_id not in keys:
            raise ValueError("active key id is not present in keyring")
        if any(len(key) != 32 for key in keys.values()):
            raise ValueError("integration encryption keys must be exactly 32 bytes")
        self._keys = dict(keys)
        self._active_key_id = active_key_id

    def encrypt(
        self, plaintext: bytes, *, tenant_id: UUID, endpoint_id: UUID, version: int
    ) -> EncryptedSecret:
        if not plaintext:
            raise ValueError("integration secret must not be empty")
        nonce = urandom(12)
        context = authenticated_context(tenant_id, endpoint_id, version)
        ciphertext = AESGCM(self._keys[self._active_key_id]).encrypt(nonce, plaintext, context)
        return EncryptedSecret(self._active_key_id, nonce, ciphertext)

    def decrypt(
        self,
        secret: EncryptedSecret,
        *,
        tenant_id: UUID,
        endpoint_id: UUID,
        version: int,
    ) -> bytes:
        key = self._keys.get(secret.key_id)
        if key is None:
            raise ValueError("secret encryption key is unavailable")
        return AESGCM(key).decrypt(
            secret.nonce,
            secret.ciphertext,
            authenticated_context(tenant_id, endpoint_id, version),
        )


def rotation_is_usable(
    *, not_before: datetime, expires_at: datetime, now: datetime | None = None
) -> bool:
    checked_at = now or datetime.now(UTC)
    if not_before.tzinfo is None or expires_at.tzinfo is None or checked_at.tzinfo is None:
        raise ValueError("secret rotation timestamps must be timezone-aware")
    return not_before <= checked_at < expires_at
