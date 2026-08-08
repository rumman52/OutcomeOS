# Implementation status

## Verified implementation levels

OutcomeOS is **in active transformation** from a Bangladesh-specific deterministic sandbox into a global outcome-verification platform. It is not production-ready and no external provider is connected or live-tested.

### Implemented and unit-testable

- Global workspace region value object for ISO country/currency identifiers, BCP 47-shaped locale tags and real IANA timezone validation.
- Exact money value object using integer minor units, including USD (2), JPY (0) and BHD (3) exponent behavior and explicit mixed-currency rejection.
- Version 1 provider-neutral canonical event envelope with tenant identity, consent purpose, aware timestamps, payload digests, references, optional exact money and processing status.
- Explicit outcome state machine for captured through settled/credited, with append-only transition record shape, audit fields and optimistic version increments.
- Existing tenant-scoped deterministic sandbox behavior remains available only as legacy local/test functionality.
- Production configuration rejects demo authentication, mock integrations, deterministic AI and the default webhook secret.

### Sandbox or partial only

- JSON runtime persistence, demo-cookie authentication, deterministic AI, seeded Bangladesh fixture and one-shot worker remain legacy sandbox implementations.
- PostgreSQL models and the initial Alembic migration are partial and are not yet the sole runtime source of truth.
- Web routes remain mostly repeated shells rather than complete workflows.
- RLS is represented by schema assertions, not yet proven through PostgreSQL integration tests in this environment.

### Not implemented / not connected

- OIDC/JWKS authentication, API keys, global production schema, durable outbox worker, production evidence storage, contracts, attribution, billing ledger, disputes, privacy workflows and complete operational UI.
- Shopify, Stripe, Meta, Google, TikTok, HubSpot, Calendly, WhatsApp, fulfilment providers and hosted LLMs. Adapter interfaces or documentation must never be read as connectivity.
- Genuine pnpm and uv lockfiles. Generation was attempted with the declared package managers on 2026-08-08 but registry access was rejected by the environment proxy; no lockfile was hand-written.

## Exact next step

Create additive migration `apps/api/migrations/versions/20260808_0002_global_core.py` and PostgreSQL integration fixtures for tenants, memberships, canonical receipts/events, outcome instances/transitions and tenant-aware RLS/foreign-key denial tests. Do not edit the applied `20260804_0001` revision.
