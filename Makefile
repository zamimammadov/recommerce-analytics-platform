SHELL := /bin/sh

DEMO_START_DATE ?= 2026-10-01
DEMO_NEXT_DATE ?= 2026-10-02
DEMO_DAYS ?= 14
DEMO_USERS ?= 250
DEMO_LISTINGS ?= 800
COMPOSE := docker compose
PYTHON ?= .venv/bin/python

.PHONY: help build up down reset init generate ingest dbt-build quality export replay demo demo-local test lint format airflow dashboard

help: ## Show the available commands.
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target>\n\n"} /^[a-zA-Z_-]+:.*## / {printf "  %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build the application and dbt image.
	$(COMPOSE) build app dbt

up: ## Start PostgreSQL and wait until it is healthy.
	$(COMPOSE) up -d --wait postgres

down: ## Stop local services without deleting data.
	$(COMPOSE) --profile dashboard --profile orchestration down

reset: ## Delete local containers and database volumes (destructive).
	$(COMPOSE) --profile dashboard --profile orchestration down --volumes --remove-orphans

init: up ## Create raw, quarantine, and operations schemas.
	$(COMPOSE) run --rm app init-db

generate: ## Generate deterministic daily source files.
	$(COMPOSE) run --rm app generate --start-date $(DEMO_START_DATE) --days $(DEMO_DAYS) --users $(DEMO_USERS) --listings-per-day $(DEMO_LISTINGS) --output-dir data/incoming

ingest: ## Load all unprocessed files; identical checksums are skipped.
	$(COMPOSE) run --rm app ingest --input-dir data/incoming

dbt-build: ## Create snapshots, dimensions, facts, marts, and run dbt tests.
	$(COMPOSE) run --rm dbt deps --profiles-dir /app/dbt
	$(COMPOSE) run --rm dbt build --profiles-dir /app/dbt

quality: ## Execute and persist cross-table data-quality checks.
	$(COMPOSE) run --rm app quality

export: ## Export business marts and the pandas executive summary.
	$(COMPOSE) run --rm app export-metrics --output-dir data/processed

replay: ## Replay the latest demo partition to prove checksum idempotency.
	$(COMPOSE) run --rm app ingest --input-dir data/incoming/$(DEMO_NEXT_DATE) --expect-replay

demo-local: up ## Run the complete demo using local Python and Docker PostgreSQL.
	$(PYTHON) scripts/demo_local.py --start-date $(DEMO_START_DATE) --users $(DEMO_USERS) --listings $(DEMO_LISTINGS)

demo: init ## Run two daily batches end-to-end and materialise SCD2 history.
	$(COMPOSE) run --rm app generate --start-date $(DEMO_START_DATE) --days 1 --users $(DEMO_USERS) --listings-per-day $(DEMO_LISTINGS) --output-dir data/incoming
	$(COMPOSE) run --rm app ingest --input-dir data/incoming/$(DEMO_START_DATE)
	$(COMPOSE) run --rm dbt build --profiles-dir /app/dbt
	$(COMPOSE) run --rm app generate --start-date $(DEMO_NEXT_DATE) --days 1 --users $(DEMO_USERS) --listings-per-day $(DEMO_LISTINGS) --output-dir data/incoming
	$(COMPOSE) run --rm app ingest --input-dir data/incoming/$(DEMO_NEXT_DATE)
	$(COMPOSE) run --rm dbt build --profiles-dir /app/dbt
	$(COMPOSE) run --rm app quality --fail-on-error
	$(COMPOSE) run --rm app export-metrics --output-dir data/processed
	$(MAKE) replay
	@echo "Demo complete: daily updates created SCD2 history and replay inserted zero rows."

test: ## Run unit tests locally in the application image.
	$(COMPOSE) --profile dev run --rm --no-deps dev pytest

lint: ## Check Python style and formatting without changing files.
	$(COMPOSE) --profile dev run --rm --no-deps dev ruff check .
	$(COMPOSE) --profile dev run --rm --no-deps dev ruff format --check .

format: ## Apply Python lint fixes and formatting.
	$(COMPOSE) --profile dev run --rm --no-deps dev ruff check --fix .
	$(COMPOSE) --profile dev run --rm --no-deps dev ruff format .

airflow: ## Start optional Airflow UI and scheduler at http://localhost:8080.
	$(COMPOSE) --profile orchestration up -d --build airflow-webserver airflow-scheduler

dashboard: ## Start optional Streamlit dashboard at http://localhost:8501.
	$(COMPOSE) --profile dashboard up -d --build dashboard
