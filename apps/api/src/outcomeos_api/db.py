from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


class TenantAccessError(PermissionError):
    """Raised when authenticated membership cannot establish tenant access."""


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user_id: UUID
    tenant_id: UUID
    membership_id: UUID


def create_database_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def principal_from_membership(
    session: Session, *, user_id: UUID, tenant_id: UUID
) -> AuthenticatedPrincipal:
    """Resolve tenant context from persisted membership, never request-supplied claims alone."""
    from .models import Membership

    membership = (
        session.query(Membership)
        .filter_by(user_id=user_id, tenant_id=tenant_id, status="active")
        .one_or_none()
    )
    if membership is None:
        raise TenantAccessError("no active membership for tenant")
    return AuthenticatedPrincipal(user_id, membership.tenant_id, membership.id)


@contextmanager
def authenticated_tenant_transaction(
    session: Session, *, user_id: UUID, tenant_id: UUID
) -> Iterator[Session]:
    """Authenticate membership and install RLS context in the same transaction."""
    if session.in_transaction():
        raise RuntimeError("authenticated_tenant_transaction must begin the transaction")
    with session.begin():
        # The selected tenant scopes the membership lookup through RLS; it does not authorize it.
        # Authorization succeeds only when an active persisted membership matches the verified user.
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            session.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
        principal = principal_from_membership(session, user_id=user_id, tenant_id=tenant_id)
        session.info["tenant_id"] = principal.tenant_id
        try:
            yield session
        finally:
            session.info.pop("tenant_id", None)


@contextmanager
def tenant_transaction(session: Session, principal: AuthenticatedPrincipal) -> Iterator[Session]:
    """Install transaction-local PostgreSQL RLS identity from an authenticated principal."""
    if session.in_transaction():
        raise RuntimeError("tenant_transaction must begin the transaction")
    with session.begin():
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            session.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(principal.tenant_id)},
            )
        session.info["tenant_id"] = principal.tenant_id
        try:
            yield session
        finally:
            session.info.pop("tenant_id", None)
