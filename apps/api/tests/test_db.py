from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from outcomeos_api.db import (
    AuthenticatedPrincipal,
    TenantAccessError,
    authenticated_tenant_transaction,
    create_database_engine,
    create_session_factory,
    principal_from_membership,
    tenant_transaction,
)
from outcomeos_api.models import Base, Membership, Tenant, User


def test_membership_resolution_and_authenticated_transaction() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    tenant_id, user_id = uuid4(), uuid4()
    with factory() as session:
        session.add_all(
            [
                Tenant(id=tenant_id, name="tenant"),
                User(id=user_id, email="db@example.test"),
                Membership(tenant_id=tenant_id, user_id=user_id, role="owner", status="active"),
            ]
        )
        session.commit()
        with authenticated_tenant_transaction(
            session, user_id=user_id, tenant_id=tenant_id
        ) as scoped:
            assert scoped.info["tenant_id"] == tenant_id
        assert "tenant_id" not in session.info
        with pytest.raises(TenantAccessError):
            principal_from_membership(session, user_id=user_id, tenant_id=uuid4())
    engine.dispose()


def test_tenant_transaction_clears_context_and_rejects_nested_transaction() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    principal = AuthenticatedPrincipal(uuid4(), uuid4(), uuid4())
    with Session(engine) as session:
        with tenant_transaction(session, principal) as scoped:
            assert scoped.info["tenant_id"] == principal.tenant_id
        assert "tenant_id" not in session.info
        with session.begin():
            with pytest.raises(RuntimeError, match="must begin"):
                tenant_transaction(session, principal).__enter__()
            with pytest.raises(RuntimeError, match="must begin"):
                authenticated_tenant_transaction(
                    session, user_id=principal.user_id, tenant_id=principal.tenant_id
                ).__enter__()
    engine.dispose()
