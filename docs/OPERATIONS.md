# Operations

## Current scope

There is no production deployment. The Compose stack and all commands in this document are development foundations, not operational evidence. Service levels, RPO/RTO, paging ownership, regions, and production vendors require explicit decisions before Phase 6.

## Local lifecycle

1. Copy `.env.example` to `.env` and keep local credentials out of Git.
2. Run `make setup`, then `make infra-up`.
3. Run `make dev` for applications. Use `make infra-down` to stop dependencies.
4. Run `make verify` before commit. `make migrations-check` is structural only; migration execution is not implemented.
5. `make seed` is safe but currently applies nothing and says so.

## Required production runbooks

Before launch, owners must write and exercise runbooks for deployment/rollback, migration failure, backup/restore, tenant access incident, credential rotation, suspected financial duplication, reconciliation mismatch, stuck outbox/dead letter, provider outage/rate limit, webhook replay, data export/deletion, and demo/mock configuration rejection.

## Observability and alerting

Planned telemetry uses structured redacted logs, metrics, and traces correlated by opaque request, tenant, command, aggregate, and outbox identifiers. Never log credentials, session material, raw webhook bodies, full financial documents, or unnecessary personal data. Alerts must cover availability/error budget, authorization denial anomalies, database saturation, migration state, job age/retries, webhook verification failure, duplicate/idempotency conflicts, and financial reconciliation failures.

## Backup, recovery, and reconciliation

PostgreSQL is the financial system of record. Define approved RPO/RTO before choosing backup schedules. Backups must be encrypted, access-controlled, retention-limited, restore-tested, and paired with object-version recovery. Redis must remain disposable. A restore exercise must verify tenant isolation, order/invoice links, audit/outbox continuity, and exact financial totals—not merely database startup.

Daily financial operations should reconcile document totals and state transitions internally, then separately reconcile any provider settlement to immutable provider references. Differences create an auditable exception; they are never silently patched.

## Incident principles

Protect tenants and financial integrity before availability: stop unsafe writes, preserve evidence, communicate through the designated incident channel, and avoid destructive repair. Rotate exposed credentials, quarantine unverified events, use new correcting facts instead of editing issued records, and complete a blameless review with tracked actions.
