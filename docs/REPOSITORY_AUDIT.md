# Repository audit

Reviewed on 2026-08-04 before implementation.

## Confirmed findings

- Canonical packaged backend code existed under `apps/api/src/outcomeos_api/`.
- A duplicate in-memory prototype existed under `apps/api/app/domains/` and a separate root test suite existed under `tests/`.
- The Next.js app lived under `apps/web/app/`, while a separate static prototype (`apps/web/index.html`, `apps/web/app.js`, `apps/web/styles.css`) duplicated dashboard UI ideas.
- SQLAlchemy models and Alembic existed, but older SQL migration locations also existed (`apps/api/migrations/001_initial.sql`, `infra/migrations/`).
- `/ready` and `/worker-health` previously reported success without real dependency or worker checks.
- Root scripts lacked real `migrate` and `dev-worker` behavior.
- Documentation emphasized a generic order-to-invoice journey rather than the requested verified-performance-marketing MVP.

## Consolidation decisions

- `apps/api/src/outcomeos_api/` is the only backend package.
- `apps/web/app/` is the only frontend implementation.
- `apps/api/migrations/versions/` is the only migration history.
- Sandbox behavior is deterministic and local-only; no real provider calls are made.
