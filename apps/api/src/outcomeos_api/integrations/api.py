from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from outcomeos_api.auth.api_keys import ApiKeyHasher
from outcomeos_api.auth.service import principal_for_api_key
from outcomeos_api.config import Settings
from outcomeos_api.db import AuthenticatedPrincipal, TenantAccessError, tenant_transaction
from outcomeos_api.integrations.endpoints import create_endpoint_material, rotation_windows
from outcomeos_api.integrations.repositories import EndpointRepository
from outcomeos_api.integrations.secrets import SecretCipher


class EndpointCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=120)


class EndpointView(BaseModel):
    id: UUID
    provider: str
    name: str
    status: str
    created_at: datetime
    revoked_at: datetime | None


class NewEndpointView(EndpointView):
    public_token: str
    signing_secret: str


class RotatedSecret(BaseModel):
    signing_secret: str
    version: int
    not_before: datetime
    expires_at: datetime


class DisableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["disable", "revoke"] = "disable"


def management_router(settings: Settings, sessions: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1/integration-endpoints", tags=["integrations"])
    cipher = SecretCipher(
        settings.parsed_integration_keyring(), settings.integration_active_key_id or ""
    )

    def principal(
        authorization: Annotated[str | None, Header()] = None,
    ) -> tuple[Session, AuthenticatedPrincipal]:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(403, "integration management permission required")
        session = sessions()
        try:
            value = principal_for_api_key(
                session,
                plaintext=authorization.removeprefix("Bearer "),
                required_scope="integration:manage",
                hasher=ApiKeyHasher(settings.api_key_pepper),
            )
            session.rollback()
            return session, value
        except TenantAccessError as error:
            session.close()
            raise HTTPException(403, "integration management permission required") from error

    @router.post("", response_model=NewEndpointView, status_code=201)
    def create(
        body: EndpointCreate, auth: tuple[Session, AuthenticatedPrincipal] = Depends(principal)
    ) -> Any:
        session, actor = auth
        now = datetime.now(UTC)
        material = create_endpoint_material(
            tenant_id=actor.tenant_id,
            cipher=cipher,
            token_bytes=settings.integration_endpoint_token_bytes,
            secret_lifetime_seconds=settings.integration_secret_lifetime_seconds,
            now=now,
        )
        try:
            with tenant_transaction(session, actor):
                EndpointRepository(session, actor.tenant_id).insert(
                    {
                        "id": material.id,
                        "created_at": now,
                        "tenant_id": actor.tenant_id,
                        "provider": body.provider,
                        "name": body.name,
                        "public_token_digest": material.public_token_digest,
                    },
                    {
                        "id": uuid4(),
                        "created_at": now,
                        "tenant_id": actor.tenant_id,
                        "endpoint_id": material.id,
                        "version": 1,
                        "key_id": material.encrypted_secret.key_id,
                        "nonce": material.encrypted_secret.nonce,
                        "ciphertext": material.encrypted_secret.ciphertext,
                        "not_before": material.not_before,
                        "expires_at": material.expires_at,
                    },
                )
            return {
                "id": material.id,
                "provider": body.provider,
                "name": body.name,
                "status": "active",
                "created_at": now,
                "revoked_at": None,
                "public_token": material.public_token,
                "signing_secret": material.signing_secret,
            }
        finally:
            session.close()

    @router.get("", response_model=list[EndpointView])
    def list_endpoints(auth: tuple[Session, AuthenticatedPrincipal] = Depends(principal)) -> Any:
        session, actor = auth
        try:
            with tenant_transaction(session, actor):
                return list(EndpointRepository(session, actor.tenant_id).list())
        finally:
            session.close()

    @router.get("/{endpoint_id}", response_model=EndpointView)
    def detail(
        endpoint_id: UUID, auth: tuple[Session, AuthenticatedPrincipal] = Depends(principal)
    ) -> Any:
        session, actor = auth
        try:
            with tenant_transaction(session, actor):
                value = EndpointRepository(session, actor.tenant_id).get(endpoint_id)
                if value is None:
                    raise HTTPException(404, "integration endpoint not found")
                return value
        finally:
            session.close()

    @router.post("/{endpoint_id}/rotate", response_model=RotatedSecret)
    def rotate(
        endpoint_id: UUID, auth: tuple[Session, AuthenticatedPrincipal] = Depends(principal)
    ) -> Any:
        session, actor = auth
        now = datetime.now(UTC)
        try:
            with tenant_transaction(session, actor):
                repository = EndpointRepository(session, actor.tenant_id)
                if repository.get(endpoint_id) is None:
                    raise HTTPException(404, "integration endpoint not found")
                previous = repository.lock_latest_version(endpoint_id)
                if previous is None:
                    raise HTTPException(409, "endpoint has no signing secret")
                version = int(previous["version"]) + 1
                not_before, expires_at, overlap_end = rotation_windows(
                    now=now,
                    lifetime_seconds=settings.integration_secret_lifetime_seconds,
                    overlap_seconds=settings.integration_secret_overlap_seconds,
                )
                plaintext = hashlib.sha256(uuid4().bytes + uuid4().bytes).hexdigest()
                encrypted = cipher.encrypt(
                    plaintext.encode(),
                    tenant_id=actor.tenant_id,
                    endpoint_id=endpoint_id,
                    version=version,
                )
                repository.shorten_previous_version(
                    endpoint_id, version - 1, expires_at=overlap_end
                )
                repository.insert_secret(
                    {
                        "id": uuid4(),
                        "created_at": now,
                        "tenant_id": actor.tenant_id,
                        "endpoint_id": endpoint_id,
                        "version": version,
                        "key_id": encrypted.key_id,
                        "nonce": encrypted.nonce,
                        "ciphertext": encrypted.ciphertext,
                        "not_before": not_before,
                        "expires_at": expires_at,
                    }
                )
            return {
                "signing_secret": plaintext,
                "version": version,
                "not_before": not_before,
                "expires_at": expires_at,
            }
        finally:
            session.close()

    @router.post("/{endpoint_id}/status", response_model=EndpointView)
    def disable(
        endpoint_id: UUID,
        body: DisableRequest,
        auth: tuple[Session, AuthenticatedPrincipal] = Depends(principal),
    ) -> Any:
        session, actor = auth
        try:
            with tenant_transaction(session, actor):
                repository = EndpointRepository(session, actor.tenant_id)
                if not repository.disable(
                    endpoint_id, revoked=body.action == "revoke", now=datetime.now(UTC)
                ):
                    raise HTTPException(404, "integration endpoint not found")
                value = repository.get(endpoint_id)
                assert value is not None
                return value
        finally:
            session.close()

    return router
