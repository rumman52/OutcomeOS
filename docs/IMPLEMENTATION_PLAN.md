# Implementation plan

## Phase 0 — foundation

Establish monorepo tooling, strict web/API skeletons, local dependencies, CI, documentation, and production guards for demo features.

## Phase 1 — secure core

Add database migrations, workspace and membership models, production OIDC, session handling, tenant authorization, audit events, API error conventions, and integration tests. Exit only after cross-tenant negative tests pass.

## Phase 2 — outcome workflows

Implement outcome trees, initiatives, check-ins, metrics, ownership, activity history, accessible UI flows, and optimistic-concurrency rules.

## Phase 3 — evidence and operations

Add direct-to-object-storage uploads, scanning/quarantine, background workers, notifications, rate limits, structured telemetry, dashboards, alerts, backups, and restore exercises.

## Phase 4 — integrations

Prioritize providers through customer validation. Implement one connector at a time against the security contract in `INTEGRATIONS.md`; use staged rollouts and expose sync freshness and failures. A roadmap entry is never evidence of operation.

## Phase 5 — production readiness

Run performance and accessibility testing, threat modeling, privacy review, incident exercises, penetration testing, and launch-gate review. Disable demo paths independently in code, configuration, and deployment policy.
