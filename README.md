# OutcomeOS

OutcomeOS is a tenant-safe commerce outcome reference service. The repository includes a
FastAPI operational surface, framework-independent domain invariants, a deterministic AI
safety evaluation harness, and a React sandbox.

## Prerequisites and installation

- Python 3.11+
- Node.js 22+

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
npm install
npx playwright install chromium
```

## Run locally

```bash
# API: http://127.0.0.1:8000
uvicorn outcomeos.app:app --reload

# Web sandbox: http://127.0.0.1:5173
npm run dev
```

Operational probes are `GET /health` (process liveness), `GET /ready` (dependency
readiness), and `GET /worker-health` (background-worker/queue health).

## Exact local verification commands

Run these from the repository root. They intentionally match CI:

```bash
ruff check .
ruff format --check .
mypy
pytest --cov=outcomeos --cov-report=term-missing --cov-fail-under=90
python scripts/validate_migrations.py
detect-secrets scan --all-files --exclude-files 'package-lock.json'
npm run lint
npx tsc --noEmit
npm test
npm run test:e2e
```

The pytest suite covers isolation and permissions, webhook authentication/replay windows,
event idempotency, atomic outbox creation, attribution, validation, concurrency, versioned
contracts, immutable credits, and dispute finality. `tests/evals` exercises the assistant
against a deterministic provider—no API key, network, randomness, or paid model is used.

## CI

`.github/workflows/ci.yml` runs on every pull request and push to `main`. Its `backend` job
installs `pip install -e '.[dev]'` and runs the first six verification commands above. Its
`frontend` job runs `npm install`, the final four commands, and installs Chromium before the
Playwright journey. A failure in linting, types, migrations, secret scanning, coverage,
component tests, AI evaluations, or the browser workflow blocks the workflow.
