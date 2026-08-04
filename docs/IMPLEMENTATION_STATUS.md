# Implementation status

Last reviewed: 2026-08-04. This ledger is the authority for capability claims, not a roadmap or architecture document.

## Status vocabulary

- **implemented:** code exists and automated local verification covers the stated scope; this does not mean production-approved.
- **mocked:** synthetic/local behavior only, clearly labeled, with no verified provider operation.
- **partial:** some stated behavior exists, but a material path or verification is absent.
- **blocked:** work cannot responsibly proceed until the listed dependency or decision exists.
- **sandbox-tested:** a real provider's non-production environment has been exercised and evidence retained; it is not live proof.
- **live-tested:** a controlled real-environment operation and reconciliation have been verified. This label does not by itself confer production readiness.
- **not started:** no executable capability exists. Documentation and reserved directories do not count.

## Capability ledger

| Capability | Status | Verification and limitations |
| --- | --- | --- |
| Repository boundaries and contributor rules | implemented | Root guidance and expected directories exist |
| Reproducible JavaScript dependencies | blocked | A genuine pnpm lockfile must be generated from the merged dependency manifest; placeholder lockfiles are not acceptable |
| Reproducible Python dependencies | blocked | A genuine uv lockfile must be generated from the merged API manifest; placeholder lockfiles are not acceptable |
| Root quality command surface | implemented | Setup, dev, lint, typecheck, tests, E2E, build, migration validation, seed, and aggregate targets exist; some targets honestly no-op/fail where capability is absent |
| Next.js strict skeleton | implemented | Landing page, strict compiler configuration, lint and build exist |
| FastAPI strict skeleton | implemented | Health route, configuration validation, tests, lint and strict mypy exist |
| Shared contract package | partial | Strict package and foundational types exist; no versioned API/domain schemas yet |
| Worker application | not started | Directory documents the boundary; there is no worker runtime |
| Local PostgreSQL/Redis/S3-compatible services | implemented | Compose definitions exist; application persistence/use is absent |
| Migration framework | partial | Ordered SQL directory and structural validation exist; no domain schema or database apply runner |
| Seed command | mocked | Safe command reports that no persistent seed is applied |
| Demo authentication | mocked | Flags and production guards exist; there is no functional login/session flow |
| Mock integration framework | mocked | Flag and production guards only; there are no provider operations |
| Tenant model and authorization | not started | No domain/persistence layer; isolation is documented but unverified |
| Persistent customer/order/invoice journey | not started | UI/API/storage behavior does not exist |
| Financial calculation and state machine | not started | Invariants are documented only |
| Payment/credit allocation | not started | No model or provider behavior exists |
| Audit log and idempotency | not started | Required design is documented only |
| E2E product coverage | not started | A placeholder test is not product coverage; the persistent journey has no executable E2E test |
| CI quality/build/migration/secret gates | partial | CI behavior is maintained on `main`; frozen dependency gates still require genuine generated lockfiles |
| Production OIDC | blocked | Provider/security decisions and Phase 1 implementation are absent |
| External payment/tax/accounting integrations | blocked | No provider selected or connector implemented |
| Any provider sandbox test | not started | No sandbox evidence has been produced |
| Any provider live test | not started | No live operation or reconciliation has been performed |
| Production deployment | blocked | Secure core, complete journey, operations evidence, and launch gates are absent |

No external integration is currently implemented, sandbox-tested, live-tested, or production-ready.
