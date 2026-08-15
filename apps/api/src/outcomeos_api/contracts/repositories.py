# ruff: noqa: E501
from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session


class ContractRepository:
    """SQL adapter whose every operation is scoped by an authenticated tenant."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    def one(self, table: str, resource_id: UUID) -> RowMapping | None:
        if table not in {"performance_contracts", "outcome_rules"}:
            raise ValueError("unsupported aggregate")
        return (
            self.session.execute(
                text(f"SELECT * FROM {table} WHERE tenant_id=:tenant AND id=:id"),
                {"tenant": self.tenant_id, "id": resource_id},
            )
            .mappings()
            .one_or_none()
        )

    def list(self, table: str, *, after: UUID | None, limit: int) -> Sequence[RowMapping]:
        if table not in {"performance_contracts", "outcome_rules"}:
            raise ValueError("unsupported aggregate")
        return (
            self.session.execute(
                text(
                    f"SELECT * FROM {table} WHERE tenant_id=:tenant AND (:after IS NULL OR id>:after) ORDER BY id LIMIT :limit"
                ),
                {"tenant": self.tenant_id, "after": after, "limit": limit},
            )
            .mappings()
            .all()
        )

    def version(
        self, table: str, parent_column: str, parent_id: UUID, version_id: UUID
    ) -> RowMapping | None:
        allowed = {
            ("performance_contract_versions", "contract_id"),
            ("outcome_rule_versions", "rule_id"),
        }
        if (table, parent_column) not in allowed:
            raise ValueError("unsupported version")
        return (
            self.session.execute(
                text(
                    f"SELECT * FROM {table} WHERE tenant_id=:tenant AND {parent_column}=:parent AND id=:id"
                ),
                {"tenant": self.tenant_id, "parent": parent_id, "id": version_id},
            )
            .mappings()
            .one_or_none()
        )

    def bindings(self, contract_id: UUID) -> Sequence[RowMapping]:
        return (
            self.session.execute(
                text("""SELECT id,contract_id,source_type,source_id,effective_start,effective_end,created_at
            FROM contract_source_bindings WHERE tenant_id=:tenant AND contract_id=:contract
            ORDER BY effective_start,id"""),
                {"tenant": self.tenant_id, "contract": contract_id},
            )
            .mappings()
            .all()
        )

    def lock_contract(
        self, contract_id: UUID, lock_version: int | None = None
    ) -> RowMapping | None:
        return (
            self.session.execute(
                text("""SELECT * FROM performance_contracts
            WHERE tenant_id=:tenant AND id=:id AND (:lock IS NULL OR lock_version=:lock)
            FOR UPDATE"""),
                {"tenant": self.tenant_id, "id": contract_id, "lock": lock_version},
            )
            .mappings()
            .one_or_none()
        )

    def command_result(self, key: str, digest: str) -> dict[str, Any] | None:
        row = (
            self.session.execute(
                text(
                    "SELECT request_digest,response FROM contract_command_results WHERE tenant_id=:tenant AND idempotency_key=:key FOR UPDATE"
                ),
                {"tenant": self.tenant_id, "key": key},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        if row["request_digest"] != digest:
            raise ValueError("idempotency_conflict")
        return dict(row["response"])

    def remember(self, key: str, digest: str, response: dict[str, Any]) -> None:
        self.session.execute(
            text(
                "INSERT INTO contract_command_results(tenant_id,idempotency_key,request_digest,response) VALUES(:tenant,:key,:digest,CAST(:response AS jsonb))"
            ),
            {
                "tenant": self.tenant_id,
                "key": key,
                "digest": digest,
                "response": __import__("json").dumps(response),
            },
        )

    def record(
        self,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID | None,
        actor_id: UUID,
        actor_type: str,
        metadata: dict[str, Any],
    ) -> None:
        from uuid import uuid4

        safe = {
            key: value
            for key, value in metadata.items()
            if key
            in {
                "previous_state",
                "new_state",
                "version",
                "digest",
                "reason",
                "idempotency_key",
                "result",
            }
        }
        self.session.execute(
            text(
                "INSERT INTO audit_events(id,created_at,tenant_id,actor_user_id,action,resource_type,resource_id,correlation_id,details) VALUES(:id,:now,:tenant,:actor,:event,:kind,:aggregate,:correlation,CAST(:metadata AS jsonb))"
            ),
            {
                "id": uuid4(),
                "now": datetime.now(UTC),
                "tenant": self.tenant_id,
                "actor": actor_id,
                "event": event_type,
                "kind": aggregate_type,
                "aggregate": aggregate_id,
                "correlation": str(metadata.get("idempotency_key", "selection"))[:100],
                "metadata": json.dumps(safe),
            },
        )
        self.session.execute(
            text(
                "INSERT INTO contract_domain_outbox(tenant_id,event_type,aggregate_type,aggregate_id,actor_id,actor_type,metadata) VALUES(:tenant,:event,:kind,:aggregate,:actor,:actor_type,CAST(:metadata AS jsonb))"
            ),
            {
                "tenant": self.tenant_id,
                "event": event_type,
                "kind": aggregate_type,
                "aggregate": aggregate_id,
                "actor": actor_id,
                "actor_type": actor_type,
                "metadata": json.dumps(safe),
            },
        )
