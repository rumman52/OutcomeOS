"""Add the tenant-isolated event pipeline persistence foundation.

Revision ID: 20260814_0003
Revises: 20260808_0002
"""

from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260814_0003"
down_revision = "20260808_0002"
branch_labels = None
depends_on = None

TABLES = (
    "integration_endpoints",
    "integration_secret_versions",
    "webhook_receipts",
    "canonical_events",
    "outbox_jobs",
    "job_attempts",
    "csv_imports",
    "csv_import_errors",
    "event_replays",
    "reconciliation_runs",
    "reconciliation_anomalies",
    "worker_heartbeats",
)


def _base_columns() -> list[Any]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        # Created before child tables so composite tenant foreign keys can resolve their parent.
        sa.UniqueConstraint("tenant_id", "id"),
    ]


def _protect(table: str, *, append_only: bool = False) -> None:
    op.create_unique_constraint(f"uq_{table}_tenant_id_id", table, ["tenant_id", "id"])
    op.create_index(f"ix_{table}_tenant_created", table, ["tenant_id", "created_at"])
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'''CREATE POLICY tenant_isolation ON "{table}"
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)'''
    )
    op.execute(
        f'''CREATE TRIGGER trg_{table}_tenant_immutable BEFORE UPDATE OF tenant_id ON "{table}"
        FOR EACH ROW EXECUTE FUNCTION outcomeos_reject_tenant_change()'''
    )
    if append_only:
        op.execute(
            f'''CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON "{table}"
            FOR EACH ROW EXECUTE FUNCTION outcomeos_reject_audit_mutation()'''
        )


def upgrade() -> None:
    jsonb = postgresql.JSONB()
    op.create_table(
        "integration_endpoints",
        *_base_columns(),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("public_token_digest", sa.LargeBinary(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("public_token_digest", name="uq_integration_endpoints_token_digest"),
        sa.UniqueConstraint("tenant_id", "provider", "name", name="uq_endpoints_tenant_name"),
        sa.CheckConstraint(
            "status IN ('active', 'disabled', 'revoked')", name="ck_endpoints_status"
        ),
    )
    op.create_table(
        "integration_secret_versions",
        *_base_columns(),
        sa.Column("endpoint_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("key_id", sa.String(128), nullable=False),
        sa.Column("nonce", sa.LargeBinary(12), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "endpoint_id", "version", name="uq_secret_versions"),
        sa.CheckConstraint("version > 0", name="ck_secret_version_positive"),
        sa.CheckConstraint("expires_at > not_before", name="ck_secret_version_window"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "endpoint_id"],
            ["integration_endpoints.tenant_id", "integration_endpoints.id"],
            name="fk_secrets_tenant_endpoint",
        ),
    )
    op.create_table(
        "webhook_receipts",
        *_base_columns(),
        sa.Column("endpoint_id", sa.Uuid(), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("payload_digest", sa.LargeBinary(32), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "endpoint_id", "provider_event_id", name="uq_receipts_provider_event"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "endpoint_id"],
            ["integration_endpoints.tenant_id", "integration_endpoints.id"],
            name="fk_receipts_tenant_endpoint",
        ),
    )
    op.create_table(
        "canonical_events",
        *_base_columns(),
        sa.Column("receipt_id", sa.Uuid()),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", jsonb, nullable=False),
        sa.Column("payload_digest", sa.LargeBinary(32), nullable=False),
        sa.UniqueConstraint("tenant_id", "receipt_id", name="uq_events_receipt"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "receipt_id"],
            ["webhook_receipts.tenant_id", "webhook_receipts.id"],
            name="fk_events_tenant_receipt",
        ),
        sa.CheckConstraint("event_version > 0", name="ck_event_version_positive"),
    )
    op.create_table(
        "outbox_jobs",
        *_base_columns(),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_token", sa.Uuid()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(80)),
        sa.UniqueConstraint("tenant_id", "event_id", "kind", name="uq_jobs_event_kind"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["canonical_events.tenant_id", "canonical_events.id"],
            name="fk_jobs_tenant_event",
        ),
        sa.CheckConstraint(
            "state IN ('pending','leased','retry','completed','dead')", name="ck_jobs_state"
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_jobs_attempt_count"),
    )
    op.create_index("ix_outbox_jobs_claim", "outbox_jobs", ["state", "available_at"])
    op.create_table(
        "job_attempts",
        *_base_columns(),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("outcome", sa.String(16)),
        sa.Column("error_code", sa.String(80)),
        sa.UniqueConstraint("tenant_id", "job_id", "attempt_number", name="uq_job_attempt_number"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "job_id"],
            ["outbox_jobs.tenant_id", "outbox_jobs.id"],
            name="fk_attempts_tenant_job",
        ),
        sa.CheckConstraint("attempt_number > 0", name="ck_attempt_number_positive"),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('succeeded','retry','dead','lease_lost')",
            name="ck_attempt_outcome",
        ),
    )
    op.create_table(
        "csv_imports",
        *_base_columns(),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.Column("object_digest", sa.LargeBinary(32), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_csv_import_idempotency"),
        sa.CheckConstraint(
            "state IN ('uploaded','processing','completed','failed')", name="ck_csv_import_state"
        ),
        sa.CheckConstraint(
            "total_rows >= 0 AND accepted_rows >= 0 AND rejected_rows >= 0",
            name="ck_csv_import_counts",
        ),
    )
    op.create_table(
        "csv_import_errors",
        *_base_columns(),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("safe_message", sa.String(500), nullable=False),
        sa.UniqueConstraint("tenant_id", "import_id", "row_number", "code", name="uq_csv_error"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "import_id"],
            ["csv_imports.tenant_id", "csv_imports.id"],
            name="fk_csv_errors_tenant_import",
        ),
        sa.CheckConstraint("row_number > 0", name="ck_csv_error_row"),
    )
    op.create_table(
        "event_replays",
        *_base_columns(),
        sa.Column("source_event_id", sa.Uuid(), nullable=False),
        sa.Column("replay_event_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.UniqueConstraint("tenant_id", "source_event_id", name="uq_event_replay_source"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_event_id"],
            ["canonical_events.tenant_id", "canonical_events.id"],
            name="fk_replays_tenant_source",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "replay_event_id"],
            ["canonical_events.tenant_id", "canonical_events.id"],
            name="fk_replays_tenant_replay",
        ),
    )
    op.create_table(
        "reconciliation_runs",
        *_base_columns(),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("summary", jsonb, nullable=False),
        sa.CheckConstraint(
            "state IN ('running','completed','failed')", name="ck_reconciliation_state"
        ),
    )
    op.create_table(
        "reconciliation_anomalies",
        *_base_columns(),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.Uuid()),
        sa.Column("safe_details", jsonb, nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["reconciliation_runs.tenant_id", "reconciliation_runs.id"],
            name="fk_anomalies_tenant_run",
        ),
    )
    op.create_table(
        "worker_heartbeats",
        *_base_columns(),
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.UniqueConstraint("tenant_id", "worker_id", name="uq_worker_heartbeat"),
        sa.CheckConstraint("status IN ('starting','healthy','draining')", name="ck_worker_status"),
    )
    for table in TABLES:
        _protect(
            table,
            append_only=table
            in {
                "webhook_receipts",
                "canonical_events",
                "job_attempts",
                "csv_import_errors",
                "event_replays",
                "reconciliation_anomalies",
            },
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
