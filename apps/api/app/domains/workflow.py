from __future__ import annotations

from decimal import Decimal

from .ai import propose_from_message
from .analytics import KnowledgeIndex
from .audit import AuditLog
from .billing import BillingService
from .commerce import OrderService
from .common import TenantContext
from .contracts import ContractService
from .conversations import ConversationService, SandboxMessageProvider
from .crm import LeadService
from .integrations import SandboxCODProvider, SandboxCourierProvider, WebhookInbox
from .outcomes import OutcomeService
from .verification import DeliveryEvidence


class OutcomeWorkflow:
    """Application service: the only place proposals/webhooks become domain commands."""

    def __init__(self) -> None:
        self.conversations = ConversationService()
        self.knowledge = KnowledgeIndex()
        self.leads = LeadService()
        self.orders = OrderService(self.leads)
        self.outcomes = OutcomeService()
        self.contracts = ContractService()
        self.billing = BillingService()
        self.webhooks = WebhookInbox()
        self.audit = AuditLog()

    def qualify(self, ctx: TenantContext, payload: dict[str, str]):
        conversation = self.conversations.receive(ctx, SandboxMessageProvider(), payload)
        docs = self.knowledge.retrieve(ctx, payload["text"])
        proposal = propose_from_message(payload["text"], docs)
        lead = self.leads.create(ctx, **proposal.arguments)
        self.audit.append(ctx, "lead.created_from_validated_proposal", lead.id)
        return conversation, proposal, lead

    def run_fulfilment(self, ctx: TenantContext, *, lead_id: str, sku: str, price: Decimal,
                       currency: str, idempotency_key: str, contract_id: str, contract_version: int):
        lead = self.leads.verify(ctx, lead_id, True)
        order = self.orders.create(ctx, lead_id=lead.id, sku=sku, quantity=1, unit_price=price,
            currency=currency, authorization=f"approved:{lead.customer_ref}", idempotency_key=idempotency_key)
        outcome = self.outcomes.create(ctx, order.id)
        outcome = self.outcomes.command(ctx, outcome.id, "dispatch", outcome.version)
        delivery = self.webhooks.accept(ctx, SandboxCourierProvider(), {"event_id": "delivery-1", "outcome_id": outcome.id,
            "tracking": "TRACK-1", "recipient": lead.name, "delivered_at": "2026-08-04T12:00:00Z"})
        evidence = DeliveryEvidence(delivery.data["tracking_id"], delivery.data["delivered_at"], delivery.data["recipient"])
        outcome = self.outcomes.command(ctx, outcome.id, "record_delivery", outcome.version, evidence)
        self.webhooks.accept(ctx, SandboxCODProvider(), {"event_id": "settlement-1", "outcome_id": outcome.id, "settlement_ref": "COD-1"})
        outcome = self.outcomes.command(ctx, outcome.id, "record_settlement", outcome.version)
        outcome = self.outcomes.command(ctx, outcome.id, "verify", outcome.version)
        contract = self.contracts.store.get(ctx, f"{contract_id}:v{contract_version}")
        accrual = self.billing.accrue(ctx, outcome, order.total, contract)
        outcome = self.outcomes.command(ctx, outcome.id, "bill", outcome.version)
        self.audit.append(ctx, "outcome.billed", outcome.id)
        return order, outcome, accrual
