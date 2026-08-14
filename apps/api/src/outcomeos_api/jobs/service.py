# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import text

from outcomeos_api.events.schemas import CanonicalEvent
from outcomeos_api.imports.csv import CsvLimits, parse_csv_v1
from outcomeos_api.storage import ObjectStorage, PaginatedObjectStorage


class RetryableJobError(RuntimeError):
    def __init__(self, code: str = "transient_failure") -> None:
        self.code = code
        super().__init__(code)


class PermanentJobError(RuntimeError):
    def __init__(self, code: str = "invalid_job") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Job:
    id: UUID
    tenant_id: UUID
    event_id: UUID
    kind: str
    lease_token: UUID
    attempt_count: int


Handler = Callable[[Job], None]


class JobRunner:
    def __init__(
        self,
        sessions: object,
        *,
        lease_seconds: int,
        batch_size: int,
        max_attempts: int,
        backoff_base: int,
        backoff_max: int,
    ) -> None:
        self.sessions = sessions
        self.lease_seconds, self.batch_size = lease_seconds, batch_size
        self.max_attempts, self.backoff_base, self.backoff_max = (
            max_attempts,
            backoff_base,
            backoff_max,
        )
        self.handlers: dict[str, Handler] = {}

    def register(self, kind: str, handler: Handler) -> None:
        if not kind or kind in self.handlers:
            raise ValueError("job kind must be unique")
        self.handlers[kind] = handler

    def backoff(self, attempt: int) -> int:
        return int(min(self.backoff_max, self.backoff_base * (2 ** max(0, attempt - 1))))

    def run_once(self) -> int:
        with self.sessions() as session, session.begin():  # type: ignore[operator]
            if session.bind.dialect.name == "postgresql":
                session.execute(text("SET LOCAL ROLE outcomeos_worker"))
            rows = session.execute(
                text("SELECT * FROM public.outcomeos_claim_jobs(:batch,:lease)"),
                {"batch": self.batch_size, "lease": self.lease_seconds},
            ).mappings()
            jobs = [
                Job(
                    UUID(str(r["id"])),
                    UUID(str(r["tenant_id"])),
                    UUID(str(r["event_id"])),
                    str(r["kind"]),
                    UUID(str(r["lease_token"])),
                    int(r["attempt_count"]),
                )
                for r in rows
            ]
        for job in jobs:
            outcome, code, delay = "succeeded", None, 0
            try:
                handler = self.handlers.get(job.kind)
                if handler is None:
                    raise PermanentJobError("unsupported_job_kind")
                handler(job)
            except PermanentJobError as error:
                outcome, code = "dead", error.code
            except RetryableJobError as error:
                code = error.code
                outcome = "dead" if job.attempt_count >= self.max_attempts else "retry"
                delay = self.backoff(job.attempt_count)
            except Exception:
                code = "handler_failure"
                outcome = "dead" if job.attempt_count >= self.max_attempts else "retry"
                delay = self.backoff(job.attempt_count)
            with self.sessions() as session, session.begin():  # type: ignore[operator]
                if session.bind.dialect.name == "postgresql":
                    session.execute(text("SET LOCAL ROLE outcomeos_worker"))
                session.execute(
                    text("SELECT public.outcomeos_finish_job(:job,:lease,:outcome,:error,:delay)"),
                    {
                        "job": job.id,
                        "lease": job.lease_token,
                        "outcome": outcome,
                        "error": code,
                        "delay": delay,
                    },
                )
        return len(jobs)


