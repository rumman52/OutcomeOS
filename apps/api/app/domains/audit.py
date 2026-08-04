from __future__ import annotations

from dataclasses import dataclass

from .common import TenantContext, new_id, now


@dataclass(frozen=True, slots=True)
class AuditEntry:
    id: str
    tenant_id: str
    actor_id: str
    action: str
    subject: str
    at: object


class AuditLog:
    """Append-only audit log exposed without update/delete operations."""

    def __init__(self) -> None:
        self._entries: tuple[AuditEntry, ...] = ()

    def append(self, ctx: TenantContext, action: str, subject: str) -> AuditEntry:
        entry = AuditEntry(new_id("audit"), ctx.tenant_id, ctx.actor_id, action, subject, now())
        self._entries = (*self._entries, entry)
        return entry

    def list(self, ctx: TenantContext) -> tuple[AuditEntry, ...]:
        return tuple(e for e in self._entries if e.tenant_id == ctx.tenant_id)
