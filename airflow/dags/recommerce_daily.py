"""Daily, backfillable orchestration for the recommerce analytics platform."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_ROOT = "/opt/airflow/project"
PIPELINE_PYTHON = "/opt/recommerce-venv/bin/python"
DBT_BINARY = "/opt/recommerce-venv/bin/dbt"
COMMON_ENV = {
    "PYTHONPATH": f"{PROJECT_ROOT}/src",
    "DBT_PROFILES_DIR": f"{PROJECT_ROOT}/dbt",
}

default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(minutes=30),
}

with DAG(
    dag_id="recommerce_daily",
    description="Generate, ingest, transform, and validate one marketplace partition",
    default_args=default_args,
    start_date=datetime(2026, 10, 1),
    schedule="0 6 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["portfolio", "marketplace", "batch"],
) as dag:
    init_database = BashOperator(
        task_id="init_database",
        bash_command=f"{PIPELINE_PYTHON} -m recommerce.cli init-db",
        cwd=PROJECT_ROOT,
        env=COMMON_ENV,
        append_env=True,
    )

    generate_partition = BashOperator(
        task_id="generate_partition",
        bash_command=(
            f"{PIPELINE_PYTHON} -m recommerce.cli generate "
            "--start-date '{{ ds }}' --days 1 --output-dir data/incoming"
        ),
        cwd=PROJECT_ROOT,
        env=COMMON_ENV,
        append_env=True,
    )

    ingest_partition = BashOperator(
        task_id="ingest_partition",
        bash_command=(
            f"{PIPELINE_PYTHON} -m recommerce.cli ingest " "--input-dir 'data/incoming/{{ ds }}'"
        ),
        cwd=PROJECT_ROOT,
        env=COMMON_ENV,
        append_env=True,
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"{DBT_BINARY} build --profiles-dir .",
        cwd=f"{PROJECT_ROOT}/dbt",
        env=COMMON_ENV,
        append_env=True,
    )

    quality_gate = BashOperator(
        task_id="quality_gate",
        bash_command=f"{PIPELINE_PYTHON} -m recommerce.cli quality --fail-on-error",
        cwd=PROJECT_ROOT,
        env=COMMON_ENV,
        append_env=True,
    )

    init_database >> generate_partition >> ingest_partition >> dbt_build >> quality_gate
