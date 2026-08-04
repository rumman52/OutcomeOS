from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping
from uuid import uuid4


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class DomainError(ValueError):
    """A deterministic business-rule failure."""


class ConflictError(DomainError):
    """Optimistic concurrency or idempotency conflict."""


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant_id: str
    actor_id: str

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.actor_id:
            raise DomainError("tenant_id and actor_id are required")


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if self.amount < 0 or len(self.currency) != 3:
            raise DomainError("invalid money")


@dataclass(frozen=True, slots=True)
class CanonicalEvent:
    tenant_id: str
    event_id: str
    kind: str
    occurred_at: datetime
    data: Mapping[str, Any]
    sandbox: bool = True
