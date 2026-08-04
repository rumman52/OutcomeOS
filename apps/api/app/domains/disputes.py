from __future__ import annotations

from dataclasses import dataclass

from .common import DomainError, TenantContext, new_id
from .outcomes import Outcome, OutcomeState
from .tenancy import TenantStore


@dataclass(frozen=True, slots=True)
class Dispute:
    id: str
    tenant_id: str
    outcome_id: str
    reason: str
    status: str = "open"


class DisputeService:
    def __init__(self) -> None:
        self.store: TenantStore[Dispute] = TenantStore()

    def open(self, ctx: TenantContext, outcome: Outcome, reason: str) -> Dispute:
        if outcome.state not in {OutcomeState.DELIVERED, OutcomeState.SETTLED, OutcomeState.VERIFIED, OutcomeState.BILLED}:
            raise DomainError("outcome is not disputable")
        dispute = Dispute(new_id("dispute"), ctx.tenant_id, outcome.id, reason)
        return self.store.put(ctx, dispute.id, dispute)
