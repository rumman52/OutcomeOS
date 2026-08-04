import sqlite3

import pytest
from pydantic import ValidationError

from outcomeos_api.ai import execute_tool
from outcomeos_api.domain import ProfitInputs, contribution_profit, prohibit_float
from outcomeos_api.models import CreateOrderArgs, Money
from outcomeos_api.store import Store


def order(store: Store, payment_method: str = "cod") -> dict[str, object]:
    return store.create_order(CreateOrderArgs.model_validate({
        "tenant_id":"tenant_dhakastyle", "contact_id":"contact_demo",
        "items":[{"variant_id":"variant_DS-PNJ","quantity":1}],
        "payment_method":payment_method, "delivery_address":"12 Demo Road, Dhaka",
        "idempotency_key":f"order-{payment_method}-0001"}))


def test_complete_cod_journey_is_transactional_and_idempotent() -> None:
    store=Store(); store.seed(); created=order(store); order_id=str(created["id"])
    assert len(store.connection.execute("SELECT * FROM outbox_messages").fetchall()) == 1
    store.record_event("tenant_dhakastyle",order_id,"order.confirmed","event-confirmed-1",{})
    store.record_event("tenant_dhakastyle",order_id,"shipment.delivered","event-delivered-1",{"tracking":"DEMO1"})
    assert store.connection.execute("SELECT stage FROM outcomes").fetchone()[0] == "converted"
    store.record_event("tenant_dhakastyle",order_id,"payment.cod_settled","event-settled-001",{"receipt":"COD1"})
    assert store.connection.execute("SELECT stage FROM outcomes").fetchone()[0] == "verified"
    result=store.connection.execute("SELECT amount_minor,currency,contract_version_id FROM billable_results").fetchone()
    assert tuple(result) == (15000,"BDT","contract_bdt150_v1")
    assert store.connection.execute("SELECT count(*) FROM ledger_entries WHERE entry_type='performance_fee_accrual'").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        store.record_event("tenant_dhakastyle",order_id,"payment.cod_settled","event-settled-001",{})


def test_prepaid_requires_independently_validated_payment_and_cancel_disqualifies() -> None:
    store=Store(); store.seed(); created=order(store,"prepaid"); order_id=str(created["id"])
    store.record_event("tenant_dhakastyle",order_id,"order.confirmed","pre-confirm-001",{})
    store.record_event("tenant_dhakastyle",order_id,"shipment.delivered","pre-deliver-001",{})
    assert store.connection.execute("SELECT stage FROM outcomes").fetchone()[0] == "converted"
    store.record_event("tenant_dhakastyle",order_id,"order.cancelled","pre-cancel-0001",{})
    assert store.connection.execute("SELECT stage FROM outcomes").fetchone()[0] == "disqualified"
    assert store.connection.execute("SELECT count(*) FROM billable_results").fetchone()[0] == 0


def test_tenant_scope_and_server_tool_validation() -> None:
    store=Store(); store.seed()
    assert store.products("wrong_tenant") == []
    with pytest.raises(ValidationError): execute_tool(store,"create_order",{"tenant_id":"tenant_dhakastyle"})


def test_finance_uses_exact_minor_units_and_reports_missing_inputs() -> None:
    result,missing=contribution_profit(ProfitInputs(Money(minor=1000,currency="BDT"),Money(minor=400,currency="BDT"),None,Money(minor=100,currency="BDT")))
    assert result is None and missing == ["delivery_cost"]
    with pytest.raises(TypeError): prohibit_float([100,1.2])
