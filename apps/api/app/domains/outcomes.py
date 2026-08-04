from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from .common import ConflictError, DomainError, TenantContext, new_id
from .tenancy import TenantStore
from .verification import DeliveryEvidence, verify_outcome


class OutcomeState(StrEnum):
    CREATED = "created"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    SETTLED = "settled"
    VERIFIED = "verified"
    BILLED = "billed"
    DISPUTED = "disputed"


@dataclass(frozen=True, slots=True)
class Outcome:
    id: str
    tenant_id: str
    order_id: str
    state: OutcomeState
    version: int = 0
    evidence: DeliveryEvidence | None = None
    cod_settled: bool = False


class OutcomeService:
    transitions = {
        "dispatch": (OutcomeState.CREATED, OutcomeState.DISPATCHED),
        "record_delivery": (OutcomeState.DISPATCHED, OutcomeState.DELIVERED),
        "record_settlement": (OutcomeState.DELIVERED, OutcomeState.SETTLED),
        "verify": (OutcomeState.SETTLED, OutcomeState.VERIFIED),
        "bill": (OutcomeState.VERIFIED, OutcomeState.BILLED),
    }

    def __init__(self) -> None:
        self.store: TenantStore[Outcome] = TenantStore()

    def create(self, ctx: TenantContext, order_id: str) -> Outcome:
        outcome = Outcome(new_id("outcome"), ctx.tenant_id, order_id, OutcomeState.CREATED)
        return self.store.put(ctx, outcome.id, outcome)

    def command(self, ctx: TenantContext, outcome_id: str, command: str, expected_version: int,
                evidence: DeliveryEvidence | None = None) -> Outcome:
        with self.store.lock:  # reference row lock; persistent adapters use SELECT ... FOR UPDATE
            current = self.store.get(ctx, outcome_id)
            if current.version != expected_version:
                raise ConflictError("stale outcome version")
            expected, target = self.transitions.get(command, (None, None))
            if current.state != expected:
                raise DomainError(f"cannot {command} from {current.state}")
            updates: dict[str, object] = {"state": target, "version": current.version + 1}
            if command == "record_delivery":
                if evidence is None:
                    raise DomainError("delivery evidence is required")
                evidence.validate()
                updates["evidence"] = evidence
            elif command == "record_settlement":
                updates["cod_settled"] = True
            elif command in {"verify", "bill"}:
                verify_outcome(current.evidence, current.cod_settled)
            changed = replace(current, **updates)
            return self.store.put(ctx, outcome_id, changed)
