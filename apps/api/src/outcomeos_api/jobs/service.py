from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text


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
