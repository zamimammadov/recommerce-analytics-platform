"""Command-line interface shared by developers, CI, and Airflow."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from recommerce.analytics import export_business_metrics
from recommerce.db import database_url, initialize_database
from recommerce.generator import generate_dataset
from recommerce.ingest import ingest_directory
from recommerce.logging_config import configure_logging
from recommerce.quality import CheckStatus, Severity, results_as_dicts, run_quality_checks

app = typer.Typer(
    name="recommerce",
    help="Build and operate the synthetic recommerce analytics platform.",
    no_args_is_help=True,
)
LOGGER = logging.getLogger(__name__)


def _print_json(payload: object) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str))


@app.callback()
def main(
    json_logs: Annotated[
        bool,
        typer.Option(help="Emit structured JSON logs for a log platform."),
    ] = False,
) -> None:
    """Load local configuration and configure consistent logging."""

    load_dotenv()
    configure_logging(json_output=json_logs)


@app.command("init-db")
def init_db() -> None:
    """Create the raw, quarantine, operations, analytics, and snapshot schemas."""

    initialize_database()
    typer.echo("Database bootstrap completed.")


@app.command()
def generate(
    start_date: Annotated[
        str,
        typer.Option(help="First partition date in YYYY-MM-DD format."),
    ],
    days: Annotated[int, typer.Option(min=1, help="Number of daily partitions.")] = 7,
    output_dir: Annotated[
        Path,
        typer.Option(file_okay=False, help="Root for YYYY-MM-DD CSV partitions."),
    ] = Path("data/incoming"),
    users: Annotated[int, typer.Option(min=2, help="User rows generated per day.")] = 250,
    listings_per_day: Annotated[
        int,
        typer.Option(min=1, help="Listing rows generated per day."),
    ] = 800,
    seed: Annotated[int, typer.Option(help="Fixed seed for reproducible output.")] = 20261115,
    invalid_rate: Annotated[
        float,
        typer.Option(min=0.0, max=1.0, help="Non-zero injects deterministic bad rows."),
    ] = 0.01,
) -> None:
    """Generate deterministic, synthetic marketplace source files."""

    try:
        parsed_start_date = date.fromisoformat(start_date)
    except ValueError as error:
        raise typer.BadParameter("expected YYYY-MM-DD", param_hint="--start-date") from error
    summary = generate_dataset(
        output_dir=output_dir,
        start_date=parsed_start_date,
        days=days,
        users=users,
        listings_per_day=listings_per_day,
        seed=seed,
        invalid_rate=invalid_rate,
    )
    _print_json(summary)


@app.command()
def ingest(
    input_dir: Annotated[
        Path,
        typer.Option(exists=True, readable=True, help="CSV file or partition tree."),
    ] = Path("data/incoming"),
    expect_replay: Annotated[
        bool,
        typer.Option(
            help="Fail unless every file was already processed and no rows were inserted."
        ),
    ] = False,
) -> None:
    """Validate and atomically load every previously unseen source file."""

    result = ingest_directory(input_dir, database_url())
    _print_json(
        {
            "run_id": str(result.run_id),
            "files_seen": result.files_seen,
            "files_loaded": result.files_loaded,
            "files_skipped": result.files_skipped,
            "rows_accepted": result.rows_accepted,
            "rows_quarantined": result.rows_quarantined,
            "rows_duplicate": result.rows_duplicate,
        }
    )
    if expect_replay and (result.files_skipped != result.files_seen or result.rows_accepted != 0):
        LOGGER.error("Replay assertion failed: at least one file was not already processed")
        raise typer.Exit(code=1)


@app.command()
def quality(
    fail_on_error: Annotated[
        bool,
        typer.Option(help="Return a non-zero status when an error-severity check fails."),
    ] = False,
) -> None:
    """Run and persist cross-table data-quality checks."""

    results = run_quality_checks(database_url())
    _print_json(results_as_dicts(results))
    blocking = [
        result
        for result in results
        if result.severity is Severity.ERROR and result.status is CheckStatus.FAIL
    ]
    if fail_on_error and blocking:
        LOGGER.error("Quality gate failed", extra={"failed_checks": len(blocking)})
        raise typer.Exit(code=1)


@app.command("export-metrics")
def export_metrics(
    output_dir: Annotated[
        Path,
        typer.Option(file_okay=False, help="Directory for CSV, JSON, and Markdown outputs."),
    ] = Path("data/processed"),
) -> None:
    """Export dbt marts and a pandas-built executive summary."""

    paths = export_business_metrics(database_url(), output_dir)
    _print_json({name: str(path) for name, path in paths.items()})


if __name__ == "__main__":
    app()
