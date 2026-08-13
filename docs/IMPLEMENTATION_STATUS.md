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
- Milestone 1 code now includes provider-neutral OIDC/JWKS signature and claim verification,
  explicit deny-by-default role policy, one-time hashed/scoped API-key primitives, and
  persisted-identity plus active-membership principal resolution. These boundaries use local
  deterministic cryptographic fixtures in tests; no live identity provider is connected.
- Additive revision `20260808_0002_global_core` defines workspace regional settings, OIDC
  identities, invitations, API keys, external grants, append-only audit events, immutable tenant
  triggers, expanded RLS, and composite tenant-aware foreign keys without modifying the applied
  `20260804_0001` revision.

### Sandbox or partial only

- JSON runtime persistence, demo-cookie authentication, deterministic AI, seeded Bangladesh fixture and one-shot worker remain legacy sandbox implementations.
- PostgreSQL is the default runtime backend and JSON wiring is mounted only when explicitly
  configured as a development/test sandbox. Staging and production validation rejects JSON,
  demo auth, mocks, deterministic AI, and default secrets. PostgreSQL migration/RLS tests are
  implemented but have not run in this environment because Docker/PostgreSQL is unavailable.
- Web routes remain mostly repeated shells rather than complete workflows.
- RLS and composite-FK tests use separate migration-owner and restricted `NOBYPASSRLS` roles,
  but remain unexecuted in this environment because no PostgreSQL server or Docker executable is
  available.

### Not implemented / not connected

- Live OIDC verification, durable outbox worker, production evidence storage, contracts,
  attribution, billing ledger, disputes, privacy workflows and complete operational UI.
- Shopify, Stripe, Meta, Google, TikTok, HubSpot, Calendly, WhatsApp, fulfilment providers and hosted LLMs. Adapter interfaces or documentation must never be read as connectivity.
- CI proof for the Milestone 1 PostgreSQL 17/pgvector boundary remains pending. The checked-in,
  uv-generated `apps/api/uv.lock` passes both `uv lock --check` and frozen synchronization; the
  pnpm lockfile also passes frozen installation.

## Exact next step

Run the Milestone 1 integration suite in CI with its disposable PostgreSQL 17/pgvector service,
review the required zero-skip evidence, and fix any evidence-based failure before beginning
Milestone 2.
