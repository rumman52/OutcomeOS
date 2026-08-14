from __future__ import annotations

import argparse
import signal
import time
from uuid import uuid4

from sqlalchemy import text

from outcomeos_api.config import Settings, get_settings
from outcomeos_api.db import create_database_engine, create_session_factory
from outcomeos_api.jobs.service import JobRunner, canonical_event_handler


def build_runner(settings: Settings) -> JobRunner:
    engine = create_database_engine(settings.database_url)
    sessions = create_session_factory(engine)
    runner = JobRunner(
        sessions,
        lease_seconds=settings.worker_lease_seconds,
        batch_size=settings.worker_batch_size,
        max_attempts=settings.worker_max_attempts,
        backoff_base=settings.worker_backoff_base_seconds,
        backoff_max=settings.worker_backoff_max_seconds,
    )
    runner.register(settings.ingestion_job_kind, canonical_event_handler(sessions))
    return runner


def run_once(settings: Settings | None = None) -> int:
    runtime = settings or get_settings()
    if runtime.persistence_backend != "postgresql":
        raise RuntimeError("durable worker requires PostgreSQL")
    return build_runner(runtime).run_once()


def main() -> None:
    parser = argparse.ArgumentParser(description="OutcomeOS durable outbox worker")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    runner = build_runner(settings)
    if args.once:
        runner.run_once()
        return
    stopping = False
    worker_id = uuid4()

    def drain(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, drain)
    signal.signal(signal.SIGINT, drain)
    while not stopping:
        with runner.sessions() as session, session.begin():  # type: ignore[operator]
            session.execute(text("SET LOCAL ROLE outcomeos_worker"))
            session.execute(
                text("SELECT public.outcomeos_worker_heartbeat(:id,'healthy')"), {"id": worker_id}
            )
        runner.run_once()
        time.sleep(settings.worker_poll_seconds)
    with runner.sessions() as session, session.begin():  # type: ignore[operator]
        session.execute(text("SET LOCAL ROLE outcomeos_worker"))
        session.execute(
            text("SELECT public.outcomeos_worker_heartbeat(:id,'draining')"), {"id": worker_id}
        )


if __name__ == "__main__":
    main()
