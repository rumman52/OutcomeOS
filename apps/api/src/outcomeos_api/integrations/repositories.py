from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, RowMapping, text
from sqlalchemy.orm import Session


class EndpointRepository:
    """Every management query is SQL-scoped to the authenticated tenant."""

    def __init__(self, session: Session, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    def list(self) -> Sequence[RowMapping]:
        return (
            self.session.execute(
                text("""SELECT id, provider, name, status, created_at, revoked_at
                      FROM integration_endpoints WHERE tenant_id=:tenant_id ORDER BY created_at"""),
                {"tenant_id": self.tenant_id},
            )
            .mappings()
            .all()
        )

    def get(self, endpoint_id: UUID) -> RowMapping | None:
        return (
            self.session.execute(
                text("""SELECT id, provider, name, status, created_at, revoked_at
                      FROM integration_endpoints WHERE tenant_id=:tenant_id AND id=:id"""),
                {"tenant_id": self.tenant_id, "id": endpoint_id},
            )
            .mappings()
            .one_or_none()
        )

    def insert(self, endpoint: dict[str, Any], secret: dict[str, Any]) -> None:
        self.session.execute(
            text("""INSERT INTO integration_endpoints
                (id,created_at,tenant_id,provider,name,public_token_digest,status)
                VALUES
                (:id,:created_at,:tenant_id,:provider,:name,:public_token_digest,'active')"""),
            endpoint,
        )
        self.session.execute(
            text("""INSERT INTO integration_secret_versions
                (id,created_at,tenant_id,endpoint_id,version,key_id,nonce,ciphertext,not_before,expires_at)
                VALUES (:id,:created_at,:tenant_id,:endpoint_id,:version,:key_id,:nonce,:ciphertext,
                        :not_before,:expires_at)"""),
            secret,
        )

    def disable(self, endpoint_id: UUID, *, revoked: bool, now: datetime) -> bool:
        status = "revoked" if revoked else "disabled"
        result = self.session.execute(
            text("""UPDATE integration_endpoints SET status=:status,
                      revoked_at=CASE WHEN :status='revoked' THEN :now ELSE revoked_at END
                      WHERE tenant_id=:tenant_id AND id=:id AND status='active'"""),
            {"status": status, "now": now, "tenant_id": self.tenant_id, "id": endpoint_id},
        )
        return cast(CursorResult[Any], result).rowcount == 1

    def lock_latest_version(self, endpoint_id: UUID) -> RowMapping | None:
        return (
            self.session.execute(
                text("""SELECT version, expires_at FROM integration_secret_versions
                      WHERE tenant_id=:tenant_id AND endpoint_id=:id
                      ORDER BY version DESC LIMIT 1 FOR UPDATE"""),
                {"tenant_id": self.tenant_id, "id": endpoint_id},
            )
            .mappings()
            .one_or_none()
        )

    def insert_secret(self, values: dict[str, Any]) -> None:
        self.session.execute(
            text("""INSERT INTO integration_secret_versions
                (id,created_at,tenant_id,endpoint_id,version,key_id,nonce,ciphertext,
                 not_before,expires_at)
                VALUES (:id,:created_at,:tenant_id,:endpoint_id,:version,:key_id,:nonce,
                        :ciphertext,:not_before,:expires_at)"""),
            values,
        )

    def shorten_previous_version(
        self, endpoint_id: UUID, version: int, *, expires_at: datetime
    ) -> None:
        self.session.execute(
            text("""UPDATE integration_secret_versions
                  SET expires_at=LEAST(expires_at,:expires_at)
                  WHERE tenant_id=:tenant_id AND endpoint_id=:id AND version=:version"""),
            {
                "tenant_id": self.tenant_id,
                "id": endpoint_id,
                "version": version,
                "expires_at": expires_at,
            },
        )
