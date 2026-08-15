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
- Milestone 1 is verified at main SHA `76508c6c2210e7c7854be9ac3875ec465648e281` by successful
  push CI run `31781784962`, including PostgreSQL 17/pgvector migrations, restricted-role RLS,
  API and web quality gates, builds, Chromium E2E, coverage, and secret scanning.
- Milestone 2 Part 1 adds the reversible `20260814_0003` persistence foundation, AES-256-GCM
  integration-secret primitives, and a real S3-compatible adapter. These are infrastructure
  boundaries only; they are not public ingestion, worker execution, or a live integration.
- Milestone 2 Part 2 adds tenant-authorized endpoint lifecycle APIs, the restricted-role public
  token resolver, exact-raw-byte HMAC authentication with bounded secret overlap, strict canonical
  validation and consent, encrypted evidence storage, and atomic idempotent receipt/event/original
  job persistence. It does not execute that job or add a live provider.

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
- Milestone 2 PostgreSQL and MinIO integration tests require the draft PR's disposable CI services;
  Docker is unavailable in the local development environment used for this change.

## Exact next step

Complete Milestone 3 Part 2's immutable PostgreSQL evaluation history, transactional worker/service,
reconciliation, and authenticated read surface. The deterministic domain is implemented, but Part 2
is not complete until those slices and their protected checks pass. Part 3 attribution is next only
after Part 2 completion and has not started.

## Milestone 2 verification

Part 1 is verified at main SHA `534a0fd37b59a4a290bd579aa405ea169a6ee7d1` by workflow `31812759157`. Part 2 provider-neutral signed ingestion is implemented on a feature branch but is not verified or production-certified until CI is green on its final PR head. It includes no live provider, Part 3 worker, replay, reconciliation, or CSV processing.
# Milestone 2 Part 3 status

Durable PostgreSQL leases, fenced completion, attempt finalization, bounded reconciliation,
replay scheduling, worker heartbeat health, and the tenant-authorized CSV upload/status/worker flow
are implemented on the Part 3 feature branch pending mandatory PostgreSQL/MinIO and pull-request
CI verification. They are **not production certified**. There are no live providers, contracts,
attribution, billing, disputes, Milestone 3 evaluation, AI pipeline, or complete UI in this work.

Verified Part 2 baseline: `3e3f744411e68eaeb9d54e5a5569788bd7240121`; successful main
workflow: `31829054612`.

## Milestone 3 Part 1 status

Canonical digest-bound terms, exact fixed-fee/basis-point metadata, lifecycle services,
exact-digest authorized human acknowledgements, deterministic effective selection, and the
authenticated management/read API are implemented. Additive revision `20260815_0009` descends
from immutable `20260815_0008` and adds tenant-scoped command idempotency, a sanitized domain
outbox, persisted party authority, and overlapping-binding prevention. Milestone 3 Part 1 is verified
on merged `main`: workflow `31883490308` passed protected `api` and `web`, including 159 API tests at
90.92% coverage, nine integration tests with zero skips, and one migration head (`20260815_0009`).

The PR #32 repair now has 159 passing non-integration API tests at 90.92% total Python coverage,
including service, repository, API, idempotency, authority, validation, actor-attribution, and
rollback-boundary coverage. Local PostgreSQL/S3 integration and Chromium evidence remains
unavailable in the repair environment and must be supplied by the protected CI jobs before the
milestone status can change to complete. The later successful merged-main workflow above supplies
that evidence and supersedes this historical pre-merge note.

## Milestone 3 Part 2 status

The provider-neutral pure evaluator implements the four approved templates with bounded typed
inputs/results, stable canonical input and decision digests, tenant/subject isolation, exact event
digest binding, deterministic ordering and duplicate handling, aware-time half-open windows,
finalization, explicit lead acceptance, conflicts, disqualifiers, and currency consistency without
fee calculation. Local focused unit tests cover this domain behavior.

Immutable PostgreSQL revisions, atomic service/worker effects, reconciliation, and authenticated read
APIs remain incomplete. Part 2 is therefore not production-ready. Part 3, attribution, billing,
disputes, live providers, AI decisions, deployment, and production work have not started.
