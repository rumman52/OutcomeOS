# ADR 0001: Global modular monolith

**Status:** Accepted (2026-08-08)

OutcomeOS will retain a Next.js boundary, FastAPI application boundary and PostgreSQL-backed modular monolith. Framework-independent domain modules own outcome, attribution and financial rules; HTTP routers and provider adapters translate only. PostgreSQL is the production source of truth and transactional outbox. Tenant identity is mandatory on every owned record and repository operation. External providers implement focused protocols and report `not_configured` until authenticated behavior is verified. This minimizes distributed consistency risk while preserving seams for independently scalable workers and adapters.
