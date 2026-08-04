from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .common import ConflictError, DomainError, Money, TenantContext, new_id
from .crm import LeadService
from .tenancy import TenantStore


@dataclass(slots=True)
class InventoryItem:
    sku: str
    price: Money
    available: int


@dataclass(frozen=True, slots=True)
class Order:
    id: str
    tenant_id: str
    lead_id: str
    sku: str
    quantity: int
    total: Money
    idempotency_key: str


class OrderService:
    def __init__(self, leads: LeadService) -> None:
        self.leads = leads
        self.inventory: TenantStore[InventoryItem] = TenantStore()
        self.orders: TenantStore[Order] = TenantStore()
        self._idempotency: dict[tuple[str, str], str] = {}

    def stock(self, ctx: TenantContext, item: InventoryItem) -> None:
        self.inventory.put(ctx, item.sku, item)

    def create(self, ctx: TenantContext, *, lead_id: str, sku: str, quantity: int, unit_price: Decimal,
               currency: str, authorization: str, idempotency_key: str) -> Order:
        key = (ctx.tenant_id, idempotency_key)
        with self.orders.lock:
            if key in self._idempotency:
                old = self.orders.get(ctx, self._idempotency[key])
                if (old.lead_id, old.sku, old.quantity) != (lead_id, sku, quantity):
                    raise ConflictError("idempotency key reused with different order")
                return old
            lead = self.leads.store.get(ctx, lead_id)
            if not lead.verified:
                raise DomainError("verified customer data is required")
            item = self.inventory.get(ctx, sku)
            if quantity <= 0 or item.available < quantity:
                raise DomainError("insufficient stock")
            if item.price != Money(unit_price, currency):
                raise DomainError("price changed")
            if authorization != f"approved:{lead.customer_ref}":
                raise DomainError("customer authorization missing")
            item.available -= quantity
            order = Order(new_id("order"), ctx.tenant_id, lead_id, sku, quantity,
                          Money(unit_price * quantity, currency), idempotency_key)
            self.orders.put(ctx, order.id, order)
            self._idempotency[key] = order.id
            return order