def canonical_event_handler(sessions: object) -> Handler:
    def handle(job: Job) -> None:
        with sessions() as session, session.begin():  # type: ignore[operator]
            session.execute(
                text("SELECT set_config('app.tenant_id',:tenant,true)"),
                {"tenant": str(job.tenant_id)},
            )
            row = (
                session.execute(
                    text(
                        "SELECT payload,payload_digest FROM canonical_events "
                        "WHERE tenant_id=:tenant AND id=:event"
                    ),
                    {"tenant": job.tenant_id, "event": job.event_id},
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise PermanentJobError("canonical_event_missing")
        payload = row["payload"]
        if not isinstance(payload, dict):
            raise PermanentJobError("canonical_envelope_invalid")
        expected = payload.get("payload_digest")
        envelope = {
            k: v
            for k, v in payload.items()
            if k not in {"event_id", "received_at", "payload_digest", "raw_object_key"}
        }
        actual = hashlib.sha256(
            json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        if expected != actual or bytes(row["payload_digest"]).hex() != actual:
            raise PermanentJobError("canonical_digest_invalid")

    return handle


def csv_import_handler(sessions: object, storage: ObjectStorage, limits: CsvLimits) -> Handler:
    """Process an uploaded CSV idempotently using deterministic row identities."""

    def handle(job: Job) -> None:
        with sessions() as session, session.begin():  # type: ignore[operator]
            session.execute(
                text("SELECT set_config('app.tenant_id',:tenant,true)"),
                {"tenant": str(job.tenant_id)},
            )
            control = (
                session.execute(
                    text("SELECT payload FROM canonical_events WHERE tenant_id=:t AND id=:e"),
                    {"t": job.tenant_id, "e": job.event_id},
                )
                .mappings()
                .one_or_none()
            )
            if control is None or not isinstance(control["payload"], dict):
                raise PermanentJobError("csv_control_event_missing")
            try:
                import_id = UUID(str(control["payload"]["import_id"]))
            except (KeyError, ValueError, TypeError) as error:
                raise PermanentJobError("csv_control_event_invalid") from error
            record = (
                session.execute(
                    text(
                        "SELECT object_key,object_digest,state FROM csv_imports WHERE tenant_id=:t AND id=:id FOR UPDATE"
                    ),
                    {"t": job.tenant_id, "id": import_id},
                )
                .mappings()
                .one_or_none()
            )
            if record is None:
                raise PermanentJobError("csv_import_missing")
            if record["state"] == "completed":
                return
            session.execute(
                text("UPDATE csv_imports SET state='processing' WHERE tenant_id=:t AND id=:id"),
                {"t": job.tenant_id, "id": import_id},
            )
            body = storage.read(job.tenant_id, str(record["object_key"]))
            if hashlib.sha256(body).digest() != bytes(record["object_digest"]):
                raise PermanentJobError("csv_digest_mismatch")
            lines = body.splitlines(keepends=True)
            if not lines:
                raise PermanentJobError("csv_header_invalid")
            accepted = rejected = 0
            now = datetime.now(UTC)
            for row_number, line in enumerate(lines[1:], start=2):
                try:
                    incoming = parse_csv_v1(lines[0] + line, limits)[0]
                    event_id = uuid5(NAMESPACE_URL, f"outcomeos:{import_id}:{row_number}")
                    canonical = CanonicalEvent(
                        event_id=event_id,
                        tenant_id=job.tenant_id,
                        provider="csv",
                        source_type="csv_import",
                        provider_event_id=incoming.provider_event_id,
                        payload_digest="0" * 64,
                        event_type=incoming.event_type,
                        occurred_at=incoming.occurred_at,
                        received_at=now,
                        subject_type=incoming.subject_type,
                        subject_id=incoming.subject_id,
                        references=incoming.references,
                        attribution=incoming.attribution,
                        money=incoming.money,
                        consent=incoming.consent,
                        payload=incoming.payload,
                    ).model_dump(mode="json")
                    envelope = {
                        k: v
                        for k, v in canonical.items()
                        if k not in {"event_id", "received_at", "payload_digest", "raw_object_key"}
                    }
                    digest = hashlib.sha256(
                        json.dumps(
                            envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                        ).encode()
                    ).digest()
                    canonical["payload_digest"] = digest.hex()
                    session.execute(
                        text("""INSERT INTO canonical_events
                        (id,created_at,tenant_id,event_type,event_version,occurred_at,payload,payload_digest)
                        VALUES(:id,:n,:t,:type,1,:occurred,CAST(:payload AS jsonb),:digest)
                        ON CONFLICT (tenant_id,id) DO NOTHING"""),
                        {
                            "id": event_id,
                            "n": now,
                            "t": job.tenant_id,
                            "type": incoming.event_type,
                            "occurred": incoming.occurred_at,
                            "payload": json.dumps(canonical),
                            "digest": digest,
                        },
                    )
                    session.execute(
                        text("""INSERT INTO outbox_jobs
                        (id,created_at,tenant_id,event_id,kind,state,available_at,attempt_count)
                        VALUES(:id,:n,:t,:event,'ingest.canonical_event.v1','pending',:n,0)
                        ON CONFLICT (tenant_id,event_id,kind) DO NOTHING"""),
                        {
                            "id": uuid5(
                                NAMESPACE_URL, f"outcomeos:csv-job:{import_id}:{row_number}"
                            ),
                            "n": now,
                            "t": job.tenant_id,
                            "event": event_id,
                        },
                    )
                    accepted += 1
                except (ValueError, IndexError, TypeError, json.JSONDecodeError):
                    rejected += 1
                    session.execute(
                        text("""INSERT INTO csv_import_errors
                        (id,created_at,tenant_id,import_id,row_number,code,safe_message)
                        VALUES(:id,:n,:t,:import,:row,'csv_row_invalid','row failed canonical validation')
                        ON CONFLICT (tenant_id,import_id,row_number,code) DO NOTHING"""),
                        {
                            "id": uuid5(
                                NAMESPACE_URL, f"outcomeos:csv-error:{import_id}:{row_number}"
                            ),
                            "n": now,
                            "t": job.tenant_id,
                            "import": import_id,
                            "row": row_number,
                        },
                    )
            session.execute(
                text("""UPDATE csv_imports SET state='completed',total_rows=:total,
                accepted_rows=:accepted,rejected_rows=:rejected WHERE tenant_id=:t AND id=:id"""),
                {
                    "total": accepted + rejected,
                    "accepted": accepted,
                    "rejected": rejected,
                    "t": job.tenant_id,
                    "id": import_id,
                },
            )

    return handle


def reconciliation_handler(sessions: object, storage: PaginatedObjectStorage) -> Handler:
    """Record allow-listed consistency anomalies without copying payload data."""

    checks = {
        "receipt_missing_event": "SELECT r.id FROM webhook_receipts r LEFT JOIN canonical_events e ON e.tenant_id=r.tenant_id AND e.receipt_id=r.id WHERE r.tenant_id=:t AND e.id IS NULL",
        "event_missing_job": "SELECT e.id FROM canonical_events e LEFT JOIN outbox_jobs j ON j.tenant_id=e.tenant_id AND j.event_id=e.id WHERE e.tenant_id=:t AND j.id IS NULL",
        "stale_lease": "SELECT id FROM outbox_jobs WHERE tenant_id=:t AND state='leased' AND lease_expires_at<clock_timestamp()",
        "inconsistent_attempt": "SELECT a.id FROM job_attempts a JOIN outbox_jobs j ON j.tenant_id=a.tenant_id AND j.id=a.job_id WHERE a.tenant_id=:t AND a.finished_at IS NULL AND j.state<>'leased'",
    }

    def handle(job: Job) -> None:
        with sessions() as session, session.begin():  # type: ignore[operator]
            session.execute(
                text("SELECT set_config('app.tenant_id',:tenant,true)"),
                {"tenant": str(job.tenant_id)},
            )
            event = (
                session.execute(
                    text("SELECT payload FROM canonical_events WHERE tenant_id=:t AND id=:e"),
                    {"t": job.tenant_id, "e": job.event_id},
                )
                .mappings()
                .one_or_none()
            )
            try:
                run_id = UUID(str(event["payload"]["run_id"]))
            except (TypeError, KeyError, ValueError) as error:
                raise PermanentJobError("reconciliation_control_invalid") from error
            counts: dict[str, int] = {}
            for code, query in checks.items():
                rows = session.execute(text(query), {"t": job.tenant_id}).scalars().all()
                counts[code] = len(rows)
                for resource_id in rows:
                    session.execute(
                        text("""INSERT INTO reconciliation_anomalies
                        (id,created_at,tenant_id,run_id,code,resource_type,resource_id,safe_details)
                        VALUES(:id,clock_timestamp(),:t,:run,:code,'pipeline_record',:resource,'{}'::jsonb)"""),
                        {
                            "id": uuid4(),
                            "t": job.tenant_id,
                            "run": run_id,
                            "code": code,
                            "resource": resource_id,
                        },
                    )
            evidence = (
                session.execute(
                    text(
                        "SELECT id,object_key,payload_digest FROM webhook_receipts WHERE tenant_id=:t"
                    ),
                    {"t": job.tenant_id},
                )
                .mappings()
                .all()
            )
            for receipt in evidence:
                evidence_code: str | None = None
                try:
                    head = storage.head(job.tenant_id, str(receipt["object_key"]))
                    if head.sha256 != bytes(receipt["payload_digest"]).hex():
                        evidence_code = "evidence_digest_mismatch"
                except Exception:  # provider errors are deliberately reduced to a safe code
                    evidence_code = "evidence_missing"
                if evidence_code:
                    counts[evidence_code] = counts.get(evidence_code, 0) + 1
                    session.execute(
                        text("""INSERT INTO reconciliation_anomalies
                        (id,created_at,tenant_id,run_id,code,resource_type,resource_id,safe_details)
                        VALUES(:id,clock_timestamp(),:t,:run,:code,'webhook_receipt',:resource,'{}'::jsonb)"""),
                        {
                            "id": uuid4(),
                            "t": job.tenant_id,
                            "run": run_id,
                            "code": evidence_code,
                            "resource": receipt["id"],
                        },
                    )
            # Object scans remain bounded and tenant-prefixed by the storage adapter.
            page = storage.list_page(job.tenant_id, limit=100)
            known = set(
                session.execute(
                    text(
                        "SELECT object_key FROM webhook_receipts WHERE tenant_id=:t UNION SELECT object_key FROM csv_imports WHERE tenant_id=:t"
                    ),
                    {"t": job.tenant_id},
                ).scalars()
            )
            orphans = [key for key in page.keys if key not in known]
            counts["orphan_evidence"] = len(orphans)
            for key in orphans:
                session.execute(
                    text("""INSERT INTO reconciliation_anomalies
                    (id,created_at,tenant_id,run_id,code,resource_type,safe_details)
                    VALUES(:id,clock_timestamp(),:t,:run,'orphan_evidence','object',CAST(:details AS jsonb))"""),
                    {
                        "id": uuid4(),
                        "t": job.tenant_id,
                        "run": run_id,
                        "details": json.dumps(
                            {"key_digest": hashlib.sha256(key.encode()).hexdigest()}
                        ),
                    },
                )
            session.execute(
                text("""UPDATE reconciliation_runs SET state='completed',finished_at=clock_timestamp(),
                summary=CAST(:summary AS jsonb) WHERE tenant_id=:t AND id=:run"""),
                {"summary": json.dumps(counts), "t": job.tenant_id, "run": run_id},
            )

    return handle
