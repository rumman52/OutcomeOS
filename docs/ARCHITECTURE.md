# Architecture

OutcomeOS is a modular monolith with canonical code in these locations:

| Path | Responsibility |
| --- | --- |
| `apps/web/app` | Next.js UI. Browser renders API results and is never authoritative for money or authorization. |
| `apps/api/src/outcomeos_api` | FastAPI boundary, deterministic demo workflow, domain invariants, persistence adapter, config guards. |
| `apps/api/migrations/versions` | Alembic migration history. Alternate SQL migration locations have been removed. |
| `packages/contracts` | Versioned shared TypeScript contract support. |
| `docs` | Product, status, security, operations, and demo evidence. |

## Current persistence

PostgreSQL is the default runtime backend. The local competition demo can persist deterministic
seeded state in a JSON file only when `PERSISTENCE_BACKEND=json_sandbox` is explicitly selected in
development or test. Staging and production reject that setting. The Alembic history is canonical;
full RLS enforcement remains unverified until the checked-in restricted-role PostgreSQL integration
suite runs in an environment with PostgreSQL.

## Provider boundary

Sandbox adapters are deterministic and local. Real provider adapters must be added behind configuration, signature verification, tenant-scoped credential storage, idempotency, retries, and retained sandbox/live evidence before any stronger capability label is used.

## Operational probes

`/health` is process liveness. `/ready` checks PostgreSQL connectivity and the expected migration
head, or reports the explicitly selected local JSON sandbox. `/worker-health` remains degraded
because the durable worker is a Milestone 2 capability.

## Event-pipeline foundation

Migration `20260814_0003` establishes tenant-scoped integration endpoints and encrypted secret
versions, immutable receipts and canonical events, outbox/job-attempt records, CSV import metadata,
replay lineage, reconciliation records, and payload-free worker heartbeats. Composite foreign keys
prevent cross-tenant relationships; forced RLS and immutable-tenant triggers provide defense in
depth. No public ingress or worker runtime is mounted in Part 1.

Raw evidence is accessed through a provider-neutral object-storage port. The S3-compatible adapter
uses deterministic `tenants/{tenant_id}/...` keys, conditional creation, bounded reads/writes,
SHA-256 metadata verification, and server-side encryption requests.

## Global modular-monolith direction (2026-08-08)

The accepted boundary decision is recorded in `docs/decisions/0001-global-modular-monolith.md`. New framework-independent code begins under `common`, `events`, and `outcomes`; the existing `mvp.py` remains legacy sandbox code until PostgreSQL repositories replace it incrementally. PostgreSQL—not the JSON store—is the intended non-test source of truth.

## Secure public ingress

Public ingress resolves an opaque token through a security-definer PostgreSQL function returning only tenant and endpoint IDs. Authentication covers exact raw bytes before strict canonical parsing. Encrypted evidence storage precedes one atomic receipt, canonical-event, and pending-outbox transaction; outbox processing remains outside Part 2.
