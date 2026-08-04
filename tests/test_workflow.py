from decimal import Decimal

import pytest

from apps.api.app.domains.analytics import KnowledgeItem
from apps.api.app.domains.commerce import InventoryItem
from apps.api.app.domains.common import ConflictError, DomainError, Money, TenantContext
from apps.api.app.domains.outcomes import OutcomeState
from apps.api.app.domains.workflow import OutcomeWorkflow


def setup_workflow():
    ctx = TenantContext("tenant-a", "agent-1")
    workflow = OutcomeWorkflow()
    workflow.knowledge.add(KnowledgeItem("tenant-a", "sage linen is available", frozenset({"linen"})))
    workflow.knowledge.add(KnowledgeItem("tenant-b", "SECRET other tenant", frozenset({"linen"})))
    workflow.orders.stock(ctx, InventoryItem("LINEN-SAGE", Money(Decimal("100"), "USD"), 2))
    workflow.contracts.publish(ctx, "performance", 3, Decimal("0.10"))
    return ctx, workflow


def test_deterministic_end_to_end_workflow():
    ctx, workflow = setup_workflow()
    conversation, proposal, lead = workflow.qualify(ctx, {"id": "msg-1", "customer_ref": "customer-1", "text": "linen"})
    assert conversation.messages[0]["sandbox"] is True
    assert proposal.tool == "create_lead"
    assert all("SECRET" not in item.text for item in workflow.knowledge.retrieve(ctx, "linen"))
    order, outcome, accrual = workflow.run_fulfilment(ctx, lead_id=lead.id, sku="LINEN-SAGE", price=Decimal("100"),
        currency="USD", idempotency_key="checkout-1", contract_id="performance", contract_version=3)
    assert outcome.state == OutcomeState.BILLED
    assert accrual.amount == Money(Decimal("10.00"), "USD")
    assert accrual.contract_version == 3
    assert len(workflow.webhooks.receipts) == len(workflow.webhooks.outbox) == 2
    assert len(workflow.billing.ledger) == 2
    assert len(workflow.audit.list(ctx)) == 2


def test_optimistic_lock_and_evidence_gate():
    ctx, workflow = setup_workflow()
    _, _, lead = workflow.qualify(ctx, {"id": "msg-1", "customer_ref": "customer-1", "text": "linen"})
    lead = workflow.leads.verify(ctx, lead.id, True)
    order = workflow.orders.create(ctx, lead_id=lead.id, sku="LINEN-SAGE", quantity=1, unit_price=Decimal("100"),
        currency="USD", authorization="approved:customer-1", idempotency_key="one")
    outcome = workflow.outcomes.create(ctx, order.id)
    with pytest.raises(ConflictError):
        workflow.outcomes.command(ctx, outcome.id, "dispatch", 9)
    dispatched = workflow.outcomes.command(ctx, outcome.id, "dispatch", 0)
    with pytest.raises(DomainError, match="evidence"):
        workflow.outcomes.command(ctx, dispatched.id, "record_delivery", 1)


def test_tenant_scope_and_order_idempotency():
    ctx, workflow = setup_workflow()
    _, _, lead = workflow.qualify(ctx, {"id": "msg-1", "customer_ref": "customer-1", "text": "linen"})
    with pytest.raises(DomainError, match="not found"):
        workflow.leads.store.get(TenantContext("tenant-b", "agent"), lead.id)
    lead = workflow.leads.verify(ctx, lead.id, True)
    args = dict(lead_id=lead.id, sku="LINEN-SAGE", quantity=1, unit_price=Decimal("100"), currency="USD",
                authorization="approved:customer-1", idempotency_key="stable")
    assert workflow.orders.create(ctx, **args) == workflow.orders.create(ctx, **args)
    with pytest.raises(ConflictError):
        workflow.orders.create(ctx, **{**args, "quantity": 2})
