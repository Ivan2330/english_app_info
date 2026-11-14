# Короткі команди для щоденної роботи. На Windows: `winget install GnuWin32.Make`
# або запускайте відповідні команди з рядків нижче напряму.

DC = docker compose -f docker-compose.dev.yml

.PHONY: help up down test build check seed logs

help:
	@echo "make up     - підняти dev-стек (тільки docker-compose.dev.yml!)"
	@echo "make down   - зупинити dev-стек"
	@echo "make test   - бекенд-тести (SQLite, без секретів)"
	@echo "make build  - перевірити збірку фронту, не чіпаючи dist/"
	@echo "make check  - test + build: те саме, що робить CI"
	@echo "make seed   - застосувати каталог із pricing.py у dev-базу"
	@echo "make logs   - логи бекенда"

up:
	$(DC) up -d

down:
	$(DC) down

test:
	cd backend && python -W ignore -m unittest discover -s tests

# --outDir поза dist/: OneDrive тримає файли в dist/ і дає EPERM (див. CLAUDE.md).
build:
	cd frontend && npm ci --no-audit --no-fund && npx vite build --outDir ../.tmp-dist-check --emptyOutDir

check: test build

seed:
	$(DC) exec backend python -m app.cli seed-packages

logs:
	$(DC) logs -f backend
