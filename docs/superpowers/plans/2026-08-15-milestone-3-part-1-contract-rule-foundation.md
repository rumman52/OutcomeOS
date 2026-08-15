# Milestone 3 Part 1: contract and rule-version foundation

## Repository patterns and boundaries

- Reuse `outcomeos_api.domain.DomainError`, immutable dataclasses, the authorization policy,
  tenant-composite keys/RLS patterns from migrations `0002`–`0007`, and transactional audit/outbox
  tables already in the schema.
- Add framework-independent contract logic under `outcomeos_api/contracts/`; HTTP and SQL adapters
  must only translate and persist domain commands.
- Add one reversible revision, `20260815_0008`, descending from `20260815_0007`.
- Part 1 stores rules and pricing metadata and selects contracts. It does not execute rules,
  attribute outcomes, calculate fees, bill, dispute, call providers, or make AI decisions.

## TDD work plan

- [x] Record the verified base, migration head, applicable instructions, and exact file patterns.
- [x] Write failing unit tests for canonical digests, pricing boundaries, lifecycle transitions,
  exact-digest acceptance, and deterministic effective selection; confirm failure.
- [x] Add the minimum framework-independent value objects and lifecycle services; make tests pass.
- [x] Add migration tests/inspection requirements, then implement additive schema, constraints,
  immutable-row triggers, indexes, composite foreign keys, forced RLS, and downgrade.
- [ ] Add failing service/API tests for authorization, tenant isolation, pagination,
  idempotency, optimistic concurrency, audit/outbox atomicity, then implement adapters/routes.
- [ ] Run PostgreSQL restricted-role, concurrent activation, and migration round-trip tests.
- [ ] Run locked installs, lint, typecheck, unit/integration tests, build, secret scan, web build,
  Playwright, migrations check, and aggregate verification as available.
- [ ] Update architecture/API/status documentation with the acknowledgement limitation and exact
  verification evidence; self-review; stage exact paths and create focused commits.

## Domain interfaces

- `canonical_document` / `document_digest`: deterministic UTF-8 JSON and SHA-256.
- `FixedFee` / `BasisPoints`: exact integer-only pricing terms with matching ISO currency.
- `RuleVersion`: draft/published/retired immutable version state.
- `ContractVersion`: draft/proposed/active/superseded/withdrawn, digest-bound acceptances.
- `PerformanceContract`: draft/active/suspended/terminated aggregate state.
- `select_effective_contract`: trusted source identity plus `occurred_at`, with bounded no-match
  and ambiguity results and stable ordering.

## Files and commit boundaries

1. This plan (`docs: plan milestone three contract foundation`).
2. `contracts/domain.py`, unit tests, migration `20260815_0008`, and migration-head constant
   (`feat: add immutable contract and rule foundation`).
3. Contract repositories/schemas/router plus API and PostgreSQL tests
   (`feat: add contract management and source binding APIs`).
4. Architecture/API/status docs and verification evidence
   (`docs: document milestone three part one`).
