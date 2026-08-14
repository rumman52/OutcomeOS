# Milestone 2 Part 3: durable pipeline implementation plan

**Baseline:** `3e3f744411e68eaeb9d54e5a5569788bd7240121` (main workflow
`31829054612`). Remote fetch and workflow-page access were attempted before work; the
execution environment returned HTTP 403 and 401 respectively, so the clean local SHA is
the authoritative fallback permitted by the delivery brief.

**Scope boundary:** This plan implements durable ingestion operations only. It makes no
live-provider calls and does not implement Milestone 3 evaluation, contracts, attribution,
billing, disputes, AI, or a complete UI.

## Checkpoint 1 — durable outbox worker

1. Write focused tests for configuration, handler classification, `run_once`, backoff,
   lease-token fencing, and graceful one-shot/daemon behavior.
2. Add reversible migration `20260815_0006_durable_pipeline.py`, retaining a linear head.
   Add one-way attempt finalization, a least-privilege worker role, locked-down
   `SECURITY DEFINER` claim/finish/lease-loss/heartbeat functions, heartbeat storage, and
   the additive tables required by checkpoints 2 and 3.
3. Implement a PostgreSQL job repository and handler registry. Claims use
   `FOR UPDATE SKIP LOCKED`, unique bounded leases, atomic attempts, deterministic bounded
   backoff, maximum attempts, safe error codes, and lease-token fencing.
4. Replace the worker entry point with an explicit PostgreSQL runtime that never imports
   sandbox state, plus a separately selected development/test sandbox path, `run_once`,
   `--once`, sleep-based polling, and signal-driven draining.
5. Prove concurrency, expired recovery, stale completion denial, outcomes, one-way attempt
   finalization, worker-role denial, and heartbeat behavior with PostgreSQL integration
   tests.
6. Run focused worker tests and commit this checkpoint independently.

## Checkpoint 2 — replay and reconciliation

1. Write authorization, tenant-isolation, lineage, idempotency/conflict, health, storage
   listing, and anomaly tests first.
2. Add focused replay and reconciliation schemas/services/routers. Derive tenant context
   only from authenticated principals and require explicit permissions; owners and
   administrators alone may start reconciliation.
3. Atomically persist replay/control canonical events, lineage/run state, outbox jobs, and
   audit records. Preserve source events and raw evidence.
4. Add a reconciliation handler that records only allow-listed anomaly metadata and never
   repairs evidence implicitly. Cover receipts/events/jobs, evidence existence/digests,
   tenant-prefix orphan objects, leases, and attempts.
5. Extend object storage with bounded, paginated, tenant-prefix-only listing.
6. Replace static worker health with fresh/missing/stale/draining/unavailable semantics.
7. Run focused and real PostgreSQL/MinIO tests, then commit independently.

## Checkpoint 3 — CSV ingestion and operational verification

1. Write strict header/UTF-8/limit tests, permissions, isolation, idempotency/conflict,
   cleanup, mixed-row, encrypted-object, retry-safety, and count/state tests first.
2. Implement raw `text/csv` upload and status routes with an explicit `imports:write`
   permission. Validate bytes, rows, columns, field lengths, exact unique headers, and
   forbidden server-owned fields before scheduling work.
3. Store original bytes through encrypted S3 storage; atomically persist import metadata,
   an internal control event, and `ingest.csv.v1` job; delete a newly created object when
   database persistence fails.
4. Add an idempotent CSV worker handler that verifies the digest, parses each row through
   `PublicEventInput`, creates accepted canonical events/jobs, writes sanitized numbered
   errors for rejected rows, and finalizes accurate counts without logging row data.
5. Update environment documentation, architecture, event catalog, operations, security,
   implementation status, migration validation, and CI integration gates while keeping
   capability claims explicitly pre-production.
6. Run all focused tests, then `make setup`, `make lint`, `make typecheck`, `make test`,
   `make test-integration`, `make migrations-check`, `make build`, `make e2e`, `make verify`,
   secret scanning, and `git diff --check`. Commit independently, push if authenticated,
   and open exactly one draft PR for green CI and human review.

