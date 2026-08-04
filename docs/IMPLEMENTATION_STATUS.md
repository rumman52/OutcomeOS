# Implementation status

Last reviewed: 2026-08-04.

## Status vocabulary

implemented = code plus local automated coverage for stated scope; mocked = deterministic local behavior; partial = material gap remains; blocked = external dependency/approval needed; sandbox-tested/live-tested/production-ready require retained external evidence and are not claimed here.

## Capability ledger

| Capability | Status | Verification and limitations |
| --- | --- | --- |
| Canonical backend/frontend/migrations | implemented | Duplicate prototype Python package, root Python project, static frontend, and alternate SQL migrations were removed after porting useful behavior/design. |
| Local Bangladesh e-commerce demo journey | mocked | Deterministic local JSON persistence demonstrates campaign → conversation → AI proposal → approval → lead/order → verification → delivery/COD evidence → outcome → BDT 150 fee → BDT 340 contribution profit → dispute credit. |
| PostgreSQL schema/RLS | partial | Alembic model history remains canonical; full required table breadth and live PostgreSQL RLS tests are not complete in this change. |
| Demo auth | mocked | Server returns a local demo principal and rejects tenant switching except for seeded membership behavior. Production guards reject demo/mock flags and default deterministic AI/webhook secret. |
| External integrations | blocked | Meta, WhatsApp, Google, TikTok, Pathao, payment, OIDC, and real AI providers are NOT CONNECTED and not sandbox-tested/live-tested. |
| Worker | partial | `make dev-worker` runs a deterministic one-shot health/queue command; long-running claiming/retry/dead-letter worker remains future work. |
| Health/readiness | partial | Liveness is process-only; readiness checks local demo persistence honestly; worker health reports degraded without heartbeat. |
| Frontend | partial | Next.js renders responsive sandbox dashboard from API when available and no longer uses local-state order creation; full multi-route app remains future work. |
| Tests | partial | Unit/API-level tests cover deterministic MVP invariants; full PostgreSQL, concurrency, and Playwright acceptance evidence remains pending. |

No real provider integration is implemented, sandbox-tested, live-tested, or production-ready.
