from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from .db import TenantAccessError
from .models import Base, KnowledgeChunk, TenantOwned


class TenantRepository[T: Base]:
    """Repository that always derives scope from transaction context."""

    def __init__(self, session: Session, model: type[T]):
        self.session = session
        self.model = model

    @property
    def tenant_id(self) -> UUID:
        tenant_id = self.session.info.get("tenant_id")
        if not isinstance(tenant_id, UUID):
            raise TenantAccessError("tenant transaction is required")
        return tenant_id

    def query(self) -> Select[tuple[T]]:
        return select(self.model).where(self.model.tenant_id == self.tenant_id)  # type: ignore[attr-defined]

    def get(self, record_id: UUID) -> T | None:
        return self.session.scalar(self.query().where(self.model.id == record_id))

    def add(self, record: T) -> T:
        if not isinstance(record, TenantOwned) or record.tenant_id != self.tenant_id:
            raise TenantAccessError("record belongs to another tenant")
        self.session.add(record)
        return record

    def delete(self, record_id: UUID) -> bool:
        record = self.get(record_id)
        if record is None:
            return False
        self.session.delete(record)
        return True


class KnowledgeRepository(TenantRepository[KnowledgeChunk]):
    def __init__(self, session: Session):
        super().__init__(session, KnowledgeChunk)

    def nearest(self, query_embedding: list[float], *, limit: int = 10) -> list[KnowledgeChunk]:
        """Apply tenant predicate in SQL before limiting or returning any vector result."""
        distance = KnowledgeChunk.embedding.l2_distance(query_embedding)
        statement = (
            self.query()
            .where(KnowledgeChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(limit)
        )
        return list(self.session.scalars(statement))
