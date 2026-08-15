# Milestone 3 Part 1 completion plan

- [x] Inspect authentication, tenant transactions, RLS, migration, audit, and router patterns.
- [x] Add `20260815_0009` for command idempotency, a domain outbox, party authority, and source-overlap enforcement.
- [x] Add tenant-scoped contract/rule persistence in `outcomeos_api/contracts/repositories.py`.
- [x] Add transactional lifecycle commands in `outcomeos_api/contracts/service.py`.
- [x] Add authenticated management schemas/routes in `outcomeos_api/contracts/api.py` and application assembly.
- [ ] Add the complete unit/API and PostgreSQL integration matrix in `apps/api/tests/`.
- [x] Document API, authorization, atomicity, concurrency, and remaining non-goals.
- [ ] Restore the 90% Python coverage gate and obtain protected `api` and `web` CI evidence.
