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

The local competition demo persists deterministic seeded state in a JSON file (`OUTCOMEOS_DEMO_DB`, default `/tmp/outcomeos-demo.json`) so refresh and service restart preserve the journey without provider credentials. PostgreSQL remains the intended source of truth and the Alembic history is canonical, but full RLS/table breadth is marked partial until integration evidence exists.

## Provider boundary

Sandbox adapters are deterministic and local. Real provider adapters must be added behind configuration, signature verification, tenant-scoped credential storage, idempotency, retries, and retained sandbox/live evidence before any stronger capability label is used.

## Operational probes

`/health` is process liveness. `/ready` checks whether the local persistent demo store is available and reports its demo nature. `/worker-health` reports degraded when no worker heartbeat exists.
