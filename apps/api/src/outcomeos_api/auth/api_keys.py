from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GeneratedApiKey:
    plaintext: str
    prefix: str
    digest: str


class ApiKeyHasher:
    """Creates one-time credentials and stores only a tenant-scoped keyed digest."""

    def __init__(self, pepper: str):
        if len(pepper) < 16:
            raise ValueError("API-key pepper must be at least 16 characters")
        self._pepper = pepper.encode()

    def digest(self, plaintext: str) -> str:
        return hmac.new(self._pepper, plaintext.encode(), hashlib.sha256).hexdigest()

    def generate(self, tenant_id: UUID) -> GeneratedApiKey:
        prefix = f"oos_live_{secrets.token_hex(6)}"
        plaintext = f"{prefix}_{tenant_id.hex}_{secrets.token_urlsafe(32)}"
        return GeneratedApiKey(plaintext, prefix, self.digest(plaintext))

    def verify(self, plaintext: str, expected_digest: str) -> bool:
        return hmac.compare_digest(self.digest(plaintext), expected_digest)
