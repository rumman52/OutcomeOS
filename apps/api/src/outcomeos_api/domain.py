from __future__ import annotations

import hashlib
import hmac
import json
import threading
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any


class DomainError(ValueError):
    """A safe, expected domain failure."""


class Role(StrEnum):
    ADMIN = "admin"
    AGENT = "agent"
    VIEWER = "viewer"


@dataclass(frozen=True)
class Actor:
    tenant_id: str
    user_id: str
    role: Role


@dataclass(frozen=True)
class Order:
    id: str
    tenant_id: str
    customer_id: str
    total: Decimal
    currency: str
    status: str = "pending"
    version: int = 0


@dataclass(frozen=True)
class OutboxMessage:
    topic: str
    tenant_id: str
    aggregate_id: str


class Store:
    """Small transactional store; production adapters can preserve these invariants."""

    def __init__(self) -> None:
        self.orders: dict[tuple[str, str], Order] = {}
        self.events: set[tuple[str, str]] = set()
        self.outbox: list[OutboxMessage] = []
        self.ledger: list[dict[str, Any]] = []
        self.disputes: dict[tuple[str, str], str] = {}
        self._lock = threading.RLock()

    def create_order(self, actor: Actor, data: dict[str, Any]) -> Order:
        require_role(actor, Role.ADMIN, Role.AGENT)
        missing = {"id", "customer_id", "total", "currency"} - data.keys()
        if missing:
            raise DomainError(f"missing order fields: {', '.join(sorted(missing))}")
        total = Decimal(str(data["total"]))
        if total <= 0 or len(str(data["currency"])) != 3:
            raise DomainError("total must be positive and currency must be ISO-4217")
        key = (actor.tenant_id, str(data["id"]))
        with self._lock:
            if key in self.orders:
                raise DomainError("order already exists")
            order = Order(
                key[1],
                actor.tenant_id,
                str(data["customer_id"]),
                total,
                str(data["currency"]).upper(),
            )
            # Aggregate and outbox are mutated under one lock/transaction boundary.
            self.orders[key] = order
            self.outbox.append(OutboxMessage("order.created", actor.tenant_id, order.id))
            return order

    def get_order(self, actor: Actor, order_id: str) -> Order:
        try:
            return self.orders[(actor.tenant_id, order_id)]
        except KeyError as exc:
            raise DomainError("order not found") from exc

    def transition(self, actor: Actor, order_id: str, status: str, version: int) -> Order:
        require_role(actor, Role.ADMIN, Role.AGENT)
        allowed = {"pending": {"confirmed", "cancelled"}, "confirmed": {"fulfilled"}}
        with self._lock:
            old = self.get_order(actor, order_id)
            if old.version != version:
                raise DomainError("concurrent update")
            if status not in allowed.get(old.status, set()):
                raise DomainError("invalid outcome transition")
            new = replace(old, status=status, version=version + 1)
            self.orders[(actor.tenant_id, order_id)] = new
            self.outbox.append(OutboxMessage("order.transitioned", actor.tenant_id, order_id))
            return new

    def ingest_event(self, tenant: str, event_id: str, payload: dict[str, Any]) -> bool:
        """Return False for a replay, using a canonical JSON digest when no source id exists."""
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        identity = event_id or hashlib.sha256(canonical.encode()).hexdigest()
        with self._lock:
            key = (tenant, identity)
            if key in self.events:
                return False
            self.events.add(key)
            self.outbox.append(OutboxMessage("event.received", tenant, identity))
            return True

    def credit(self, actor: Actor, account: str, amount: Decimal, reference: str) -> None:
        require_role(actor, Role.ADMIN)
        if amount <= 0 or any(x["reference"] == reference for x in self.ledger):
            raise DomainError("invalid or duplicate credit")
        self.ledger.append(
            {
                "tenant": actor.tenant_id,
                "account": account,
                "amount": amount,
                "reference": reference,
            }
        )

    def resolve_dispute(self, actor: Actor, dispute_id: str, resolution: str) -> None:
        require_role(actor, Role.ADMIN)
        if resolution not in {"upheld", "reversed"}:
            raise DomainError("invalid resolution")
        key = (actor.tenant_id, dispute_id)
        if key in self.disputes:
            raise DomainError("dispute already resolved")
        self.disputes[key] = resolution


def require_role(actor: Actor, *roles: Role) -> None:
    if actor.role not in roles:
        raise PermissionError("role is not authorized")


def verify_webhook(
    secret: str, body: bytes, signature: str, timestamp: int, now: datetime | None = None
) -> bool:
    now = now or datetime.now(UTC)
    if abs(now.timestamp() - timestamp) > timedelta(minutes=5).total_seconds():
        return False
    message = f"{timestamp}.".encode() + body
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def attribute(touches: list[dict[str, Any]], conversion: datetime) -> dict[str, Any] | None:
    """Last eligible touch wins; stable source id breaks equal-time ties."""
    eligible = [t for t in touches if conversion - timedelta(days=30) <= t["at"] <= conversion]
    return max(eligible, key=lambda t: (t["at"], t["id"])) if eligible else None


def negotiate_contract(version: str) -> str:
    if version not in {"2025-01", "2026-01"}:
        raise DomainError("unsupported contract version")
    return version
