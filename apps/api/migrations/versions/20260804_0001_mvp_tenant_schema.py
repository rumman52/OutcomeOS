"""Create the tenant-isolated MVP schema.

Revision ID: 20260804_0001
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "20260804_0001"
down_revision = None
branch_labels = None
depends_on = None


def _common():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    ]


def _tenant_owned():
    return [sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False)]


def _external():
    return [
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
    ]


def _money():
    return [
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
    ]


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table("tenants", *_common(), sa.Column("name", sa.String(200), nullable=False))
    op.create_table(
        "users", *_common(), sa.Column("email", sa.String(320), nullable=False, unique=True)
    )
    op.create_table(
        "memberships",
        *_common(),
        *_tenant_owned(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_memberships_tenant_user"),
    )
    op.create_table(
        "contacts",
        *_common(),
        *_tenant_owned(),
        *_external(),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.UniqueConstraint("tenant_id", "provider", "external_id", name="uq_contacts_external"),
    )
    op.create_table(
        "conversations",
        *_common(),
        *_tenant_owned(),
        *_external(),
        sa.Column("contact_id", sa.Uuid(), sa.ForeignKey("contacts.id")),
        sa.Column("subject", sa.String(500)),
        sa.UniqueConstraint(
            "tenant_id", "provider", "external_id", name="uq_conversations_external"
        ),
    )
    op.create_table(
        "knowledge_documents",
        *_common(),
        *_tenant_owned(),
        *_external(),
        sa.Column("title", sa.String(500), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "provider", "external_id", name="uq_knowledge_documents_external"
        ),
    )
    op.create_table(
        "knowledge_chunks",
        *_common(),
        *_tenant_owned(),
        sa.Column(
            "document_id", sa.Uuid(), sa.ForeignKey("knowledge_documents.id"), nullable=False
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536)),
        sa.UniqueConstraint(
            "tenant_id", "document_id", "chunk_index", name="uq_knowledge_chunks_position"
        ),
    )
    op.create_table(
        "orders",
        *_common(),
        *_tenant_owned(),
        *_external(),
        *_money(),
        sa.Column("contact_id", sa.Uuid(), sa.ForeignKey("contacts.id")),
        sa.Column("status", sa.String(32), nullable=False),
        sa.UniqueConstraint("tenant_id", "provider", "external_id", name="uq_orders_external"),
    )
    op.create_table(
        "outcomes",
        *_common(),
        *_tenant_owned(),
        *_external(),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id")),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.UniqueConstraint("tenant_id", "provider", "external_id", name="uq_outcomes_external"),
    )
    op.create_table(
        "dispute_evidence",
        *_common(),
        *_tenant_owned(),
        *_external(),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "provider", "external_id", name="uq_dispute_evidence_external"
        ),
    )
    op.create_table(
        "billable_results",
        *_common(),
        *_tenant_owned(),
        *_external(),
        *_money(),
        sa.Column("outcome_id", sa.Uuid(), sa.ForeignKey("outcomes.id"), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "provider", "external_id", name="uq_billable_results_external"
        ),
    )
    op.create_table(
        "ledger_entries",
        *_common(),
        *_tenant_owned(),
        *_external(),
        *_money(),
        sa.Column("billable_result_id", sa.Uuid(), sa.ForeignKey("billable_results.id")),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "provider", "external_id", name="uq_ledger_entries_external"
        ),
    )

    tenant_tables = (
        "memberships",
        "contacts",
        "conversations",
        "knowledge_documents",
        "knowledge_chunks",
        "orders",
        "outcomes",
        "dispute_evidence",
        "billable_results",
        "ledger_entries",
    )
    for table in tenant_tables:
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])

    # FORCE protects even when the application connects as table owner. The empty
    # setting is converted to NULL, making unscoped reads and writes fail closed.
    high_risk = (
        "contacts",
        "conversations",
        "knowledge_chunks",
        "orders",
        "outcomes",
        "dispute_evidence",
        "billable_results",
        "ledger_entries",
    )
    for table in high_risk:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f'''CREATE POLICY tenant_isolation ON "{table}"
                USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)'''
        )


def downgrade():
    for table in (
        "ledger_entries",
        "billable_results",
        "dispute_evidence",
        "outcomes",
        "orders",
        "knowledge_chunks",
        "knowledge_documents",
        "conversations",
        "contacts",
        "memberships",
        "users",
        "tenants",
    ):
        op.drop_table(table)
    op.execute("DROP EXTENSION IF EXISTS vector")
