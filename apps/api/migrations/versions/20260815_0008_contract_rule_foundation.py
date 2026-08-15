# ruff: noqa: E501
"""Add immutable contract and outcome-rule foundation.

Revision ID: 20260815_0008
Revises: 20260815_0007
"""

from alembic import op

revision = "20260815_0008"
down_revision = "20260815_0007"
branch_labels = None
depends_on = None

TABLES = (
    "performance_contracts",
    "outcome_rules",
    "outcome_rule_versions",
    "performance_contract_versions",
    "contract_party_acceptances",
    "contract_source_bindings",
)


def upgrade() -> None:
    op.execute("""
    CREATE TABLE performance_contracts (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id),
      state text NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','active','suspended','terminated')),
      lock_version int NOT NULL DEFAULT 0 CHECK(lock_version>=0), created_by uuid NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(), UNIQUE(tenant_id,id)
    );
    CREATE TABLE outcome_rules (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id),
      name varchar(160) NOT NULL, created_by uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      UNIQUE(tenant_id,id), UNIQUE(tenant_id,name)
    );
    CREATE TABLE outcome_rule_versions (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, rule_id uuid NOT NULL,
      version int NOT NULL CHECK(version>0), schema_version int NOT NULL DEFAULT 1 CHECK(schema_version>0),
      template_id text NOT NULL CHECK(template_id IN ('delivered_paid_order','attended_booking','qualified_lead_accepted','paid_activated_subscription')),
      definition jsonb NOT NULL, canonical_document text, digest char(64),
      state text NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','published','retired')),
      created_by uuid NOT NULL, published_by uuid, created_at timestamptz NOT NULL DEFAULT clock_timestamp(), published_at timestamptz,
      UNIQUE(tenant_id,id), UNIQUE(tenant_id,rule_id,version),
      FOREIGN KEY(tenant_id,rule_id) REFERENCES outcome_rules(tenant_id,id)
    );
    CREATE TABLE performance_contract_versions (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, contract_id uuid NOT NULL,
      version int NOT NULL CHECK(version>0), schema_version int NOT NULL DEFAULT 1 CHECK(schema_version>0),
      display_name varchar(160) NOT NULL, description varchar(2000), required_party_roles jsonb NOT NULL,
      rule_version_id uuid NOT NULL, contract_timezone varchar(64) NOT NULL, currency char(3) NOT NULL,
      pricing_model text NOT NULL CHECK(pricing_model IN ('fixed_fee','basis_points')),
      fixed_fee_minor bigint, rate_basis_points int, floor_minor bigint, cap_minor bigint,
      anchor_event_type varchar(160) NOT NULL, attribution_window_seconds int NOT NULL CHECK(attribution_window_seconds>=0),
      evaluation_window_seconds int NOT NULL CHECK(evaluation_window_seconds>=0), finalization_window_seconds int NOT NULL CHECK(finalization_window_seconds>=0),
      effective_start timestamptz NOT NULL, effective_end timestamptz, terms jsonb NOT NULL,
      canonical_document text, digest char(64), state text NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','proposed','active','superseded','withdrawn')),
      created_by uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      CHECK(effective_end IS NULL OR effective_end>effective_start),
      CHECK((pricing_model='fixed_fee' AND fixed_fee_minor>0 AND rate_basis_points IS NULL AND floor_minor IS NULL AND cap_minor IS NULL) OR
            (pricing_model='basis_points' AND fixed_fee_minor IS NULL AND rate_basis_points BETWEEN 1 AND 10000 AND coalesce(floor_minor,0)>=0 AND coalesce(cap_minor,0)>=0 AND (floor_minor IS NULL OR cap_minor IS NULL OR floor_minor<=cap_minor))),
      UNIQUE(tenant_id,id), UNIQUE(tenant_id,contract_id,version),
      FOREIGN KEY(tenant_id,contract_id) REFERENCES performance_contracts(tenant_id,id),
      FOREIGN KEY(tenant_id,rule_version_id) REFERENCES outcome_rule_versions(tenant_id,id)
    );
    CREATE UNIQUE INDEX one_active_contract_version ON performance_contract_versions(tenant_id,contract_id) WHERE state='active';
    CREATE TABLE contract_party_acceptances (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, contract_version_id uuid NOT NULL,
      digest char(64) NOT NULL, party_role varchar(64) NOT NULL, principal_id uuid NOT NULL,
      accepted_at timestamptz NOT NULL, UNIQUE(tenant_id,contract_version_id,digest,party_role),
      FOREIGN KEY(tenant_id,contract_version_id) REFERENCES performance_contract_versions(tenant_id,id)
    );
    CREATE TABLE contract_source_bindings (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, contract_id uuid NOT NULL,
      source_type varchar(64) NOT NULL, source_id varchar(255) NOT NULL, effective_start timestamptz NOT NULL,
      effective_end timestamptz, created_by uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      CHECK(effective_end IS NULL OR effective_end>effective_start), UNIQUE(tenant_id,id),
      FOREIGN KEY(tenant_id,contract_id) REFERENCES performance_contracts(tenant_id,id)
    );
    CREATE INDEX contract_selection_idx ON contract_source_bindings(tenant_id,source_type,source_id,effective_start,effective_end);
    CREATE INDEX contract_list_idx ON performance_contracts(tenant_id,created_at,id);
    CREATE INDEX rule_list_idx ON outcome_rules(tenant_id,created_at,id);
    CREATE FUNCTION protect_contract_history() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
      IF TG_OP='DELETE' OR TG_TABLE_NAME='contract_party_acceptances' THEN RAISE EXCEPTION 'immutable commercial history'; END IF;
      IF TG_TABLE_NAME='outcome_rule_versions' AND OLD.state IN ('published','retired') AND
        (NEW.definition,NEW.canonical_document,NEW.digest,NEW.template_id,NEW.version) IS DISTINCT FROM
        (OLD.definition,OLD.canonical_document,OLD.digest,OLD.template_id,OLD.version) THEN RAISE EXCEPTION 'immutable published rule'; END IF;
      IF TG_TABLE_NAME='performance_contract_versions' AND OLD.state IN ('proposed','active','superseded','withdrawn') AND
        (NEW.terms,NEW.canonical_document,NEW.digest,NEW.currency,NEW.pricing_model,NEW.fixed_fee_minor,NEW.rate_basis_points,NEW.floor_minor,NEW.cap_minor,NEW.effective_start,NEW.effective_end) IS DISTINCT FROM
        (OLD.terms,OLD.canonical_document,OLD.digest,OLD.currency,OLD.pricing_model,OLD.fixed_fee_minor,OLD.rate_basis_points,OLD.floor_minor,OLD.cap_minor,OLD.effective_start,OLD.effective_end) THEN RAISE EXCEPTION 'immutable proposed contract'; END IF;
      RETURN NEW; END $$;
    CREATE TRIGGER immutable_rule_versions BEFORE UPDATE OR DELETE ON outcome_rule_versions FOR EACH ROW EXECUTE FUNCTION protect_contract_history();
    CREATE TRIGGER immutable_contract_versions BEFORE UPDATE OR DELETE ON performance_contract_versions FOR EACH ROW EXECUTE FUNCTION protect_contract_history();
    CREATE TRIGGER immutable_acceptances BEFORE UPDATE OR DELETE ON contract_party_acceptances FOR EACH ROW EXECUTE FUNCTION protect_contract_history();
    """)
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f'''CREATE POLICY tenant_isolation ON "{table}" USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid)'''
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f'DROP TABLE "{table}"')
    op.execute("DROP FUNCTION protect_contract_history()")
