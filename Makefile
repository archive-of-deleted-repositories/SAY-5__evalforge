.PHONY: help install lint typecheck test test-unit test-integration test-web bench bench-regress e2e build clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-20s %s\n", $$1, $$2}'

install: ## install api + web deps
	cd apps/api && pip install -e ".[dev]"
	cd apps/web && npm ci

lint: ## ruff + black
	cd apps/api && ruff check src tests && black --check src tests

typecheck: ## mypy + tsc
	cd apps/api && mypy src
	cd apps/web && npm run typecheck

test-unit: ## backend unit tests
	cd apps/api && pytest tests/unit -q

test-integration: ## backend integration tests (testcontainers)
	cd apps/api && pytest tests/integration -q

test-web: ## frontend tests
	cd apps/web && npm test

test: test-unit test-integration test-web ## all tests

bench: ## inline latency bench (full)
	cd apps/api && python -m evalforge.bench

bench-smoke: ## inline latency bench (CI smoke)
	cd apps/api && python -m evalforge.bench --smoke

bench-regress: ## bench regress gate at 30 percent drift
	cd apps/api && python -m evalforge.bench --smoke --regress

e2e: ## Playwright e2e
	cd apps/web && npm run e2e

build: ## docker images
	docker compose build

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
