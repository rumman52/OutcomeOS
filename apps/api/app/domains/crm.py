from __future__ import annotations

from dataclasses import dataclass

from .common import DomainError, TenantContext, new_id
from .tenancy import TenantStore


@dataclass(frozen=True, slots=True)
class Lead:
    id: str
    tenant_id: str
    customer_ref: str
    name: str
    contact: str
    verified: bool = False


class LeadService:
    def __init__(self) -> None:
        self.store: TenantStore[Lead] = TenantStore()

    def create(self, ctx: TenantContext, customer_ref: str, name: str, contact: str) -> Lead:
        if not all((customer_ref, name, contact)):
            raise DomainError("complete customer data is required")
        lead = Lead(new_id("lead"), ctx.tenant_id, customer_ref, name, contact)
        return self.store.put(ctx, lead.id, lead)

    def verify(self, ctx: TenantContext, lead_id: str, challenge_passed: bool) -> Lead:
        lead = self.store.get(ctx, lead_id)
        if not challenge_passed:
            raise DomainError("lead verification failed")
        verified = Lead(lead.id, lead.tenant_id, lead.customer_ref, lead.name, lead.contact, True)
        return self.store.put(ctx, lead.id, verified)
