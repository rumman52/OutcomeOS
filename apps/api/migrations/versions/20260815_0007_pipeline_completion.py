"""Complete durable CSV metadata and worker-role membership.

Revision ID: 20260815_0007
Revises: 20260815_0006
"""

from alembic import op

revision = "20260815_0007"
down_revision = "20260815_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE csv_imports ADD COLUMN request_digest bytea")
    # The application login may assume only this non-login, function-only role.
    op.execute("GRANT outcomeos_worker TO CURRENT_USER")
    op.execute("""
    CREATE OR REPLACE FUNCTION public.outcomeos_claim_jobs(p_batch int,p_lease_seconds int)
    RETURNS SETOF outbox_jobs LANGUAGE sql VOLATILE SECURITY DEFINER
    SET search_path=pg_catalog,public AS $$
      WITH candidates AS (
        SELECT id,lease_token,state FROM public.outbox_jobs
        WHERE (state IN ('pending','retry') AND available_at<=clock_timestamp())
           OR (state='leased' AND lease_expires_at<=clock_timestamp())
        ORDER BY available_at,id FOR UPDATE SKIP LOCKED LIMIT greatest(0,least(p_batch,100))
      ), lost AS (
        UPDATE public.job_attempts a SET finished_at=clock_timestamp(),outcome='lease_lost'
        FROM candidates c WHERE c.state='leased' AND a.job_id=c.id
          AND a.lease_token=c.lease_token AND a.finished_at IS NULL RETURNING a.job_id
      ), claimed AS (
        UPDATE public.outbox_jobs j SET state='leased', lease_token=gen_random_uuid(),
          lease_expires_at=clock_timestamp()+make_interval(secs=>greatest(1,least(p_lease_seconds,3600))),
          attempt_count=j.attempt_count+1
        FROM candidates c WHERE j.id=c.id RETURNING j.*
      ), attempts AS (
        INSERT INTO public.job_attempts(id,created_at,tenant_id,job_id,attempt_number,
          lease_token,started_at) SELECT gen_random_uuid(),clock_timestamp(),tenant_id,id,
          attempt_count,lease_token,clock_timestamp() FROM claimed RETURNING job_id
      ) SELECT c.* FROM claimed c JOIN attempts a ON a.job_id=c.id
    $$
    """)


def downgrade() -> None:
    # Migration 0006's implementation is restored by the following downgrade in a full rollback.
    op.execute("REVOKE outcomeos_worker FROM CURRENT_USER")
    op.execute("ALTER TABLE csv_imports DROP COLUMN request_digest")
