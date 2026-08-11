# OutcomeOS Milestone 1 closure and Milestone 2 event-pipeline plan

This plan records the approved execution sequence. A capability is complete only when its executable
gate passes; no provider adapter, fixture, or protocol is a live integration.

## Gate 0: preserve and establish the baseline

1. Record Git status, history, branches, reflogs, unreachable objects, tool versions, and available
   PostgreSQL/container tooling.
2. Read repository instructions plus `README.md`, `Makefile`, `.env.example`, CI, API dependency
   metadata, both immutable migrations, backend source/tests, web build/E2E configuration, and all
   documentation.
3. Inspect any candidate recovery commits before reuse. If none exist, describe Milestone 1 work as
   reconstructed rather than recovered.

## Gate 1: close Milestone 1 before pipeline work

1. Generate `apps/api/uv.lock` with `uv lock --project apps/api`; align `Makefile`, CI, and docs on
   frozen installs without changing the pinned pnpm lockfile.
2. Add focused failures under `apps/api/tests/`, `apps/api/tests/integration/`, and `apps/web/e2e/`
   for any observed lint, strict typing, clean-build, authentication, authorization, production
   configuration, tenant isolation, or deterministic E2E defect; make the smallest repair in the
   corresponding `outcomeos_api` module or web configuration.
3. Harden the PostgreSQL harness in `apps/api/tests/integration/`, `Makefile`, and CI so missing
   prerequisites fail, migration-owner and restricted execution roles are distinct, required tests
   never skip, and connection tenant context cannot leak.
4. Exercise clean migration, upgrades from revisions `20260804_0001` and `20260808_0002`, one-head
   validation, downgrade/upgrade, pgvector, restricted-role RLS, immutable tenant identifiers,
   composite tenant foreign keys, and negative cross-tenant operations without modifying either
   applied migration.
5. Run the complete Milestone 1 command gate and record only observed evidence in
   `docs/IMPLEMENTATION_STATUS.md`. Stop before Milestone 2 on any unverified security-critical item.

## Milestone 2: schema and public ingestion

1. Add a reversible `apps/api/migrations/versions/20260812_0003_event_pipeline.py` containing the
   tenant-scoped endpoint, secret, receipt, event, job, attempt, CSV, replay, reconciliation, and
   anomaly tables plus payload-free worker heartbeats, candidate keys, composite foreign keys,
   constraints, indexes, immutable-tenant/append-only enforcement, forced RLS, and a least-privilege
   public-token resolver.
2. Add strict canonical input parsing in `outcomeos_api/events/`; authenticated encryption and
   rotation in `outcomeos_api/integrations/`; exact raw-byte signature verification in
   `outcomeos_api/ingestion/`; and bounded object-store ports plus memory/S3 implementations in
   `outcomeos_api/storage/`.
3. Add tenant-required PostgreSQL repositories and an ingestion service that performs endpoint
   resolution, signature verification, duplicate-key-safe validation, consent handling, evidence
   storage, and atomic receipt/event/original-job persistence with explicit duplicate/conflict
   semantics.
4. Keep HTTP translation in focused routers under `outcomeos_api/api/` and only mount routers and
   lifecycle dependencies from `main.py`. Add endpoint-management and public-webhook tests before
   implementation, including cross-tenant and invalid-signature negative cases.

## Milestone 2: durable execution and operations

1. Replace the deployed worker path in `outcomeos_api/worker.py` with a PostgreSQL runtime backed by
   focused `outcomeos_api/jobs/` policy, repository, registry, and handler modules. Preserve the
   legacy one-shot behavior only behind an explicit non-production sandbox setting.
2. Test and implement atomic `SKIP LOCKED` claims, lease tokens, attempts, renewals, stale-owner
   rejection, deterministic retry/dead-letter policy, crash recovery, graceful shutdown, `--once`,
   continuous execution, and persisted heartbeat health.
3. Add tenant-authorized dead-letter list/detail/replay and reconciliation services/routes in
   `outcomeos_api/operations/`, preserving immutable lineage and safe audit metadata. Test concurrent
   replay, idempotency, safe repairs, unsafe anomalies, storage failures, and isolation.
4. Add streaming, bounded, idempotent asynchronous CSV upload/parsing in `outcomeos_api/imports/`,
   reusing canonical ingestion. Test encoding/header/row/byte/schema failures, mixed results,
   counters, duplicate events, lease recovery, object-store failure, and tenant isolation.

## Configuration, integration evidence, and documentation

1. Extend `outcomeos_api/config.py` and `.env.example` for webhook, keyring, storage, retention, CSV,
   worker, health, retry, and reconciliation limits; add production fail-closed tests for malformed,
   default, insecure, missing, or internally inconsistent settings.
2. Extend `Makefile`, `.github/workflows/ci.yml`, and disposable integration fixtures for PostgreSQL
   17/pgvector, separate restricted identities, and real loopback S3-compatible storage. Make
   `make verify` include every required gate, including zero-skip integration and E2E execution.
3. Update `README.md`, `.env.example`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`,
   `docs/INTEGRATIONS.md`, `docs/EVENT_CATALOG.md`, `docs/OPERATIONS.md`, API/webhook/CSV/storage
   documentation, and worker/retry/replay/reconciliation runbooks to match executable behavior and
   explicitly retain at-least-once and no-live-provider limitations.
4. Run frozen installs, lint, strict types, coverage-bearing unit tests, all zero-skip integration
   suites, web/API builds, migration checks and round trips, deterministic E2E, aggregate verify,
   and `git diff --check`. Review and commit only coherent, explicitly staged slices.

Milestone 3 contracts, attribution evaluation, outcome qualification, billing, disputes, postbacks,
and hosted AI are intentionally excluded.
