# Architecture

## Concrete stack

OutcomeOS is a monorepo with three independently runnable processes:

| Component | Technology | Responsibility |
| --- | --- | --- |
| Web | Next.js 15, React 19, TypeScript | Server-rendered UI and browser interactions |
| API | Python 3.12, FastAPI, Uvicorn, psycopg | HTTP contracts, authorization, domain logic, and PostgreSQL access |
| Worker | Python 3.12, psycopg | Separate background-process boundary for asynchronous work |
| Database | PostgreSQL 17 with pgvector | Durable system of record and future vector search |
| Migrations | Alembic and SQLAlchemy | Ordered, reversible database schema changes |

The worker is intentionally only a runnable shell today: it proves database connectivity and then
idles. It is not a production-ready queue consumer. A queue will be selected when actual background
job semantics are defined rather than hidden behind a mock.

## Runtime and repository boundaries

```text
browser -> apps/web (Next.js) -> apps/api (FastAPI) -> PostgreSQL
                                      ^                    ^
                                      |                    |
                              HTTP health probes    apps/worker
```

| Path | Responsibility |
| --- | --- |
| `apps/web` | Deployable web process |
| `apps/api` | Deployable HTTP API and versioned migrations |
| `apps/worker` | Deployable background worker process |
| `packages` | Shared schemas, clients, and UI code when introduced |
| `infra` | Local infrastructure and deployment assets |
| `scripts` | Developer and operational automation |

Code may depend inward on shared packages, but deployable applications do not import one another.
External providers must be accessed through API-side adapters, never directly from the browser.

## Operations and data

`GET /health` is a liveness check and does no network I/O. `GET /ready` executes `SELECT 1` against
PostgreSQL and returns HTTP 503 if the required dependency is unavailable. Local PostgreSQL runs in
Docker Compose; its database, user, and password are supplied from the ignored `.env`, not embedded
in the Compose definition. Alembic migrations are the only supported schema-change mechanism.

Configuration is validated at process startup. Demo authentication and mock integrations are
rejected when `APP_ENV=production`. Secrets belong in runtime environment variables or a deployment
secret store and must never be committed.

## Deployment shape

Web, API, and worker are separately built and deployed processes connected to managed PostgreSQL.
`docker-compose.yml` is strictly local development infrastructure, not a production deployment.
The initial outcomes table is foundational only; authentication, authorization, tenant isolation,
queue processing, and product workflows remain to be implemented.
