"""Run a two-day demonstration in an installed local Python environment.

Start PostgreSQL first. This path also works when the host has insufficient
storage for additional Docker application containers.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter

import psycopg
from dotenv import load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2026, 10, 1))
    parser.add_argument("--users", type=int, default=250)
    parser.add_argument("--listings", type=int, default=800)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    os.environ["DBT_PROFILES_DIR"] = str(root / "dbt")
    dbt = Path(sys.executable).parent / ("dbt.exe" if os.name == "nt" else "dbt")
    dbt_command = str(dbt) if dbt.exists() else shutil.which("dbt")
    if not dbt_command:
        parser.error('dbt is missing; install the project with ".[dev,warehouse]"')
    if not os.getenv("DATABASE_URL"):
        parser.error("DATABASE_URL is missing; configure .env first")
    start = perf_counter()

    def cli(*arguments: str, capture: bool = False):
        command = [sys.executable, "-m", "recommerce", *arguments]
        return subprocess.run(command, cwd=root, check=True, text=True, capture_output=capture)

    cli("init-db")
    for offset in range(2):
        day = (args.start_date + timedelta(days=offset)).isoformat()
        cli(
            "generate",
            "--start-date",
            day,
            "--days",
            "1",
            "--users",
            str(args.users),
            "--listings-per-day",
            str(args.listings),
            "--output-dir",
            "data/incoming",
        )
        cli("ingest", "--input-dir", f"data/incoming/{day}")
        subprocess.run(
            [dbt_command, "--quiet", "build", "--project-dir", "dbt", "--profiles-dir", "dbt"],
            cwd=root,
            check=True,
        )
    cli("quality", "--fail-on-error")
    cli("export-metrics", "--output-dir", "data/processed")
    replay_day = (args.start_date + timedelta(days=1)).isoformat()
    replay = json.loads(
        cli("ingest", "--input-dir", f"data/incoming/{replay_day}", capture=True).stdout
    )
    assert replay["files_skipped"] == 4 and replay["rows_accepted"] == 0
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        historical = connection.execute(
            "SELECT count(*) FROM snapshots.listings_snapshot WHERE dbt_valid_to IS NOT NULL"
        ).fetchone()[0]
        assert historical > 0, "Demo must process each day's snapshot separately"
        quarantine = connection.execute(
            "SELECT count(*) FROM quarantine.invalid_records"
        ).fetchone()[0]
    report = {
        "historical_listing_versions": historical,
        "quarantined_records": quarantine,
        "replay_files_skipped": replay["files_skipped"],
        "replay_rows_inserted": replay["rows_accepted"],
        "elapsed_seconds": round(perf_counter() - start, 2),
    }
    output = root / "data/processed/demo_validation.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
