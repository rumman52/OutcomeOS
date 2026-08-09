"""Add the global tenant, identity, authorization, and audit core.

Revision ID: 20260808_0002
Revises: 20260804_0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260808_0002"
down_revision = "20260804_0001"
branch_labels = None
depends_on = None

ROLES = (
    "owner",
    "administrator",
    "operator",
    "marketer",
    "analyst",
    "finance",
    "dispute_reviewer",
    "external_partner",
    "read_only",
)

TENANT_TABLES = (
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
    "invitations",
    "api_keys",
    "external_grants",
    "audit_events",
)


def _rls(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
    op.execute(
        f'''CREATE POLICY tenant_isolation ON "{table}"
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)'''
    )


def upgrade() -> None:
    op.add_column(
        "tenants", sa.Column("country_code", sa.String(2), nullable=False, server_default="US")
    )
    op.add_column(
        "tenants", sa.Column("currency", sa.String(3), nullable=False, server_default="USD")
    )
    op.add_column(
        "tenants", sa.Column("locale", sa.String(35), nullable=False, server_default="en-US")
    )
    op.add_column(
        "tenants", sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC")
    )
    op.add_column(
        "tenants", sa.Column("business_type", sa.String(32), nullable=False, server_default="other")
    )
    op.add_column("tenants", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.create_check_constraint("ck_tenants_country_code", "tenants", "country_code ~ '^[A-Z]{2}$'")
    op.create_check_constraint("ck_tenants_currency", "tenants", "currency ~ '^[A-Z]{3}$'")
    op.create_check_constraint("ck_tenants_version", "tenants", "version > 0")
    op.create_check_constraint("ck_memberships_role", "memberships", f"role IN {ROLES!r}")

    op.create_table(
        "oidc_identities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="uq_oidc_identity_subject"),
    )
    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "token_digest", name="uq_invitations_tenant_token"),
        sa.CheckConstraint(f"role IN {ROLES!r}", name="ck_invitations_role"),
    )
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("prefix", sa.String(21), nullable=False),
        sa.Column("key_digest", sa.String(64), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "prefix", name="uq_api_keys_tenant_prefix"),
    )
    op.create_table(
        "external_grants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("permissions", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "membership_id",
            "resource_type",
            "resource_id",
            name="uq_external_grants_resource",
        ),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.Uuid()),
        sa.Column("correlation_id", sa.String(100), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
    )

    # Candidate keys make every tenant-owned parent referenceable with tenant context.
    for table in TENANT_TABLES:
        op.create_unique_constraint(f"uq_{table}_tenant_id_id", table, ["tenant_id", "id"])
        op.create_index(f"ix_{table}_tenant_created", table, ["tenant_id", "created_at"])

    relationships = (
        ("conversations", "contact_id", "contacts", "fk_conversations_tenant_contact"),
        ("knowledge_chunks", "document_id", "knowledge_documents", "fk_chunks_tenant_document"),
        ("orders", "contact_id", "contacts", "fk_orders_tenant_contact"),
        ("outcomes", "order_id", "orders", "fk_outcomes_tenant_order"),
        ("dispute_evidence", "order_id", "orders", "fk_evidence_tenant_order"),
        ("billable_results", "outcome_id", "outcomes", "fk_results_tenant_outcome"),
        ("ledger_entries", "billable_result_id", "billable_results", "fk_ledger_tenant_result"),
        ("external_grants", "membership_id", "memberships", "fk_grants_tenant_membership"),
    )
    for child, child_id, parent, name in relationships:
        op.create_foreign_key(name, child, parent, ["tenant_id", child_id], ["tenant_id", "id"])

    op.execute(
        """CREATE FUNCTION outcomeos_reject_tenant_change() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
            RAISE EXCEPTION 'tenant_id is immutable';
          END IF;
          RETURN NEW;
        END $$"""
    )
    for table in TENANT_TABLES:
        op.execute(
            f'''CREATE TRIGGER trg_{table}_tenant_immutable BEFORE UPDATE OF tenant_id
                ON "{table}" FOR EACH ROW EXECUTE FUNCTION outcomeos_reject_tenant_change()'''
        )
        _rls(table)
    op.execute(
        """CREATE FUNCTION outcomeos_reject_audit_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          RAISE EXCEPTION 'audit_events are append-only';
        END $$"""
    )
    op.execute(
        """CREATE TRIGGER trg_audit_events_append_only BEFORE UPDATE OR DELETE
        ON audit_events FOR EACH ROW EXECUTE FUNCTION outcomeos_reject_audit_mutation()"""
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS outcomeos_reject_audit_mutation()")
    relationships = (
        ("external_grants", "fk_grants_tenant_membership"),
        ("ledger_entries", "fk_ledger_tenant_result"),
        ("billable_results", "fk_results_tenant_outcome"),
        ("dispute_evidence", "fk_evidence_tenant_order"),
        ("outcomes", "fk_outcomes_tenant_order"),
        ("orders", "fk_orders_tenant_contact"),
        ("knowledge_chunks", "fk_chunks_tenant_document"),
        ("conversations", "fk_conversations_tenant_contact"),
    )
    for table, name in relationships:
        op.drop_constraint(name, table, type_="foreignkey")
    for table in reversed(TENANT_TABLES):
        op.execute(f'DROP TRIGGER IF EXISTS trg_{table}_tenant_immutable ON "{table}"')
    op.execute("DROP FUNCTION IF EXISTS outcomeos_reject_tenant_change()")
    original_tables = TENANT_TABLES[:10]
    for table in original_tables:
        op.drop_index(f"ix_{table}_tenant_created", table_name=table)
        op.drop_constraint(f"uq_{table}_tenant_id_id", table, type_="unique")
    for table in ("memberships", "knowledge_documents"):
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
    for table in ("audit_events", "external_grants", "api_keys", "invitations"):
        op.drop_table(table)
    op.drop_table("oidc_identities")
    op.drop_constraint("ck_memberships_role", "memberships", type_="check")
    for name in ("ck_tenants_version", "ck_tenants_currency", "ck_tenants_country_code"):
        op.drop_constraint(name, "tenants", type_="check")
    for column in ("version", "business_type", "timezone", "locale", "currency", "country_code"):
        op.drop_column("tenants", column)
