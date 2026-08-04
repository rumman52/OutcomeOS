# Implementation plan

Updated 2026-08-04 during the competition-MVP hardening pass.

## Confirmed baseline problems

- `pnpm-lock.yaml` and `apps/api/uv.lock` were absent, so frozen installs could not run.
- Network/proxy restrictions prevented generating genuine lockfiles in this environment; no lockfile was hand-written.
- The runtime API still uses the deterministic local store for this sandbox pass; PostgreSQL SQLAlchemy models and Alembic remain the canonical database direction but are not fully connected to every endpoint yet.
- Approval previously created lead, order, verification, delivery, COD settlement, outcome, billable result and ledger fee at once.
- Delivery and COD webhooks previously called the same complete workflow.
- Several endpoints accepted tenant headers without a server-side session/membership model.
- The dashboard had a fallback financial data path when the API failed.
- The Playwright test targeted the obsolete sandbox order form.
- The worker was a one-shot placeholder.

## Implemented in this pass

1. Split the deterministic Bangladesh journey into explicit persisted commands:
   - `tool_proposal.approved` creates lead/order/attribution only.
   - `lead.verification_completed` records deterministic checks.
   - `shipment.delivered` records delivery evidence only.
   - `payment.cod_settled` records COD settlement evidence only.
   - `outcome.evaluate` creates the BDT 150 fee only when all evidence is present.
2. Added webhook receipt/idempotency tracking in the local store so replayed delivery/COD events do not duplicate billable results or ledger debits.
3. Preserved append-only dispute reversal with a linked BDT 150 credit; the original debit remains present.
4. Added a development-only demo sign-in cookie and fail-closed production behavior for demo sign-in.
5. Replaced dashboard fallback finances with an explicit service-unavailable state.
6. Added professional route shells for `/login`, `/overview`, `/inbox`, `/inbox/[conversationId]`, `/leads`, `/orders`, `/outcomes`, `/outcomes/[outcomeId]`, `/profit`, `/disputes`, `/disputes/[disputeId]`, `/integrations`, and `/settings`.
7. Replaced obsolete unit/E2E test targets with current dashboard and journey assertions.

## Remaining work before production/live claims

- Generate genuine pnpm/uv lockfiles once registry access is available.
- Wire all runtime API paths to PostgreSQL sessions, Alembic migrations and RLS policies instead of the deterministic local store.
- Expand composite tenant-aware foreign keys across all business records and run PostgreSQL RLS integration tests against a real PostgreSQL service.
- Implement durable outbox polling, bounded retries/dead-letter tables and a real worker heartbeat in PostgreSQL.
- Replace demo cookie auth with production OIDC while keeping demo auth fail-closed in production.
- Connect real provider webhooks only after credentials, retained evidence, signature verification and operational runbooks exist.
