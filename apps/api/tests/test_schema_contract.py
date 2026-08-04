from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from outcomeos_api.models import (
    BillableResult,
    Contact,
    Conversation,
    DisputeEvidence,
    LedgerEntry,
    Order,
    Outcome,
)


def test_external_records_have_tenant_scoped_idempotency_constraints():
    for model in (
        Contact,
        Conversation,
        Order,
        Outcome,
        DisputeEvidence,
        BillableResult,
        LedgerEntry,
    ):
        constraints = {
            tuple(column.name for column in constraint.columns)
            for constraint in model.__table__.constraints
            if hasattr(constraint, "columns")
        }
        assert ("tenant_id", "provider", "external_id") in constraints


def test_money_is_integer_minor_units_with_currency():
    for model in (Order, BillableResult, LedgerEntry):
        ddl = str(CreateTable(model.__table__).compile(dialect=postgresql.dialect()))
        assert "amount_minor BIGINT NOT NULL" in ddl
        assert "currency VARCHAR(3) NOT NULL" in ddl
        assert "NUMERIC" not in ddl and "FLOAT" not in ddl


def test_high_risk_tables_are_forced_through_rls():
    migration = (
        Path(__file__).parents[1] / "migrations/versions/20260804_0001_mvp_tenant_schema.py"
    ).read_text()
    for table in (
        "contacts",
        "conversations",
        "knowledge_chunks",
        "orders",
        "outcomes",
        "dispute_evidence",
        "billable_results",
        "ledger_entries",
    ):
        assert f'"{table}"' in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "WITH CHECK" in migration
    assert "current_setting('app.tenant_id', true)" in migration
