from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from jwt.algorithms import RSAAlgorithm
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from outcomeos_api.auth.api_keys import ApiKeyHasher
from outcomeos_api.auth.invitations import InvitationTokenHasher
from outcomeos_api.auth.jwt import JwtVerifier, TokenVerificationError, load_oidc_jwks
from outcomeos_api.auth.policy import Permission, Role, authorize
from outcomeos_api.auth.service import principal_for_api_key, principal_for_oidc_claims
from outcomeos_api.db import TenantAccessError
from outcomeos_api.models import ApiKey, Base, Membership, OidcIdentity, Tenant, User


def jwt_fixture() -> tuple[RSAPrivateKey, dict[str, object]]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    jwk.update({"kid": "fixture-key", "use": "sig", "alg": "RS256"})
    return key, {"keys": [jwk]}


def token_for(key: RSAPrivateKey, **overrides: object) -> str:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "iss": "https://identity.test",
        "aud": "outcomeos-api",
        "sub": "fixture-subject",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "fixture-key"})


def test_oidc_jwks_verification_and_claim_rejections() -> None:
    key, jwks = jwt_fixture()
    verifier = JwtVerifier(issuer="https://identity.test", audience="outcomeos-api", jwks=jwks)
    assert verifier.verify(token_for(key)).subject == "fixture-subject"
    for overrides in (
        {"iss": "https://attacker.test"},
        {"aud": "other-api"},
        {"exp": datetime.now(UTC) - timedelta(seconds=1)},
        {"sub": ""},
    ):
        with pytest.raises(TokenVerificationError):
            verifier.verify(token_for(key, **overrides))


def test_oidc_rejects_bad_headers_and_jwks() -> None:
    key, jwks = jwt_fixture()
    verifier = JwtVerifier(issuer="https://identity.test", audience="outcomeos-api", jwks=jwks)
    for token in (
        "malformed",
        jwt.encode({"sub": "x"}, key, algorithm="RS256"),
        jwt.encode({"sub": "x"}, key, algorithm="RS256", headers={"kid": "unknown"}),
    ):
        with pytest.raises(TokenVerificationError):
            verifier.verify(token)
    with pytest.raises(ValueError, match="at least one"):
        JwtVerifier(issuer="https://identity.test", audience="api", jwks={"keys": []})


def test_oidc_endpoint_validation_fails_before_network() -> None:
    for kwargs in (
        {"issuer": "http://identity.test", "jwks_url": None, "discovery_url": None},
        {
            "issuer": "https://identity.test",
            "jwks_url": "https://attacker.test/jwks",
            "discovery_url": None,
        },
        {
            "issuer": "https://identity.test",
            "jwks_url": "https://user@identity.test/jwks",
            "discovery_url": None,
        },
    ):
        with pytest.raises(ValueError):
            load_oidc_jwks(**kwargs)  # type: ignore[arg-type]


def test_policy_is_explicit_and_deny_by_default() -> None:
    assert authorize(Role.OWNER, Permission.API_KEY_MANAGE)
    assert authorize(Role.FINANCE, Permission.FINANCE_WRITE)
    assert not authorize(Role.EXTERNAL_PARTNER, Permission.DISPUTE_REVIEW)
    assert not authorize(Role.READ_ONLY, Permission.DATA_WRITE)
    assert set(Role) == {
        Role.OWNER,
        Role.ADMINISTRATOR,
        Role.OPERATOR,
        Role.MARKETER,
        Role.ANALYST,
        Role.FINANCE,
        Role.DISPUTE_REVIEWER,
        Role.EXTERNAL_PARTNER,
        Role.READ_ONLY,
    }


def test_invitation_tokens_are_stored_as_keyed_digests() -> None:
    hasher = InvitationTokenHasher("fixture-pepper-at-least-sixteen")
    token, digest = hasher.generate()
    assert token not in digest
    assert hasher.verify(token, digest)
    assert not hasher.verify(f"{token}-tampered", digest)


def test_verified_identity_still_requires_persisted_membership() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    tenant_a, tenant_b, user_id = uuid4(), uuid4(), uuid4()
    with Session(engine) as session:
        session.add_all([Tenant(id=tenant_a, name="A"), Tenant(id=tenant_b, name="B")])
        session.add(User(id=user_id, email="user@example.test"))
        session.add(OidcIdentity(user_id=user_id, issuer="issuer", subject="subject"))
        membership = Membership(tenant_id=tenant_a, user_id=user_id, role="owner", status="active")
        session.add(membership)
        session.commit()
        from outcomeos_api.auth.jwt import OidcClaims

        claims = OidcClaims("issuer", "subject", "audience", 9999999999)
        assert (
            principal_for_oidc_claims(session, claims=claims, selected_tenant_id=tenant_a).tenant_id
            == tenant_a
        )
        with pytest.raises(TenantAccessError):
            principal_for_oidc_claims(session, claims=claims, selected_tenant_id=tenant_b)


def test_api_keys_are_hashed_scoped_expirable_and_revocable() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    tenant_id, user_id = uuid4(), uuid4()
    hasher = ApiKeyHasher("fixture-pepper-at-least-sixteen")
    generated = hasher.generate(tenant_id)
    with Session(engine) as session:
        session.add(Tenant(id=tenant_id, name="A"))
        session.add(User(id=user_id, email="owner@example.test"))
        session.add(Membership(tenant_id=tenant_id, user_id=user_id, role="owner", status="active"))
        api_key = ApiKey(
            tenant_id=tenant_id,
            name="CI",
            prefix=generated.prefix,
            key_digest=generated.digest,
            scopes=["events:write"],
        )
        session.add(api_key)
        session.commit()
        assert generated.plaintext not in api_key.key_digest
        assert (
            principal_for_api_key(
                session, plaintext=generated.plaintext, required_scope="events:write", hasher=hasher
            ).tenant_id
            == tenant_id
        )
        with pytest.raises(TenantAccessError):
            principal_for_api_key(
                session,
                plaintext=generated.plaintext,
                required_scope="finance:write",
                hasher=hasher,
            )
        api_key.revoked_at = datetime.now(UTC)
        session.commit()
        with pytest.raises(TenantAccessError):
            principal_for_api_key(
                session, plaintext=generated.plaintext, required_scope="events:write", hasher=hasher
            )
