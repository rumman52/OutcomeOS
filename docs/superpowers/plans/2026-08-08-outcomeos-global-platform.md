# OutcomeOS global platform execution plan

This plan is evidence-driven: a checkbox means code and tests exist, not that a provider is live.

## Dependencies and sequence

1. **Baseline** — `package.json`, `pnpm-lock.yaml`, `apps/api/pyproject.toml`, `apps/api/uv.lock`; run frozen installs and capture blockers. Add `docs/decisions/0001-global-modular-monolith.md`. Isolate `mvp.py` behind sandbox-only wiring.
2. **Global domain** — add `outcomeos_api/common`, `events`, and `outcomes`; test money exponents, currency mismatch, regional configuration, canonical envelopes and every transition before repository work.
3. **PostgreSQL/auth** — additive `apps/api/migrations/versions/20260808_0002_global_core.py`; add `auth`, tenant-required repositories, RLS/composite FKs and PostgreSQL denial tests. Configure standards-based OIDC/JWKS and hashed scoped API keys.
4. **Pipeline/worker** — webhook receipt + outbox transaction, `SKIP LOCKED` worker, retry/dead letter/heartbeat/replay/reconciliation tests.
5. **Contracts/outcomes** — immutable rule/contract/attribution versions, fixed/basis-point pricing and evaluator tests.
6. **Billing/disputes** — exact minor-unit profit, invoices, balanced ledger, credits, obligations and idempotency/reconciliation tests.
7. **AI** — provider-neutral gateway, tenant-vector retrieval, discriminated tools, approval/handoff and adversarial evals without CI network calls.
8. **Integrations** — signed webhook, CSV, Shopify, Stripe, postback protocols then consent-aware Meta/Google Data Manager/TikTok adapters; fixture contract tests and honest health states.
9. **Web** — API client/Intl formatters/externalised English messages, then each required route and Playwright workflows.
10. **Hardening** — privacy workflows, structured telemetry, threat model, backup/migration runbooks, Vercel/Render configuration and CI PostgreSQL services.

## Migration rules

Never edit `20260804_0001_mvp_tenant_schema.py`. Each milestone uses an additive revision with tenant-aware unique constraints and foreign keys. Test `alembic upgrade head` from the existing revision and downgrade only in disposable databases.

## Test-first loop for every milestone

1. Add positive, negative, cross-tenant, replay and invariant tests as applicable.
2. Implement the smallest domain service/repository/adapter change.
3. Run focused tests, then `make lint`, `make typecheck`, `make test`, `make build`, `make migrations-check`, `git diff --check`, and `make verify`.
4. Update `docs/IMPLEMENTATION_STATUS.md` with evidence and the exact next unchecked step.

## Current execution

- [x] Repository and current runtime inspected; legacy JSON persistence, demo auth, partial schema, deterministic AI/worker and repeated web shells confirmed.
- [x] Global Money/region primitives, canonical event v1 envelope and explicit outcome state machine added with focused tests.
- [ ] Generate lockfiles using pnpm 10.14.0 and uv (blocked by registry proxy on 2026-08-08; do not hand-write).
- [ ] Next: create additive global-core migration and PostgreSQL tenant-isolation integration harness.
