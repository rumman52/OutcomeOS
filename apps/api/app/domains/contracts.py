from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .common import DomainError, TenantContext
from .tenancy import TenantStore


@dataclass(frozen=True, slots=True)
class ContractVersion:
    id: str
    tenant_id: str
    version: int
    fee_rate: Decimal


class ContractService:
    def __init__(self) -> None:
        self.store: TenantStore[ContractVersion] = TenantStore()

    def publish(self, ctx: TenantContext, contract_id: str, version: int, fee_rate: Decimal) -> ContractVersion:
        if not Decimal("0") <= fee_rate <= Decimal("1"):
            raise DomainError("fee rate must be between zero and one")
        contract = ContractVersion(contract_id, ctx.tenant_id, version, fee_rate)
        return self.store.put(ctx, f"{contract_id}:v{version}", contract)
