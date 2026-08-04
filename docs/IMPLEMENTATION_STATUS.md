# Implementation status

Last reviewed: 2026-08-04.

Allowed status vocabulary in this document is limited to: `complete`, `partial`, `mock`, `blocked`, and `not started`. `complete` means implemented and verified within the stated scope; it does not imply production approval.

| Capability | Status | Evidence / limitation |
| --- | --- | --- |
| Repository layout and contributor guidance | complete | Root structure and guidance exist |
| Next.js strict TypeScript skeleton | complete | Strict compiler options, linting, and landing page exist |
| FastAPI uv-managed skeleton | complete | Package, health route, strict checks, and tests exist |
| Local PostgreSQL with pgvector | complete | Compose service and extension initialization exist; API use is not started |
| Local Redis | complete | Compose service exists; API use is not started |
| Local S3-compatible storage | complete | MinIO Compose service exists; application use is not started |
| CI checks | complete | Web and API check jobs exist |
| Demo authentication | partial | Development/demo OTP challenge storage exists; code exposure fails closed outside those environments |
| Mock integration framework | mock | Deterministic AI shop assistant and validated tools exist; no provider operations |
| Production authentication | not started | OIDC provider and sessions are absent |
| Tenant authorization | partial | PostgreSQL row-level policies and tenant-scoped queries exist; production identity integration is absent |
| Outcome and initiative workflows | partial | Deterministic commerce outcome and fixed-fee billing journey exists |
| Database schema and migrations | partial | Initial tenant commerce/outcome PostgreSQL migration and demo SQLite schema exist |
| Evidence upload pipeline | not started | Storage is local infrastructure only |
| Background workers | partial | Transactional outbox is populated; worker delivery runtime is absent |
| Observability and audit logging | not started | No telemetry or audit store exists |
| External provider integrations | not started | Candidates are plans only; none are operational |
| Production deployment | blocked | Requires secure core, operations, and launch gates |
