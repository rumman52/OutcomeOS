# Architecture

## System context

The intended system has a Next.js browser application (`apps/web`), a FastAPI domain API (`apps/api`), and an asynchronous worker boundary (`apps/worker`). PostgreSQL is the system of record; Redis is limited to disposable coordination, cache, and rate-limit data; S3-compatible storage holds evidence objects. Provider access occurs only through backend adapters. Today, only the web/API skeleton and health endpoint run; the worker and persistence described here are targets.

## Monorepo boundaries

| Path | Responsibility |
| --- | --- |
| `apps/web` | Server-rendered UI and browser interactions; never authoritative for authorization or totals |
| `apps/api` | HTTP boundary, tenant authorization, domain commands, persistence transactions |
| `apps/worker` | Asynchronous delivery and synchronization (reserved; not implemented) |
| `packages/contracts` | Framework-independent versioned TypeScript contracts and value shapes |
| `infra/migrations` | Ordered, transactional schema history |
| `infra` | Local dependencies and future deployment assets |
| `scripts` | Repeatable developer and operational automation |

## Domain and persistence model

The first bounded context contains Tenant, Membership, Customer, Order/OrderVersion, Invoice, Credit, Payment, Allocation, IdempotencyRecord, and AuditEvent. Every tenant-owned row includes `tenant_id`; foreign keys and tenant-local uniqueness include it. Repositories require a tenant context rather than accepting an optional filter. Database row-level security is planned defense in depth, not a substitute for application authorization.

Financial aggregates are computed in the domain layer with decimal quantity/rate rules and persisted monetary minor units. Accepted order versions and issued invoices are immutable snapshots. State transitions and related audit/outbox records commit atomically. Tenant-scoped idempotency records store request fingerprints and stable results so a reused key with different input is rejected.

## Request and event flow

1. The API validates a real or explicitly local-demo principal and derives tenant/actor context.
2. Authorization runs before repository access; inputs and state transition preconditions are validated.
3. A database transaction locks relevant aggregates, applies exact calculations, persists facts, audit events, idempotency result, and an outbox event.
4. The worker eventually claims outbox work and records delivery attempts. Handlers are idempotent because delivery is at least once.
5. APIs expose stable resource versions for optimistic concurrency. Logs use opaque identifiers and redact sensitive content.

## Trust boundaries and failure behavior

The browser is untrusted. Provider webhooks, uploaded files, queues, caches, and all tenant identifiers are untrusted. PostgreSQL is authoritative; Redis loss must not change financial truth. External timeouts cannot leave a committed provider effect without a recoverable reconciliation state. Production startup rejects demo authentication and mock adapters.

## Deployment shape

Production is intended to separate web, API, worker, managed PostgreSQL, managed Redis, private object storage, and a secret manager with independently scoped identities. `docker-compose.yml` is local development only. Availability, scaling, recovery objectives, and provider selections remain undecided and must not be inferred from this target diagram.
