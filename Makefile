# Короткі команди для щоденної роботи. На Windows: `winget install GnuWin32.Make`
# або запускайте відповідні команди з рядків нижче напряму.

DC = docker compose -f docker-compose.dev.yml

# Postgres із dev-стеку (порт 5433). Тести створюють у ньому ВЛАСНІ бази
# pa_test_* / pa_mig_*, базу prime_dev з вашими даними не чіпають.
PG_URL = postgresql+asyncpg://postgres:postgres@localhost:5433/postgres

.PHONY: help up down test test-pg cov build check check-all seed logs

help:
	@echo "make up        - підняти dev-стек (тільки docker-compose.dev.yml!)"
	@echo "make down      - зупинити dev-стек"
	@echo "make test      - бекенд-тести на всіх ядрах (SQLite, без Docker, ~10 с)"
	@echo "make test-pg   - усі тести разом із PostgreSQL: міграції, дашборд (потрібен make up)"
	@echo "make cov       - як test-pg, плюс звіт покриття; нижче 95% падає, як у CI"
	@echo "make build     - перевірити збірку фронту, не чіпаючи dist/"
	@echo "make check     - test + build"
	@echo "make check-all - cov + build: те саме, що робить CI"
	@echo "make seed      - застосувати каталог із pricing.py у dev-базу"
	@echo "make logs      - логи бекенда"

up:
	$(DC) up -d

down:
	$(DC) down

test:
	cd backend && python -m pytest -n auto -q

test-pg:
	cd backend && TEST_DATABASE_URL=$(PG_URL) python -m pytest -n auto -q

cov:
	cd backend && TEST_DATABASE_URL=$(PG_URL) python -m pytest -n auto -q --cov --cov-fail-under=95 --cov-report=term-missing:skip-covered

# --outDir поза dist/: OneDrive тримає файли в dist/ і дає EPERM (див. CLAUDE.md).
build:
	cd frontend && npm ci --no-audit --no-fund && npx vite build --outDir ../.tmp-dist-check --emptyOutDir

check: test build

check-all: cov build

seed:
	$(DC) exec backend python -m app.cli seed-packages

logs:
	$(DC) logs -f backend
