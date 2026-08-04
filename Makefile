.PHONY: setup install dev dev-web dev-api dev-worker lint typecheck test e2e build migrations-check migrate seed verify infra-up infra-down

setup install:
	pnpm install --frozen-lockfile
	uv sync --project apps/api --frozen

dev:
	pnpm dev

dev-web:
	pnpm --filter @outcomeos/web dev

dev-api:
	uv run --project apps/api uvicorn outcomeos_api.main:app --reload

dev-worker:
	@echo "Worker runtime is not implemented; see apps/worker/README.md" && exit 1

lint:
	pnpm lint
	uv run --project apps/api ruff check apps/api

typecheck:
	pnpm typecheck
	uv run --project apps/api mypy apps/api/src apps/api/tests

test:
	pnpm test
	uv run --project apps/api pytest apps/api/tests

e2e:
	pnpm e2e

build:
	pnpm build
	uv build --project apps/api

migrations-check:
	python3 scripts/validate_migrations.py

migrate:
	@echo "Migration execution is not implemented; validation is available via make migrations-check" && exit 1

seed:
	python3 scripts/seed.py

verify: lint typecheck test e2e build migrations-check

infra-up:
	docker compose up -d

infra-down:
	docker compose down
