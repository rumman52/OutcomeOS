# Architecture

## Context

The browser uses a Next.js application in `apps/web`. It calls the FastAPI service in `apps/api`, which will own business rules and access to PostgreSQL, Redis, and object storage. External providers must be accessed only through backend adapters.

## Repository boundaries

| Path | Responsibility |
| --- | --- |
| `apps/web` | Server-rendered UI and browser interactions |
| `apps/api` | HTTP API, authorization, domain logic, background job entry points |
| `packages` | Future shared schemas, clients, and UI components |
| `infra` | Local initialization and future deployment assets |
| `scripts` | Repeatable developer and operations automation |
| `docs` | Product, architecture, security, integration, and delivery records |

## Local dependencies

- PostgreSQL 17 with pgvector is the future system of record and vector store.
- Redis is reserved for caching, rate limits, and job coordination.
- MinIO provides a local S3-compatible API for future evidence attachments.

The running API currently exposes only a health endpoint and does not connect to these services.

## Design rules

- Keep domain logic independent of HTTP and provider SDKs.
- Validate configuration at startup and fail closed.
- Make tenant identity explicit in storage and authorization interfaces.
- Apply schema changes through versioned migrations (not yet implemented).
- Use transactional outbox/event patterns for reliable asynchronous work when added.
- Version API contracts and share generated types rather than duplicating models.

## Deployment shape

The intended production shape separates web, API, worker, managed PostgreSQL, managed Redis, and private object storage. `docker-compose.yml` is strictly a local-development topology and is not a production deployment definition.
