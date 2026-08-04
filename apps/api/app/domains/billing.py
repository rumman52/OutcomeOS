from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .common import DomainError, Money, TenantContext, new_id, now
from .contracts import ContractVersion
from .outcomes import Outcome, OutcomeState


@dataclass(frozen=True, slots=True)
class FeeAccrual:
    id: str
    tenant_id: str
    outcome_id: str
    contract_id: str
    contract_version: int
    amount: Money


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    id: str
    tenant_id: str
    account: str
    direction: str
    amount: Money
    reference: str
    recorded_at: object


class BillingService:
    def __init__(self) -> None:
        self.accruals: tuple[FeeAccrual, ...] = ()
        self.ledger: tuple[LedgerEntry, ...] = ()

    def accrue(self, ctx: TenantContext, outcome: Outcome, gross: Money, contract: ContractVersion) -> FeeAccrual:
        if outcome.state != OutcomeState.VERIFIED or not outcome.evidence or not outcome.cod_settled:
            raise DomainError("only verified delivered and settled outcomes can be billed")
        if contract.tenant_id != ctx.tenant_id:
            raise DomainError("contract tenant mismatch")
        fee = Money((gross.amount * contract.fee_rate).quantize(Decimal("0.01")), gross.currency)
        accrual = FeeAccrual(new_id("fee"), ctx.tenant_id, outcome.id, contract.id, contract.version, fee)
        entries = (
            LedgerEntry(new_id("ledger"), ctx.tenant_id, "fees_receivable", "debit", fee, accrual.id, now()),
            LedgerEntry(new_id("ledger"), ctx.tenant_id, "performance_revenue", "credit", fee, accrual.id, now()),
        )
        self.accruals = (*self.accruals, accrual)
        self.ledger = (*self.ledger, *entries)
        return accrual
