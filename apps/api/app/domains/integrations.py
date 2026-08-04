from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Mapping, Any

from .common import CanonicalEvent, ConflictError, TenantContext, now


class SandboxCourierProvider:
    name = "sandbox-courier"
    sandbox = True

    def normalize(self, tenant_id: str, payload: Mapping[str, Any]) -> CanonicalEvent:
        return CanonicalEvent(tenant_id, str(payload["event_id"]), "delivery.completed", now(), {
            "outcome_id": payload["outcome_id"], "tracking_id": payload["tracking"],
            "recipient": payload["recipient"], "delivered_at": payload["delivered_at"],
        }, True)


class SandboxCODProvider:
    name = "sandbox-cod"
    sandbox = True

    def normalize(self, tenant_id: str, payload: Mapping[str, Any]) -> CanonicalEvent:
        return CanonicalEvent(tenant_id, str(payload["event_id"]), "cod.settled", now(), {
            "outcome_id": payload["outcome_id"], "settlement_ref": payload["settlement_ref"],
        }, True)


@dataclass(frozen=True, slots=True)
class WebhookReceipt:
    tenant_id: str
    provider: str
    external_event_id: str
    received_at: object


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    tenant_id: str
    event: CanonicalEvent
    published: bool = False


class WebhookInbox:
    """Reference transaction boundary: receipt and outbox append commit under one lock."""

    def __init__(self) -> None:
        self.receipts: tuple[WebhookReceipt, ...] = ()
        self.outbox: tuple[OutboxRecord, ...] = ()
        self._lock = RLock()

    def accept(self, ctx: TenantContext, provider: object, payload: Mapping[str, Any]) -> CanonicalEvent:
        event = provider.normalize(ctx.tenant_id, payload)  # type: ignore[attr-defined]
        key = (ctx.tenant_id, provider.name, event.event_id)  # type: ignore[attr-defined]
        with self._lock:
            if any((r.tenant_id, r.provider, r.external_event_id) == key for r in self.receipts):
                raise ConflictError("duplicate webhook")
            receipt = WebhookReceipt(ctx.tenant_id, provider.name, event.event_id, now())  # type: ignore[attr-defined]
            # Tuple replacement makes this all-or-nothing in the reference adapter.
            self.receipts, self.outbox = (*self.receipts, receipt), (*self.outbox, OutboxRecord(ctx.tenant_id, event))
        return event
