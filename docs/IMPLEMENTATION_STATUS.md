# Implementation status

Last reviewed: 2026-08-04.

Allowed status vocabulary in this document is limited to: `complete`, `partial`, `mock`, `blocked`, and `not started`. `complete` means implemented and verified within the stated scope; it does not imply production approval.

| Capability | Status | Evidence / limitation |
| --- | --- | --- |
| Repository layout and contributor guidance | complete | Root structure and guidance exist |
| Next.js strict TypeScript skeleton | complete | Strict compiler options, linting, and landing page exist |
| FastAPI uv-managed skeleton | complete | Package, liveness/readiness routes, strict checks, and tests exist |
| Local PostgreSQL with pgvector | complete | Parameterized Compose service, readiness probe, and extension initialization exist |
| Local Redis | not started | A queue/cache will be selected when its concrete semantics are known |
| Local S3-compatible storage | not started | Evidence storage is not part of this foundation |
| Local quality gates | complete | `make verify` covers lint, types, tests, and production builds |
| Demo authentication | mock | No real identity validation; production configuration rejects demo mode |
| Mock integration framework | mock | Configuration flag and production guard only; no provider operations |
| Production authentication | not started | OIDC provider and sessions are absent |
| Tenant authorization | not started | Domain and persistence layers are absent |
| Outcome and initiative workflows | not started | Product behavior is documented only |
| Database schema and migrations | partial | Alembic tooling and the foundational outcomes table exist |
| Evidence upload pipeline | not started | Storage is local infrastructure only |
| Background workers | partial | A separate runnable shell checks PostgreSQL then idles; queue consumption is absent |
| Observability and audit logging | not started | No telemetry or audit store exists |
| External provider integrations | not started | Candidates are plans only; none are operational |
| Production deployment | blocked | Requires secure core, operations, and launch gates |
