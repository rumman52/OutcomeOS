# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from outcomeos_api.contracts.domain import (
    BasisPoints,
    FixedFee,
    RuleVersion,
    canonical_document,
    document_digest,
    validate_currency,
    validate_timezone,
)
from outcomeos_api.contracts.repositories import ContractRepository
from outcomeos_api.db import AuthenticatedPrincipal
from outcomeos_api.domain import DomainError


class ContractCommandError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ContractService:
    """Transactional application service; HTTP and lifecycle concerns remain separate."""

    def __init__(
        self, session: Session, principal: AuthenticatedPrincipal, *, actor_type: str = "human"
    ) -> None:
        self.session = session
        self.principal = principal
        self.repo = ContractRepository(session, principal.tenant_id)
        self.actor_type = actor_type

    def _record(self, **values: Any) -> None:
        self.repo.record(actor_type=self.actor_type, **values)

    def _run(self, key: str, request: dict[str, Any], operation: Any) -> dict[str, Any]:
        digest = hashlib.sha256(
            json.dumps(request, sort_keys=True, default=str, separators=(",", ":")).encode()
        ).hexdigest()
        try:
            prior = self.repo.command_result(key, digest)
        except ValueError as error:
            raise ContractCommandError("idempotency_conflict") from error
        if prior is not None:
            return prior
        result: dict[str, Any] = operation()
        self.repo.remember(key, digest, result)
        return result

    def create_contract(self, key: str) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            identifier = uuid4()
            self.session.execute(
                text(
                    "INSERT INTO performance_contracts(id,tenant_id,created_by) VALUES(:id,:tenant,:actor)"
                ),
                {
                    "id": identifier,
                    "tenant": self.principal.tenant_id,
                    "actor": self.principal.user_id,
                },
            )
            result = {"id": str(identifier), "state": "draft", "lock_version": 0}
            self._record(
                event_type="contract_created",
                aggregate_type="performance_contract",
                aggregate_id=identifier,
                actor_id=self.principal.user_id,
                metadata={"new_state": "draft", "idempotency_key": key},
            )
            return result

        return self._run(key, {"command": "create_contract"}, operation)

    def create_rule(self, key: str, name: str) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            identifier = uuid4()
            self.session.execute(
                text(
                    "INSERT INTO outcome_rules(id,tenant_id,name,created_by) VALUES(:id,:tenant,:name,:actor)"
                ),
                {
                    "id": identifier,
                    "tenant": self.principal.tenant_id,
                    "name": name,
                    "actor": self.principal.user_id,
                },
            )
            result = {"id": str(identifier), "name": name}
            self._record(
                event_type="outcome_rule_created",
                aggregate_type="outcome_rule",
                aggregate_id=identifier,
                actor_id=self.principal.user_id,
                metadata={"idempotency_key": key},
            )
            return result

        return self._run(key, {"command": "create_rule", "name": name}, operation)

    def create_rule_version(self, key: str, rule_id: UUID, body: dict[str, Any]) -> dict[str, Any]:
        try:
            RuleVersion("validation", 1, body["template_id"], body["definition"])
        except DomainError as error:
            raise ContractCommandError("invalid_rule_definition") from error

        def operation() -> dict[str, Any]:
            if self.repo.one("outcome_rules", rule_id) is None:
                raise ContractCommandError("resource_not_found")
            identifier = uuid4()
            version = self.session.execute(
                text(
                    "SELECT COALESCE(MAX(version),0)+1 FROM outcome_rule_versions WHERE tenant_id=:tenant AND rule_id=:rule"
                ),
                {"tenant": self.principal.tenant_id, "rule": rule_id},
            ).scalar_one()
            definition = body["definition"]
            self.session.execute(
                text("""INSERT INTO outcome_rule_versions(id,tenant_id,rule_id,version,schema_version,template_id,definition,created_by)
                VALUES(:id,:tenant,:rule,:version,1,:template,CAST(:definition AS jsonb),:actor)"""),
                {
                    "id": identifier,
                    "tenant": self.principal.tenant_id,
                    "rule": rule_id,
                    "version": version,
                    "template": body["template_id"],
                    "definition": canonical_document(definition),
                    "actor": self.principal.user_id,
                },
            )
            result = {
                "id": str(identifier),
                "rule_id": str(rule_id),
                "version": version,
                "state": "draft",
                "digest": None,
            }
            self._record(
                event_type="rule_version_created",
                aggregate_type="outcome_rule",
                aggregate_id=rule_id,
                actor_id=self.principal.user_id,
                metadata={"version": version, "idempotency_key": key},
            )
            return result

        return self._run(
            key, {"command": "create_rule_version", "rule": str(rule_id), **body}, operation
        )

    def transition_rule(
        self, key: str, rule_id: UUID, version_id: UUID, action: str
    ) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            row = self.repo.version("outcome_rule_versions", "rule_id", rule_id, version_id)
            if row is None:
                raise ContractCommandError("resource_not_found")
            expected, target = (
                ("draft", "published") if action == "publish" else ("published", "retired")
            )
            if row["state"] != expected:
                raise ContractCommandError("invalid_lifecycle")
            if action == "publish":
                try:
                    RuleVersion(
                        str(version_id),
                        int(row["version"]),
                        str(row["template_id"]),
                        row["definition"],
                    )
                except DomainError as error:
                    raise ContractCommandError("invalid_rule_definition") from error
            digest = document_digest(row["definition"])
            self.session.execute(
                text("""UPDATE outcome_rule_versions SET state=:target,
                canonical_document=COALESCE(canonical_document,:document), digest=COALESCE(digest,:digest),
                published_by=CASE WHEN :target='published' THEN :actor ELSE published_by END,
                published_at=CASE WHEN :target='published' THEN :now ELSE published_at END
                WHERE tenant_id=:tenant AND id=:id"""),
                {
                    "target": target,
                    "document": canonical_document(row["definition"]),
                    "digest": digest,
                    "actor": self.principal.user_id,
                    "now": datetime.now(UTC),
                    "tenant": self.principal.tenant_id,
                    "id": version_id,
                },
            )
            result = {
                "id": str(version_id),
                "rule_id": str(rule_id),
                "version": row["version"],
                "state": target,
                "digest": digest,
            }
            self._record(
                event_type=f"rule_version_{action}ed",
                aggregate_type="outcome_rule",
                aggregate_id=rule_id,
                actor_id=self.principal.user_id,
                metadata={
                    "previous_state": expected,
                    "new_state": target,
                    "version": row["version"],
                    "digest": digest,
                    "idempotency_key": key,
                },
            )
            return result

        return self._run(
            key, {"command": action, "rule": str(rule_id), "version": str(version_id)}, operation
        )

    def create_contract_version(
        self, key: str, contract_id: UUID, body: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            body = dict(body)
            body["currency"] = validate_currency(body["currency"])
            body["contract_timezone"] = validate_timezone(body["contract_timezone"])
            if body["pricing_model"] == "fixed_fee":
                FixedFee(body["fixed_fee_minor"], body["currency"])
            else:
                BasisPoints(
                    body["rate_basis_points"],
                    body["currency"],
                    body.get("floor_minor"),
                    body.get("cap_minor"),
                )
        except (DomainError, KeyError) as error:
            raise ContractCommandError("invalid_contract_terms") from error

        def operation() -> dict[str, Any]:
            if self.repo.lock_contract(contract_id) is None:
                raise ContractCommandError("resource_not_found")
            rule = self.session.execute(
                text("SELECT state FROM outcome_rule_versions WHERE tenant_id=:tenant AND id=:id"),
                {"tenant": self.principal.tenant_id, "id": body["rule_version_id"]},
            ).scalar_one_or_none()
            if rule != "published":
                raise ContractCommandError("published_rule_required")
            identifier = uuid4()
            version = self.session.execute(
                text(
                    "SELECT COALESCE(MAX(version),0)+1 FROM performance_contract_versions WHERE tenant_id=:tenant AND contract_id=:contract"
                ),
                {"tenant": self.principal.tenant_id, "contract": contract_id},
            ).scalar_one()
            values = {
                **body,
                "id": identifier,
                "tenant": self.principal.tenant_id,
                "contract": contract_id,
                "version": version,
                "actor": self.principal.user_id,
                "roles": json.dumps(body["required_party_roles"]),
                "terms_json": canonical_document(body["terms"]),
            }
            self.session.execute(
                text("""INSERT INTO performance_contract_versions
                (id,tenant_id,contract_id,version,display_name,description,required_party_roles,rule_version_id,contract_timezone,currency,pricing_model,fixed_fee_minor,rate_basis_points,floor_minor,cap_minor,anchor_event_type,attribution_window_seconds,evaluation_window_seconds,finalization_window_seconds,effective_start,effective_end,terms,created_by)
                VALUES(:id,:tenant,:contract,:version,:display_name,:description,CAST(:roles AS jsonb),:rule_version_id,:contract_timezone,:currency,:pricing_model,:fixed_fee_minor,:rate_basis_points,:floor_minor,:cap_minor,:anchor_event_type,:attribution_window_seconds,:evaluation_window_seconds,:finalization_window_seconds,:effective_start,:effective_end,CAST(:terms_json AS jsonb),:actor)"""),
                values,
            )
            result = {
                "id": str(identifier),
                "contract_id": str(contract_id),
                "version": version,
                "state": "draft",
                "digest": None,
            }
            self._record(
                event_type="contract_version_created",
                aggregate_type="performance_contract",
                aggregate_id=contract_id,
                actor_id=self.principal.user_id,
                metadata={"version": version, "idempotency_key": key},
            )
            return result

        request = {"command": "create_contract_version", "contract": str(contract_id), **body}
        return self._run(key, request, operation)

    def transition_contract_version(
        self,
        key: str,
        contract_id: UUID,
        version_id: UUID,
        action: str,
        *,
        digest: str | None = None,
        party_role: str | None = None,
        human: bool = True,
    ) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            if self.repo.lock_contract(contract_id) is None:
                raise ContractCommandError("resource_not_found")
            row = self.repo.version(
                "performance_contract_versions", "contract_id", contract_id, version_id
            )
            if row is None:
                raise ContractCommandError("resource_not_found")
            target = row["state"]
            actual_digest = row["digest"]
            if action == "propose":
                if row["state"] != "draft":
                    raise ContractCommandError("invalid_lifecycle")
                actual_digest = document_digest(row["terms"])
                target = "proposed"
                self.session.execute(
                    text(
                        "UPDATE performance_contract_versions SET state='proposed',canonical_document=:document,digest=:digest WHERE tenant_id=:tenant AND id=:id"
                    ),
                    {
                        "document": canonical_document(row["terms"]),
                        "digest": actual_digest,
                        "tenant": self.principal.tenant_id,
                        "id": version_id,
                    },
                )
            elif action == "accept":
                if not human:
                    raise ContractCommandError("human_principal_required")
                authority = self.session.execute(
                    text(
                        "SELECT 1 FROM contract_party_authorities WHERE tenant_id=:tenant AND contract_id=:contract AND party_role=:role AND principal_id=:actor"
                    ),
                    {
                        "tenant": self.principal.tenant_id,
                        "contract": contract_id,
                        "role": party_role,
                        "actor": self.principal.user_id,
                    },
                ).scalar_one_or_none()
                if row["state"] != "proposed" or digest != actual_digest or authority is None:
                    raise ContractCommandError("acceptance_not_authorized")
                self.session.execute(
                    text(
                        "INSERT INTO contract_party_acceptances(tenant_id,contract_version_id,digest,party_role,principal_id,accepted_at) VALUES(:tenant,:version,:digest,:role,:actor,:now)"
                    ),
                    {
                        "tenant": self.principal.tenant_id,
                        "version": version_id,
                        "digest": digest,
                        "role": party_role,
                        "actor": self.principal.user_id,
                        "now": datetime.now(UTC),
                    },
                )
            elif action == "activate":
                roles = set(row["required_party_roles"])
                accepted = set(
                    self.session.execute(
                        text(
                            "SELECT party_role FROM contract_party_acceptances WHERE tenant_id=:tenant AND contract_version_id=:version AND digest=:digest"
                        ),
                        {
                            "tenant": self.principal.tenant_id,
                            "version": version_id,
                            "digest": actual_digest,
                        },
                    ).scalars()
                )
                if row["state"] != "proposed" or roles != accepted:
                    raise ContractCommandError("acceptances_required")
                self.session.execute(
                    text(
                        "UPDATE performance_contract_versions SET state='superseded' WHERE tenant_id=:tenant AND contract_id=:contract AND state='active'"
                    ),
                    {"tenant": self.principal.tenant_id, "contract": contract_id},
                )
                self.session.execute(
                    text(
                        "UPDATE performance_contract_versions SET state='active' WHERE tenant_id=:tenant AND id=:id"
                    ),
                    {"tenant": self.principal.tenant_id, "id": version_id},
                )
                self.session.execute(
                    text(
                        "UPDATE performance_contracts SET state='active',lock_version=lock_version+1 WHERE tenant_id=:tenant AND id=:id"
                    ),
                    {"tenant": self.principal.tenant_id, "id": contract_id},
                )
                target = "active"
            result = {
                "id": str(version_id),
                "contract_id": str(contract_id),
                "version": row["version"],
                "state": target,
                "digest": actual_digest,
            }
            self._record(
                event_type=f"contract_version_{action}ed",
                aggregate_type="performance_contract",
                aggregate_id=contract_id,
                actor_id=self.principal.user_id,
                metadata={
                    "new_state": target,
                    "version": row["version"],
                    "digest": actual_digest,
                    "idempotency_key": key,
                },
            )
            return result

        return self._run(
            key,
            {
                "command": action,
                "contract": str(contract_id),
                "version": str(version_id),
                "digest": digest,
                "party_role": party_role,
            },
            operation,
        )

    def transition_contract(
        self, key: str, contract_id: UUID, action: str, lock_version: int | None
    ) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            row = self.repo.lock_contract(contract_id, lock_version)
            if row is None:
                raise ContractCommandError("concurrency_conflict")
            target = {"suspend": "suspended", "resume": "active", "terminate": "terminated"}[action]
            allowed = {
                ("active", "suspended"),
                ("suspended", "active"),
                ("draft", "terminated"),
                ("active", "terminated"),
                ("suspended", "terminated"),
            }
            if (row["state"], target) not in allowed:
                raise ContractCommandError("invalid_lifecycle")
            self.session.execute(
                text(
                    "UPDATE performance_contracts SET state=:state,lock_version=lock_version+1 WHERE tenant_id=:tenant AND id=:id"
                ),
                {"state": target, "tenant": self.principal.tenant_id, "id": contract_id},
            )
            result = {
                "id": str(contract_id),
                "state": target,
                "lock_version": row["lock_version"] + 1,
            }
            self._record(
                event_type=f"contract_{action}ed",
                aggregate_type="performance_contract",
                aggregate_id=contract_id,
                actor_id=self.principal.user_id,
                metadata={
                    "previous_state": row["state"],
                    "new_state": target,
                    "idempotency_key": key,
                },
            )
            return result

        return self._run(
            key,
            {"command": action, "contract": str(contract_id), "lock_version": lock_version},
            operation,
        )

    def provision_authority(
        self, key: str, contract_id: UUID, party_role: str, principal_id: UUID
    ) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            if self.repo.lock_contract(contract_id) is None:
                raise ContractCommandError("resource_not_found")
            identifier = uuid4()
            self.session.execute(
                text("""INSERT INTO contract_party_authorities
                (id,tenant_id,contract_id,party_role,principal_id)
                VALUES(:id,:tenant,:contract,:role,:principal)"""),
                {
                    "id": identifier,
                    "tenant": self.principal.tenant_id,
                    "contract": contract_id,
                    "role": party_role,
                    "principal": principal_id,
                },
            )
            result = {
                "id": str(identifier),
                "contract_id": str(contract_id),
                "party_role": party_role,
                "principal_id": str(principal_id),
            }
            self._record(
                event_type="contract_party_authority_granted",
                aggregate_type="performance_contract",
                aggregate_id=contract_id,
                actor_id=self.principal.user_id,
                metadata={"result": "granted", "idempotency_key": key},
            )
            return result

        return self._run(
            key,
            {
                "command": "provision_authority",
                "contract": str(contract_id),
                "role": party_role,
                "principal": str(principal_id),
            },
            operation,
        )

    def create_binding(self, key: str, contract_id: UUID, body: dict[str, Any]) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            if self.repo.lock_contract(contract_id) is None:
                raise ContractCommandError("resource_not_found")
            identifier = uuid4()
            self.session.execute(
                text("""INSERT INTO contract_source_bindings
                (id,tenant_id,contract_id,source_type,source_id,effective_start,effective_end,created_by)
                VALUES(:id,:tenant,:contract,:type,:source,:start,:end,:actor)"""),
                {
                    "id": identifier,
                    "tenant": self.principal.tenant_id,
                    "contract": contract_id,
                    "type": body["source_type"],
                    "source": body["source_id"],
                    "start": body["effective_start"],
                    "end": body.get("effective_end"),
                    "actor": self.principal.user_id,
                },
            )
            result = {"id": str(identifier), "contract_id": str(contract_id), **body}
            self._record(
                event_type="contract_source_binding_created",
                aggregate_type="performance_contract",
                aggregate_id=contract_id,
                actor_id=self.principal.user_id,
                metadata={"idempotency_key": key},
            )
            return result

        return self._run(
            key, {"command": "create_binding", "contract": str(contract_id), **body}, operation
        )
