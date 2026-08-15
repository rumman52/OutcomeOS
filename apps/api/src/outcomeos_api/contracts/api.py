# ruff: noqa: E501
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from outcomeos_api.auth.api_keys import ApiKeyHasher
from outcomeos_api.auth.jwt import JwtVerifier, load_oidc_jwks
from outcomeos_api.auth.service import principal_for_api_key, principal_for_oidc_claims
from outcomeos_api.config import Settings
from outcomeos_api.contracts.repositories import ContractRepository
from outcomeos_api.contracts.service import ContractCommandError, ContractService
from outcomeos_api.db import AuthenticatedPrincipal, TenantAccessError, tenant_transaction


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RuleCreate(StrictBody):
    name: str = Field(min_length=1, max_length=160)


class RuleVersionCreate(StrictBody):
    template_id: Literal[
        "delivered_paid_order",
        "attended_booking",
        "qualified_lead_accepted",
        "paid_activated_subscription",
    ]
    definition: dict[str, Any]


class ContractVersionCreate(StrictBody):
    display_name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    required_party_roles: list[str] = Field(min_length=1, max_length=20)
    rule_version_id: UUID
    contract_timezone: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    pricing_model: Literal["fixed_fee", "basis_points"]
    fixed_fee_minor: int | None = None
    rate_basis_points: int | None = None
    floor_minor: int | None = None
    cap_minor: int | None = None
    anchor_event_type: str = Field(min_length=1, max_length=160)
    attribution_window_seconds: int = Field(ge=0)
    evaluation_window_seconds: int = Field(ge=0)
    finalization_window_seconds: int = Field(ge=0)
    effective_start: datetime
    effective_end: datetime | None = None
    terms: dict[str, Any]


class AcceptanceBody(StrictBody):
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    party_role: str = Field(min_length=1, max_length=64)


class BindingCreate(StrictBody):
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=255)
    effective_start: datetime
    effective_end: datetime | None = None


class AuthorityCreate(StrictBody):
    party_role: str = Field(min_length=1, max_length=64)
    principal_id: UUID


