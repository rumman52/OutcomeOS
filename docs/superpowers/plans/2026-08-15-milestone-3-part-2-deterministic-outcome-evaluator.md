# Agentic worker plan: Milestone 3 Part 2 deterministic outcome evaluator

> Work test-first, preserve tenant and financial invariants, stage exact paths only, and stop before
> attribution or billing. The worker must record failed and passing commands as it completes slices.

## Interfaces and files

- `outcomeos_api.outcomes.evaluator`: immutable trusted projections, bound request/result types,
  canonical input/decision digests, validation, temporal filtering, and deterministic evaluation.
- `outcomeos_api.outcomes.templates`: four explicit, bounded template strategies and registry.
- `outcomeos_api.outcomes.state_machine`: factual rejection transition only; timestamps injected.
- `apps/api/migrations/versions/20260815_0010_outcome_evaluation.py`: additive tenant-owned
  projection and append-only revision/evidence/transition persistence.
- `apps/api/tests/test_outcome_evaluator.py` and PostgreSQL migration tests: deterministic,
  boundary, isolation, replay, constraint, RLS, and append-only coverage.
- `docs/OUTCOME_EVALUATION.md`, `docs/EVENT_CATALOG.md`, `docs/CONTRACTS.md`, and
  `docs/IMPLEMENTATION_STATUS.md`: exact behavior and verified limitations.

## TDD tasks

- [x] Inspect repository instructions and canonical-document, event, contract, state-machine,
  migration, RLS, idempotency, audit, outbox, worker, API, and integration-test patterns.
- [x] Write focused failing tests for all template paths, temporal boundaries, permutations,
  duplicate evidence, tenant/subject/digest/schema/timestamp failures, and money consistency.
- [x] Implement immutable projections, explicit strategies, canonical digests, and bounded errors;
  rerun targeted tests and review the focused diff.
- [x] Add explicit tests and the minimal `converted -> rejected` factual transition.
- [ ] Add migration and repository tests, then the single reversible `0010` migration with forced
  RLS, composite tenant foreign keys, immutable histories, constraints, and indexes.
- [ ] Add service/worker tests, then transactional selection, evaluation, exactly-once persistence,
  audit/outbox emission, lease fencing, failure classification, and reconciliation checks.
- [ ] Add authenticated read/replay API tests, then bounded tenant-scoped adapters and redacted
  response schemas without accepting evaluator authority from callers.
- [x] Update evaluator/event/contract/status documentation without production or billing claims.
- [ ] Run every verification-gate command, record exact evidence and limitations, self-review the
  complete diff, create focused commits, push, and open a draft PR when publication is available.

