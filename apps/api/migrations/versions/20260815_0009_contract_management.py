# ruff: noqa: E501
"""Complete transactional contract management persistence.

Revision ID: 20260815_0009
Revises: 20260815_0008
"""

from alembic import op

revision = "20260815_0009"
down_revision = "20260815_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE EXTENSION IF NOT EXISTS btree_gist;
    CREATE TABLE contract_command_results (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id),
      idempotency_key varchar(200) NOT NULL, request_digest char(64) NOT NULL,
      response jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      UNIQUE(tenant_id,id), UNIQUE(tenant_id,idempotency_key)
    );
    CREATE TABLE contract_domain_outbox (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id),
      event_type varchar(100) NOT NULL, aggregate_type varchar(64) NOT NULL,
      aggregate_id uuid, actor_id uuid NOT NULL, actor_type varchar(16) NOT NULL,
      metadata jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      UNIQUE(tenant_id,id)
    );
    CREATE TABLE contract_party_authorities (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id),
      contract_id uuid NOT NULL, party_role varchar(64) NOT NULL, principal_id uuid NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(), UNIQUE(tenant_id,id),
      UNIQUE(tenant_id,contract_id,party_role,principal_id),
      FOREIGN KEY(tenant_id,contract_id) REFERENCES performance_contracts(tenant_id,id)
    );
    ALTER TABLE contract_source_bindings ADD CONSTRAINT no_overlapping_source_bindings
      EXCLUDE USING gist (tenant_id WITH =, source_type WITH =, source_id WITH =,
        tstzrange(effective_start,effective_end,'[)') WITH &&);
    """)
    for table in (
        "contract_command_results",
        "contract_domain_outbox",
        "contract_party_authorities",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}_tenant_immutable BEFORE UPDATE OF tenant_id ON {table} FOR EACH ROW EXECUTE FUNCTION outcomeos_reject_tenant_change()"
        )
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid)"
        )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE contract_source_bindings DROP CONSTRAINT no_overlapping_source_bindings"
    )
    op.execute(
        "DROP TABLE contract_party_authorities, contract_domain_outbox, contract_command_results"
    )
