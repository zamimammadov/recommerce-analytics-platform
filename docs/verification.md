# Verification record

Local checks were verified on **16 November 2026** in the development workspace.
GitHub Actions also passed on **17 November 2026** after publication. Results
below describe the commands actually executed, and distinguish those results
from configuration that has only been checked statically.

## What was tested

| Area | Result and evidence |
|---|---|
| Python tests | All **40** tests passed, including three tests against a live PostgreSQL server. |
| Live ingestion behaviour | Verified identical-file replay, changed-file duplicate/conflict accounting, file transaction rollback after invalid UTF-8, and concurrent processing of identical input. |
| Local end-to-end run | `scripts/demo_local.py --users 100 --listings 200` completed two daily batches against PostgreSQL 16 and dbt Core 1.9.1 / dbt Postgres 1.9.0. |
| Accepted raw history | **3,060** source versions stored across the two days. |
| Quarantine | **6** intentionally invalid records retained with validation reasons. |
| SCD2 | **15** historical listing versions preserved by processing a snapshot after each daily batch. |
| Idempotent replay | Second-day replay skipped all **4** files and inserted **0** rows. |
| Cross-table quality | All **6/6** persisted DQ checks passed. |
| dbt build | All **107** selected nodes passed, including **93 data tests**. The other nodes are models and snapshots, not additional tests. |
| Measured local duration | **33.06 seconds** for the two-day local demo on this host. This is a single measured run, not an SLA or a cross-machine benchmark. |
| Docker image builds | App and dbt build targets completed at approximately **343 MB** and **448 MB** before the final source fixes. Final application-container execution remains unverified. Sizes depend on platform/package resolution. |
| Airflow configuration | DAG compilation and static configuration checks completed. |
| Dashboard | Streamlit AppTest rendered four KPI cards from the live marts with no application errors. |
| Package | Built and installed the wheel into an isolated temporary directory; verified that its packaged bootstrap SQL includes the latest migrations. |
| GitHub Actions | Both `code-quality` and `pipeline-integration` passed on source commit `5da3a4337de112936fd6e1d4c7fa1feecbcb9621`. The integration job exercised daily ingestion, live database invariants, two dbt builds, SCD2 history, quality checks, replay and metric export. See the [successful run](https://github.com/zamimammadov/recommerce-analytics-platform/actions/runs/43968369710). |

Generated `data/processed/demo_validation.json` records the latest demo's
history, quarantine, replay and timing results. Generated files remain outside
source control; rerunning the demo produces fresh evidence.

## What remains unverified or undeployed

| Area | Limitation |
|---|---|
| Full `make demo` container run | The host uses Docker VFS storage and has a 7.9 GB filesystem limit. Application-container creation exhausted host space, so the complete Compose app/dbt execution path was not demonstrated here. The same Python pipeline and dbt commands passed using the local fallback below. |
| Airflow runtime | The full Airflow scheduler/webserver stack and a live DAG run were not exercised. Do not present static checks as an operational Airflow deployment. |
| Cloud deployment | No cloud environment was deployed; there is no claim of cloud CI/CD, HA, production traffic, or operational ownership. |

## Reproduce the verified local fallback

This path runs Python/dbt locally and uses Docker only for PostgreSQL. It is
useful when the machine cannot store additional application containers.

From the repository root:

```bash
cp .env.example .env
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev,warehouse]'
docker compose up -d --wait postgres
.venv/bin/python scripts/demo_local.py --users 100 --listings 200
```

Before running, edit `.env` so `POSTGRES_HOST=localhost` and `DATABASE_URL`
points to the same local database/user/password configured for Compose. For
example, if the local password remains the sample `change-me-locally`, use:

```dotenv
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=recommerce
POSTGRES_USER=recommerce
POSTGRES_PASSWORD=change-me-locally
DATABASE_URL=postgresql://recommerce:change-me-locally@localhost:5432/recommerce
```

The script sets `DBT_PROFILES_DIR` to this checkout automatically. It processes
each day and its snapshot separately, runs the DQ gate, exports metrics and
asserts replay/history behaviour. The stated row/history counts assume a clean
demo database; accumulated deliveries can increase totals.

On Windows, replace `.venv/bin/python` with `.venv\Scripts\python.exe`.
The default container-backed route remains `make demo`; see the
[runbook](runbook.md) for recovery and corporate CA instructions.
