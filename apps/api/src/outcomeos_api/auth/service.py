from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from outcomeos_api.auth.api_keys import ApiKeyHasher
from outcomeos_api.auth.jwt import OidcClaims
from outcomeos_api.db import AuthenticatedPrincipal, TenantAccessError
from outcomeos_api.models import ApiKey, Membership, OidcIdentity


def principal_for_oidc_claims(
    session: Session, *, claims: OidcClaims, selected_tenant_id: UUID
) -> AuthenticatedPrincipal:
    """Resolve a verified identity through persisted identity and active membership records."""
    identity = session.scalar(
        select(OidcIdentity).where(
            OidcIdentity.issuer == claims.issuer,
            OidcIdentity.subject == claims.subject,
        )
    )
    if identity is None:
        raise TenantAccessError("identity is not provisioned")
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(selected_tenant_id)},
        )
    membership = session.scalar(
        select(Membership).where(
            Membership.user_id == identity.user_id,
            Membership.tenant_id == selected_tenant_id,
            Membership.status == "active",
        )
    )
    if membership is None:
        raise TenantAccessError("active membership is required")
    return AuthenticatedPrincipal(identity.user_id, membership.tenant_id, membership.id)


def principal_for_api_key(
    session: Session,
    *,
    plaintext: str,
    required_scope: str,
    hasher: ApiKeyHasher,
) -> AuthenticatedPrincipal:
    try:
        marker, environment, random_prefix, tenant_hex, _secret = plaintext.split("_", 4)
        if (marker, environment) != ("oos", "live"):
            raise ValueError
        tenant_id = UUID(hex=tenant_hex)
        prefix = f"{marker}_{environment}_{random_prefix}"
    except ValueError as exc:
        raise TenantAccessError("invalid API key or scope") from exc
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
    candidates = session.scalars(
        select(ApiKey).where(ApiKey.tenant_id == tenant_id, ApiKey.prefix == prefix)
    ).all()
    now = datetime.now(UTC)
    for candidate in candidates:
        if candidate.revoked_at is not None or (
            candidate.expires_at is not None and candidate.expires_at <= now
        ):
            continue
        if required_scope not in candidate.scopes:
            continue
        if hasher.verify(plaintext, candidate.key_digest):
            membership = session.scalar(
                select(Membership).where(
                    Membership.tenant_id == candidate.tenant_id,
                    Membership.role.in_(("owner", "administrator")),
                    Membership.status == "active",
                )
            )
            if membership is None:
                raise TenantAccessError("API key tenant has no active administrator")
            return AuthenticatedPrincipal(membership.user_id, candidate.tenant_id, membership.id)
    raise TenantAccessError("invalid API key or scope")
