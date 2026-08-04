# OutcomeOS contributor guide

These instructions apply to the entire repository.

- Keep the monorepo boundaries clear: deployable services live in `apps/`, shared code in `packages/`, deployment assets in `infra/`, and developer automation in `scripts/`.
- Never describe a mock, demo, or planned integration as production-ready.
- Demo authentication and mock integrations must fail closed when `APP_ENV=production`.
- Add tests for behavior changes and keep TypeScript and Python checks strict.
- Do not commit secrets. Document new configuration in `.env.example`.
