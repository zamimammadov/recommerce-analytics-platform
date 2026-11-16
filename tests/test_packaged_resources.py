from pathlib import Path

from recommerce.db import bootstrap_sql


def test_bootstrap_resource_contains_schema_and_audit_contract():
    """Both editable installs and built wheels expose the required bootstrap DDL."""

    ddl = bootstrap_sql()

    assert "CREATE SCHEMA IF NOT EXISTS raw" in ddl
    assert "CREATE TABLE IF NOT EXISTS ops.pipeline_runs" in ddl
    assert "CREATE TABLE IF NOT EXISTS quarantine.invalid_records" in ddl
    assert ddl == (Path(__file__).parents[1] / "sql" / "bootstrap.sql").read_text()
