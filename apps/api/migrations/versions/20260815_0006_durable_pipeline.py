# ruff: noqa: E501
"""Add the durable pipeline worker controls and idempotency metadata.

Revision ID: 20260815_0006
Revises: 20260814_0005
"""

from alembic import op

revision = "20260815_0006"
down_revision = "20260814_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_event_replay_source", "event_replays", type_="unique")
    op.execute("DROP TRIGGER trg_job_attempts_append_only ON job_attempts")
    op.execute("""
    CREATE FUNCTION public.outcomeos_finalize_attempt_only() RETURNS trigger
    LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$ BEGIN
      IF OLD.id<>NEW.id OR OLD.tenant_id<>NEW.tenant_id OR OLD.job_id<>NEW.job_id
         OR OLD.attempt_number<>NEW.attempt_number OR OLD.lease_token<>NEW.lease_token
         OR OLD.started_at<>NEW.started_at OR OLD.created_at<>NEW.created_at
         OR OLD.finished_at IS NOT NULL OR OLD.outcome IS NOT NULL OR OLD.error_code IS NOT NULL
         OR NEW.finished_at IS NULL OR NEW.outcome IS NULL THEN
        RAISE EXCEPTION 'job attempts are immutable except for one-way finalization';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER trg_job_attempts_finalize BEFORE UPDATE ON job_attempts
      FOR EACH ROW EXECUTE FUNCTION public.outcomeos_finalize_attempt_only();
    CREATE TRIGGER trg_job_attempts_delete BEFORE DELETE ON job_attempts
      FOR EACH ROW EXECUTE FUNCTION public.outcomeos_reject_audit_mutation();
    """)
    op.execute("ALTER TABLE event_replays ADD COLUMN idempotency_key varchar(255)")
    op.execute("ALTER TABLE event_replays ADD COLUMN request_digest bytea")
    op.execute("ALTER TABLE reconciliation_runs ADD COLUMN idempotency_key varchar(255)")
    op.execute("ALTER TABLE reconciliation_runs ADD COLUMN request_digest bytea")
    op.execute(
        "CREATE UNIQUE INDEX uq_replay_idempotency ON event_replays(tenant_id,idempotency_key)"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_reconciliation_idempotency ON reconciliation_runs(tenant_id,idempotency_key)"
    )
    op.execute("""
    CREATE ROLE outcomeos_worker NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    CREATE FUNCTION public.outcomeos_claim_jobs(p_batch int,p_lease_seconds int)
    RETURNS SETOF outbox_jobs LANGUAGE sql VOLATILE SECURITY DEFINER
    SET search_path=pg_catalog,public AS $$
      WITH candidates AS (
        SELECT id FROM public.outbox_jobs
        WHERE (state IN ('pending','retry') AND available_at<=clock_timestamp())
           OR (state='leased' AND lease_expires_at<=clock_timestamp())
        ORDER BY available_at,id FOR UPDATE SKIP LOCKED LIMIT greatest(0,least(p_batch,100))
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
    $$;
    CREATE FUNCTION public.outcomeos_finish_job(p_job uuid,p_lease uuid,p_outcome text,
      p_error text,p_delay int) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
    SET search_path=pg_catalog,public AS $$ DECLARE changed int; BEGIN
      IF p_outcome NOT IN ('succeeded','retry','dead') OR
         (p_error IS NOT NULL AND p_error !~ '^[a-z0-9_.-]{1,80}$') THEN
        RAISE EXCEPTION 'invalid safe outcome'; END IF;
      UPDATE public.outbox_jobs SET
        state=CASE p_outcome WHEN 'succeeded' THEN 'completed' WHEN 'retry' THEN 'retry' ELSE 'dead' END,
        completed_at=CASE WHEN p_outcome IN ('succeeded','dead') THEN clock_timestamp() END,
        available_at=CASE WHEN p_outcome='retry' THEN clock_timestamp()+make_interval(secs=>greatest(0,p_delay)) ELSE available_at END,
        lease_token=NULL,lease_expires_at=NULL,last_error_code=p_error
      WHERE id=p_job AND state='leased' AND lease_token=p_lease;
      GET DIAGNOSTICS changed=ROW_COUNT;
      IF changed=1 THEN UPDATE public.job_attempts SET finished_at=clock_timestamp(),
        outcome=p_outcome,error_code=p_error WHERE job_id=p_job AND lease_token=p_lease
        AND finished_at IS NULL; END IF; RETURN changed=1;
    END $$;
    CREATE FUNCTION public.outcomeos_lease_lost(p_job uuid,p_lease uuid) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$ DECLARE changed int;
    BEGIN UPDATE public.job_attempts SET finished_at=clock_timestamp(),outcome='lease_lost'
      WHERE job_id=p_job AND lease_token=p_lease AND finished_at IS NULL;
      GET DIAGNOSTICS changed=ROW_COUNT; RETURN changed=1; END $$;
    CREATE FUNCTION public.outcomeos_worker_heartbeat(p_worker uuid,p_status text)
    RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$ BEGIN
      IF p_status NOT IN ('starting','healthy','draining') THEN RAISE EXCEPTION 'invalid status'; END IF;
      INSERT INTO public.worker_heartbeats(id,created_at,tenant_id,worker_id,observed_at,status)
      SELECT gen_random_uuid(),clock_timestamp(),id,p_worker,clock_timestamp(),p_status FROM public.tenants
      ON CONFLICT (tenant_id,worker_id) DO UPDATE SET observed_at=EXCLUDED.observed_at,status=EXCLUDED.status;
    END $$;
    REVOKE ALL ON FUNCTION public.outcomeos_claim_jobs(int,int) FROM PUBLIC;
    REVOKE ALL ON FUNCTION public.outcomeos_finish_job(uuid,uuid,text,text,int) FROM PUBLIC;
    REVOKE ALL ON FUNCTION public.outcomeos_lease_lost(uuid,uuid) FROM PUBLIC;
    REVOKE ALL ON FUNCTION public.outcomeos_worker_heartbeat(uuid,text) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.outcomeos_claim_jobs(int,int),
      public.outcomeos_finish_job(uuid,uuid,text,text,int),
      public.outcomeos_lease_lost(uuid,uuid),public.outcomeos_worker_heartbeat(uuid,text)
      TO outcomeos_worker;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION public.outcomeos_worker_heartbeat(uuid,text)")
    op.execute("DROP FUNCTION public.outcomeos_lease_lost(uuid,uuid)")
    op.execute("DROP FUNCTION public.outcomeos_finish_job(uuid,uuid,text,text,int)")
    op.execute("DROP FUNCTION public.outcomeos_claim_jobs(int,int)")
    op.execute("DROP ROLE outcomeos_worker")
    op.execute("DROP INDEX uq_reconciliation_idempotency")
    op.execute("DROP INDEX uq_replay_idempotency")
    op.execute(
        "ALTER TABLE reconciliation_runs DROP COLUMN request_digest, DROP COLUMN idempotency_key"
    )
    op.execute("ALTER TABLE event_replays DROP COLUMN request_digest, DROP COLUMN idempotency_key")
    op.execute("DROP TRIGGER trg_job_attempts_delete ON job_attempts")
    op.execute("DROP TRIGGER trg_job_attempts_finalize ON job_attempts")
    op.execute("DROP FUNCTION public.outcomeos_finalize_attempt_only()")
    op.execute(
        "CREATE TRIGGER trg_job_attempts_append_only BEFORE UPDATE OR DELETE ON job_attempts FOR EACH ROW EXECUTE FUNCTION outcomeos_reject_audit_mutation()"
    )
    op.create_unique_constraint(
        "uq_event_replay_source", "event_replays", ["tenant_id", "source_event_id"]
    )
