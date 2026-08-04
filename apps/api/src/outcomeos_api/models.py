from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class TenantOwned:
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False, index=True
    )


class MoneyMixin:
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)


class Tenant(Base, IdMixin):
    __tablename__ = "tenants"
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class User(Base, IdMixin):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)


class Membership(Base, IdMixin, TenantOwned):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_memberships_tenant_user"),)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")


class ExternalMixin:
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)


class Contact(Base, IdMixin, TenantOwned, ExternalMixin):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "external_id", name="uq_contacts_external"),
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))


class Conversation(Base, IdMixin, TenantOwned, ExternalMixin):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "external_id", name="uq_conversations_external"),
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id"))
    subject: Mapped[str | None] = mapped_column(String(500))


class KnowledgeDocument(Base, IdMixin, TenantOwned, ExternalMixin):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "external_id",
            name="uq_knowledge_documents_external",
        ),
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)


class KnowledgeChunk(Base, IdMixin, TenantOwned):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "document_id",
            "chunk_index",
            name="uq_knowledge_chunks_position",
        ),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_documents.id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))


class Order(Base, IdMixin, TenantOwned, ExternalMixin, MoneyMixin):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "external_id", name="uq_orders_external"),
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id"))
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class Outcome(Base, IdMixin, TenantOwned, ExternalMixin):
    __tablename__ = "outcomes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "external_id", name="uq_outcomes_external"),
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"))
    kind: Mapped[str] = mapped_column(String(64), nullable=False)


class DisputeEvidence(Base, IdMixin, TenantOwned, ExternalMixin):
    __tablename__ = "dispute_evidence"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider", "external_id", name="uq_dispute_evidence_external"
        ),
    )
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)


class BillableResult(Base, IdMixin, TenantOwned, ExternalMixin, MoneyMixin):
    __tablename__ = "billable_results"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider", "external_id", name="uq_billable_results_external"
        ),
    )
    outcome_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outcomes.id"), nullable=False)


class LedgerEntry(Base, IdMixin, TenantOwned, ExternalMixin, MoneyMixin):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "external_id", name="uq_ledger_entries_external"),
        Index("ix_ledger_entries_tenant_created", "tenant_id", "created_at"),
    )
    billable_result_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("billable_results.id"))
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
