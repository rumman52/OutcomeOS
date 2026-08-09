from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from outcomeos_api.db import TenantAccessError
from outcomeos_api.models import (
    Base,
    BillableResult,
    Contact,
    Conversation,
    DisputeEvidence,
    KnowledgeChunk,
    KnowledgeDocument,
    LedgerEntry,
    Order,
    Outcome,
    Tenant,
)
from outcomeos_api.repositories import TenantRepository


@pytest.fixture()
def session(tenant_ids: dict[str, Any]) -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Tenant(id=UUID(tenant_ids["tenant_a"]), name="Tenant A"),
                Tenant(id=UUID(tenant_ids["tenant_b"]), name="Tenant B"),
            ]
        )
        session.commit()
        yield session


def records_for(tenant_id: UUID) -> list[Base]:
    document_id, order_id, outcome_id, billable_id = uuid4(), uuid4(), uuid4(), uuid4()
    return [
        Contact(
            tenant_id=tenant_id,
            provider="fixture",
            external_id=str(uuid4()),
            display_name="Contact",
        ),
        Conversation(
            tenant_id=tenant_id,
            provider="fixture",
            external_id=str(uuid4()),
            subject="Private",
        ),
        KnowledgeDocument(
            id=document_id,
            tenant_id=tenant_id,
            provider="fixture",
            external_id=str(uuid4()),
            title="Private",
        ),
        KnowledgeChunk(
            tenant_id=tenant_id,
            document_id=document_id,
            chunk_index=0,
            content="Private",
        ),
        Order(
            id=order_id,
            tenant_id=tenant_id,
            provider="fixture",
            external_id=str(uuid4()),
            status="paid",
            amount_minor=1099,
            currency="USD",
        ),
        Outcome(
            id=outcome_id,
            tenant_id=tenant_id,
            provider="fixture",
            external_id=str(uuid4()),
            order_id=order_id,
            kind="retained",
        ),
        DisputeEvidence(
            tenant_id=tenant_id,
            provider="fixture",
            external_id=str(uuid4()),
            order_id=order_id,
            object_key="private",
        ),
        BillableResult(
            id=billable_id,
            tenant_id=tenant_id,
            provider="fixture",
            external_id=str(uuid4()),
            outcome_id=outcome_id,
            amount_minor=250,
            currency="USD",
        ),
        LedgerEntry(
            tenant_id=tenant_id,
            provider="fixture",
            external_id=str(uuid4()),
            billable_result_id=billable_id,
            direction="credit",
            amount_minor=250,
            currency="USD",
        ),
    ]


@pytest.mark.parametrize(
    "model",
    [
        Contact,
        Conversation,
        KnowledgeDocument,
        KnowledgeChunk,
        Order,
        Outcome,
        DisputeEvidence,
        BillableResult,
        LedgerEntry,
    ],
)
def test_tenant_a_cannot_read_or_delete_tenant_b_business_data(
    session: Session, tenant_ids: dict[str, Any], model: type[Base]
) -> None:
    tenant_a, tenant_b = UUID(tenant_ids["tenant_a"]), UUID(tenant_ids["tenant_b"])
    records = records_for(tenant_b)
    session.add_all(records)
    session.commit()
    target = next(record for record in records if isinstance(record, model))

    session.info["tenant_id"] = tenant_a
    repository = TenantRepository(session, model)
    target_id = target.id  # type: ignore[attr-defined]
    assert repository.get(target_id) is None
    assert repository.delete(target_id) is False
    assert session.get(model, target_id) is not None


@pytest.mark.parametrize(
    "model",
    [
        Contact,
        Conversation,
        KnowledgeChunk,
        Order,
        Outcome,
        DisputeEvidence,
        BillableResult,
        LedgerEntry,
    ],
)
def test_tenant_a_cannot_insert_tenant_b_record(
    session: Session, tenant_ids: dict[str, Any], model: type[Base]
) -> None:
    tenant_a, tenant_b = UUID(tenant_ids["tenant_a"]), UUID(tenant_ids["tenant_b"])
    session.info["tenant_id"] = tenant_a
    record = next(item for item in records_for(tenant_b) if isinstance(item, model))
    with pytest.raises(TenantAccessError):
        TenantRepository(session, model).add(record)
