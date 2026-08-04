# Implementation plan

The phases are sequential risk gates, not release-date promises. Work inside a phase should prioritize the smallest vertical slice of the **persistent order-to-billing demo journey** in `PRODUCT.md`, rather than broad but disconnected screens or connector mocks.

## Phase 0 — reproducible foundation

Establish monorepo boundaries, strict TypeScript/Python skeletons, lockfiles, local infrastructure, documentation, quality commands, CI, migration validation, secret scanning, and production guards for demo facilities.

**Exit criteria:** a clean checkout passes `make setup` and `make verify`; CI installs only from lockfiles; web/API production configuration rejects demo auth and mock integrations; capability status is honest; no secrets are detected. A running order journey is not required.

## Phase 1 — secure tenant and persistence core

Implement versioned migrations, tenant/membership/customer models, local demo sessions, tenant-derived authorization, repository scoping, idempotency records, audit events, transaction helpers, error conventions, and integration-test database isolation. Design the production OIDC boundary without claiming a provider implementation.

**Exit criteria:** customer data persists across restart; authorization derives tenant context server-side; every tenant repository requires it; same-tenant tests pass; cross-tenant read/write/list/search/export and identifier-confusion tests fail closed; migrations apply to empty and prior schemas and roll forward in CI; audit and idempotency facts commit atomically.

## Phase 2 — persistent order-to-invoice slice

Build customer creation, draft order lines, exact server-side calculations, edits/versioning, acceptance, invoice issuance, list/detail pages, optimistic concurrency, and durable audit history. Use one currency per document and an explicit rounding policy before adding breadth.

**Exit criteria:** from an empty database a demo user completes customer → draft order → accepted order → issued invoice through the UI; refresh and service restart preserve facts; issued totals exactly reconcile and trace to an accepted immutable order version; invalid state transitions, mixed currencies, stale writes, duplicate idempotency keys, and cross-tenant access are tested and rejected.

## Phase 3 — billing completion and reliable work

Add manual payment records and allocations, invoice balance/status derivation, credits/voids, transactional outbox, worker runtime, invoice document generation/delivery simulation, evidence storage quarantine, structured telemetry, and retry/dead-letter operations.

**Exit criteria:** the persistent journey ends in partial/paid balance with exact reconciliation; over-allocation and duplicate financial effects are impossible under concurrency/retry tests; accepted/issued facts remain immutable; worker restart and repeated delivery are safe; mock delivery is unmistakably labeled and production-inaccessible; operators can trace a command through audit/outbox attempts.

## Phase 4 — hardened product workflow

Add role administration, search/export boundaries, accessibility, notification preferences, operational dashboards, rate limits, backup automation, and broader order/invoice edge cases. Exercise migration and restore paths with production-shaped volumes.

**Exit criteria:** primary journey meets agreed accessibility and performance budgets; restore exercise meets documented draft recovery objectives; authorization matrices and security regression suites pass; dashboards/alerts detect stuck outbox work and reconciliation failures; operations runbooks have been exercised.

## Phase 5 — controlled integrations

Select integrations only from validated user need. Implement one adapter at a time under `INTEGRATIONS.md`, beginning with production identity if launch requires it, then payment/tax/accounting capabilities as separately approved. Preserve internal financial truth and reconciliation boundaries.

**Exit criteria:** each connector has threat review, least-privilege scopes, encrypted tenant credentials, signature verification, idempotency, rate-limit/retry behavior, deletion, auditability, freshness/error UI, contract tests, and sandbox evidence. Sandbox-tested is still not live-tested. No capability is marked live until a controlled live transaction and reconciliation are independently verified.

## Phase 6 — production readiness and launch

Complete capacity and failure testing, privacy review, threat modeling, incident exercises, penetration testing, dependency/container review, access review, legal/compliance decisions, support ownership, staged rollout, and launch-gate review.

**Exit criteria:** production identity and tenant isolation are verified; backups and restores meet approved RPO/RTO; alerts and incident/rollback runbooks are exercised; financial reconciliation and audit evidence are reviewed; demo/mock code is disabled by code, configuration, and deployment policy; owners sign off on security, product, finance, and operations gates. Only then may verified capabilities be described as production-ready.
