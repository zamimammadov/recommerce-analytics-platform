# Recommerce Analytics Platform

Daily listings, orders and browsing events from a synthetic second-hand marketplace feed a PostgreSQL warehouse. Operations can trace a reported sale back to a delivery, inspect rejected rows and replay a file without counting its sales twice.

[Five-minute demo](docs/demo.md) · [Sample results](examples/demo-results/executive_summary.md) · [CI runs](https://github.com/zamimammadov/recommerce-analytics-platform/actions/workflows/ci.yml)

## Follow a delivery

1. Python generates one dated delivery containing four CSVs and validates each file as it streams into PostgreSQL. Valid records enter the raw tables. Invalid records retain their source row and reason in quarantine.
2. A processed-file registry skips identical deliveries. A failed file rolls back. Run and file audit tables record what was loaded, skipped or rejected.
3. dbt selects current records, builds facts and dimensions and aggregates daily marketplace KPIs. Separate snapshots preserve user and listing versions observed on successive runs.
4. Six cross-table checks evaluate the results. Streamlit reads the reporting marts, and pandas exports the same marts and a period summary.

The ingestion step is incremental. The downstream dbt tables rebuild in full and use the latest known dimensions. A late source update can therefore revise historical totals. [Metric definitions](docs/business-case.md) cover eligible order statuses, shipping, and the denominator for each rate.

## Run a two-day demo

Verified route on Linux or macOS, with Python 3.11+ and Docker Compose for PostgreSQL. Use a fresh demo database for the sample counts.

```sh
cp .env.example .env
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev,warehouse]'
docker compose up -d --wait postgres
.venv/bin/python scripts/demo_local.py --users 100 --listings 200
```

Keep the localhost database settings in `.env` consistent if you change the password or port. On Windows, use `Copy-Item .env.example .env` and `.venv\Scripts\python.exe` for the virtual environment's Python. The same script accepts an existing PostgreSQL instance. For the Compose application services and optional Airflow scheduler, see the [runbook](docs/runbook.md) and [verification record](docs/verification.md).

## Explore the results

The small two-day example produced 60 orders. Of these, 51 contributed €12,639.97 to gross merchandise value and 31 reached completed status. The difference comes from the definition of GMV, which includes paid and shipped orders as well as completed ones. Business dates can precede the delivery date.

- [Business SQL](analysis/business_questions.sql) covers weekly supply, category engagement, time to sale and GMV reconciliation.
- [Operational SQL](analysis/inspect_pipeline.sql) shows rejected rows, file replay and historical listing prices.
- [Data model](docs/data-model.md), [architecture](docs/architecture.md) and [design decisions](docs/tradeoffs.md) describe the warehouse.
- [Verification](docs/verification.md) lists local and CI checks and their runtime coverage.

MIT licensed. All source data is synthetic. AI tools assisted with implementation, review and documentation.
