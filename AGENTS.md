# OutcomeOS contributor guide

These instructions apply to the entire repository. More deeply nested `AGENTS.md` files may refine them.

## Repository conventions

- Deployable services live in `apps/`, framework-independent shared code in `packages/`, deployment and database assets in `infra/`, documentation in `docs/`, and developer automation in `scripts/`.
- Keep domain rules out of HTTP handlers, React components, job runners, and provider SDK adapters.
- Treat API and event contracts as versioned interfaces. Update producers, consumers, contract tests, and documentation together.
- Use the checked-in pnpm and uv lockfiles. Do not hand-edit generated lockfiles.
- Add tests for behavior changes and keep TypeScript and Python checks strict.
- Update `docs/IMPLEMENTATION_STATUS.md` when a capability changes state. Never describe a mock, demo, sandbox result, plan, or unverified integration as live or production-ready.

## Tenant isolation

- Every tenant-owned record, query, cache key, object-storage key, event, job, audit entry, and integration credential must carry an immutable `tenant_id`.
- Derive tenant context from an authenticated server-side principal; never trust a client-supplied tenant identifier by itself.
- Authorize every tenant-scoped read and write. Repository methods must require tenant context and database policies should provide defense in depth.
- Never use an unscoped lookup followed by an in-memory tenant check. Unique constraints for tenant data must include `tenant_id` unless global uniqueness is intentional and documented.
- Add positive and negative isolation tests, including cross-tenant identifiers, list/search/export paths, background jobs, and object URLs.

## Financial invariants

- Represent money as an integer number of minor units plus an ISO 4217 currency. Never use binary floating point or silently combine currencies.
- Persist the price, tax, discount, quantity, currency, and rounding inputs used for every calculated line. Server-side totals are authoritative.
- An accepted order and an issued invoice are immutable accounting facts. Correct them with explicit version, credit, void, or adjustment records; do not overwrite history.
- Invoice totals must reconcile exactly: line subtotals, discounts, tax, credits, payments, balance, and currency must satisfy documented equations at the transaction boundary.
- Payment and credit allocations cannot be negative or exceed the unallocated amount. State transitions must follow an explicit state machine.
- Commands that can create orders, invoices, ledger entries, or provider side effects require tenant-scoped idempotency keys and atomic persistence. Retries must not double bill.
- Preserve an append-only audit trail linking actor, tenant, source order, invoice, calculations, and external references. Financial timestamps are stored in UTC; business dates retain their applicable timezone.

## Security constraints

- Deny by default, validate all inputs, apply least privilege, and keep credentials out of source, logs, URLs, fixtures, and client bundles.
- Document configuration names and safe descriptions in `.env.example`; never add credential values. Production credentials belong in a secret manager and must be rotatable.
- Encrypt sensitive data in transit and at rest, redact logs, verify webhook signatures before parsing business data, and constrain outbound provider calls.
- Demo authentication and mock integrations are local/test facilities only. They **must fail closed at startup when `APP_ENV=production`**, even if another environment flag attempts to enable them.
- Do not weaken an authorization or financial invariant to make a demo work.

## Required quality commands

Run `make verify` before proposing a change. Individual commands are:

- `make setup`, `make dev`
- `make lint`, `make typecheck`, `make test`, `make e2e`
- `make build`, `make migrations-check`, `make seed`
- `make verify` (aggregate non-destructive verification)

CI installs with `pnpm install --frozen-lockfile` and `uv sync --frozen`; local changes must remain reproducible under those constraints.