def contracts_router(settings: Settings, sessions: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["contracts"])

    verifier: JwtVerifier | None = None
    if settings.oidc_issuer and settings.oidc_audience:
        verifier = JwtVerifier(
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            jwks=load_oidc_jwks(
                issuer=settings.oidc_issuer,
                jwks_url=settings.oidc_jwks_url,
                discovery_url=settings.oidc_discovery_url,
            ),
        )

    def auth(
        authorization: Annotated[str | None, Header()] = None,
        selected_tenant: Annotated[UUID | None, Header(alias="X-OutcomeOS-Tenant")] = None,
    ) -> tuple[Session, AuthenticatedPrincipal, bool]:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(403, "contract management permission required")
        session = sessions()
        try:
            token = authorization.removeprefix("Bearer ")
            human = not token.startswith("oos_live_")
            if human:
                if verifier is None or selected_tenant is None:
                    raise TenantAccessError("verified human identity required")
                principal = principal_for_oidc_claims(
                    session,
                    claims=verifier.verify(token),
                    selected_tenant_id=selected_tenant,
                )
                role = session.execute(
                    __import__("sqlalchemy").text(
                        "SELECT role FROM memberships WHERE tenant_id=:tenant AND id=:membership"
                    ),
                    {"tenant": principal.tenant_id, "membership": principal.membership_id},
                ).scalar_one()
                if role not in {"owner", "administrator"}:
                    raise TenantAccessError("data write permission required")
            else:
                principal = principal_for_api_key(
                    session,
                    plaintext=token,
                    required_scope="data:write",
                    hasher=ApiKeyHasher(settings.api_key_pepper),
                )
            session.rollback()
            return session, principal, human
        except (TenantAccessError, ValueError) as error:
            session.close()
            raise HTTPException(403, "contract management permission required") from error

    def command(
        key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
    ) -> str:
        return key

    def execute(auth_value: tuple[Session, AuthenticatedPrincipal, bool], callback: Any) -> Any:
        session, actor, human = auth_value
        try:
            with tenant_transaction(session, actor):
                return callback(
                    ContractService(session, actor, actor_type="human" if human else "api_key")
                )
        except ContractCommandError as error:
            status = 404 if error.code == "resource_not_found" else 409
            if error.code in {"human_principal_required", "acceptance_not_authorized"}:
                status = 403
            raise HTTPException(status, error.code) from error
        finally:
            session.close()

    @router.post("/contracts", status_code=201)
    def create_contract(
        key: str = Depends(command),
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        return execute(value, lambda service: service.create_contract(key))

    @router.get("/contracts")
    def list_contracts(
        after: UUID | None = None,
        limit: int = Query(50, ge=1, le=100),
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        session, actor, _ = value
        try:
            with tenant_transaction(session, actor):
                return list(
                    ContractRepository(session, actor.tenant_id).list(
                        "performance_contracts", after=after, limit=limit
                    )
                )
        finally:
            session.close()

    @router.get("/contracts/{contract_id}")
    def get_contract(
        contract_id: UUID, value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth)
    ) -> Any:
        session, actor, _ = value
        try:
            with tenant_transaction(session, actor):
                result = ContractRepository(session, actor.tenant_id).one(
                    "performance_contracts", contract_id
                )
            if result is None:
                raise HTTPException(404, "resource_not_found")
            return result
        finally:
            session.close()

    @router.post("/contracts/{contract_id}/versions", status_code=201)
    def create_version(
        contract_id: UUID,
        body: ContractVersionCreate,
        key: str = Depends(command),
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        return execute(
            value,
            lambda service: service.create_contract_version(key, contract_id, body.model_dump()),
        )

    @router.get("/contracts/{contract_id}/versions/{version_id}")
    def get_version(
        contract_id: UUID,
        version_id: UUID,
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        session, actor, _ = value
        try:
            with tenant_transaction(session, actor):
                result = ContractRepository(session, actor.tenant_id).version(
                    "performance_contract_versions", "contract_id", contract_id, version_id
                )
            if result is None:
                raise HTTPException(404, "resource_not_found")
            return result
        finally:
            session.close()

    @router.post("/contracts/{contract_id}/versions/{version_id}/propose")
    def propose_version(
        contract_id: UUID,
        version_id: UUID,
        key: str = Depends(command),
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        return execute(
            value,
            lambda service: service.transition_contract_version(
                key, contract_id, version_id, "propose"
            ),
        )

    @router.post("/contracts/{contract_id}/versions/{version_id}/accept")
    def accept(
        contract_id: UUID,
        version_id: UUID,
        body: AcceptanceBody,
        key: str = Depends(command),
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        human = value[2]
        return execute(
            value,
            lambda service: service.transition_contract_version(
                key,
                contract_id,
                version_id,
                "accept",
                digest=body.digest,
                party_role=body.party_role,
                human=human,
            ),
        )

    @router.post("/contracts/{contract_id}/versions/{version_id}/activate")
    def activate_version(
        contract_id: UUID,
        version_id: UUID,
        key: str = Depends(command),
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        return execute(
            value,
            lambda service: service.transition_contract_version(
                key, contract_id, version_id, "activate"
            ),
        )

    def change_contract_state(
        contract_id: UUID,
        action: str,
        key: str,
        if_match: int | None,
        value: tuple[Session, AuthenticatedPrincipal, bool],
    ) -> Any:
        return execute(
            value, lambda service: service.transition_contract(key, contract_id, action, if_match)
        )

    @router.post("/contracts/{contract_id}/suspend")
    def suspend_contract(
        contract_id: UUID,
        key: str = Depends(command),
        if_match: Annotated[int | None, Header(alias="If-Match")] = None,
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        return change_contract_state(contract_id, "suspend", key, if_match, value)

    @router.post("/contracts/{contract_id}/resume")
    def resume_contract(
        contract_id: UUID,
        key: str = Depends(command),
        if_match: Annotated[int | None, Header(alias="If-Match")] = None,
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        return change_contract_state(contract_id, "resume", key, if_match, value)

    @router.post("/contracts/{contract_id}/terminate")
    def terminate_contract(
        contract_id: UUID,
        key: str = Depends(command),
        if_match: Annotated[int | None, Header(alias="If-Match")] = None,
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        return change_contract_state(contract_id, "terminate", key, if_match, value)

    @router.post("/outcome-rules", status_code=201)
    def create_rule(
        body: RuleCreate,
        key: str = Depends(command),
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        return execute(value, lambda service: service.create_rule(key, body.name))

    @router.get("/outcome-rules")
    def list_rules(
        after: UUID | None = None,
        limit: int = Query(50, ge=1, le=100),
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        session, actor, _ = value
        try:
            with tenant_transaction(session, actor):
                return list(
                    ContractRepository(session, actor.tenant_id).list(
                        "outcome_rules", after=after, limit=limit
                    )
                )
        finally:
            session.close()

    @router.get("/outcome-rules/{rule_id}")
    def get_rule(
        rule_id: UUID, value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth)
    ) -> Any:
        session, actor, _ = value
        try:
            with tenant_transaction(session, actor):
                result = ContractRepository(session, actor.tenant_id).one("outcome_rules", rule_id)
            if result is None:
                raise HTTPException(404, "resource_not_found")
            return result
        finally:
            session.close()

    @router.post("/outcome-rules/{rule_id}/versions", status_code=201)
    def create_rule_version(
        rule_id: UUID,
        body: RuleVersionCreate,
        key: str = Depends(command),
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        return execute(
            value, lambda service: service.create_rule_version(key, rule_id, body.model_dump())
        )

    @router.get("/outcome-rules/{rule_id}/versions/{version_id}")
    def get_rule_version(
        rule_id: UUID,
        version_id: UUID,
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        session, actor, _ = value
        try:
            with tenant_transaction(session, actor):
                result = ContractRepository(session, actor.tenant_id).version(
                    "outcome_rule_versions", "rule_id", rule_id, version_id
                )
            if result is None:
                raise HTTPException(404, "resource_not_found")
            return result
        finally:
            session.close()

    @router.post("/outcome-rules/{rule_id}/versions/{version_id}/{action}")
    def rule_action(
        rule_id: UUID,
        version_id: UUID,
        action: Literal["publish", "retire"],
        key: str = Depends(command),
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        return execute(
            value, lambda service: service.transition_rule(key, rule_id, version_id, action)
        )

    @router.post("/contracts/{contract_id}/source-bindings", status_code=201)
    def create_binding(
        contract_id: UUID,
        body: BindingCreate,
        key: str = Depends(command),
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        return execute(
            value, lambda service: service.create_binding(key, contract_id, body.model_dump())
        )

    @router.post("/contracts/{contract_id}/party-authorities", status_code=201)
    def provision_authority(
        contract_id: UUID,
        body: AuthorityCreate,
        key: str = Depends(command),
        value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth),
    ) -> Any:
        if not value[2]:
            raise HTTPException(403, "human_principal_required")
        return execute(
            value,
            lambda service: service.provision_authority(
                key, contract_id, body.party_role, body.principal_id
            ),
        )

    @router.get("/contracts/{contract_id}/source-bindings")
    def list_bindings(
        contract_id: UUID, value: tuple[Session, AuthenticatedPrincipal, bool] = Depends(auth)
    ) -> Any:
        session, actor, _ = value
        try:
            with tenant_transaction(session, actor):
                return list(ContractRepository(session, actor.tenant_id).bindings(contract_id))
        finally:
            session.close()

    return router
