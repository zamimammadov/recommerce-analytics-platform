"""Database invariants; opt in with TEST_DATABASE_URL to a local test server."""

from __future__ import annotations

import csv
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from recommerce.db import bootstrap
from recommerce.ingest import REQUIRED_COLUMNS, ingest_path

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def test_database():
    admin_url = os.getenv("TEST_DATABASE_URL")
    if not admin_url:
        pytest.skip("TEST_DATABASE_URL is not set")
    name = f"recommerce_test_{uuid.uuid4().hex}"
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        url = make_conninfo(admin_url, dbname=name)
        try:
            with psycopg.connect(url) as connection:
                bootstrap(connection)
            yield url
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def _write_users(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=REQUIRED_COLUMNS["users"])
        writer.writeheader()
        writer.writerows(rows)


def _user(identifier: str) -> dict[str, str]:
    return {
        "user_id": identifier,
        "country_code": "LT",
        "signup_at": "2026-10-01T10:00:00+00:00",
        "acquisition_channel": "organic",
        "is_business": "false",
        "updated_at": "2026-10-01T11:00:00+00:00",
    }


def test_replay_duplicate_and_conflicting_version_accounting(test_database, tmp_path):
    path = tmp_path / "users.csv"
    user = _user(f"test_{uuid.uuid4().hex}")
    _write_users(path, [user])
    with psycopg.connect(test_database) as connection:
        first = ingest_path(connection, path)
        replay = ingest_path(connection, path)
        changed = {**user, "country_code": "DE"}
        _write_users(path, [user, user, changed, {**user, "country_code": "INVALID"}])
        correction = ingest_path(connection, path)
        assert first.rows_accepted == 1
        assert replay.files_skipped == 1
        assert replay.rows_accepted == 0
        assert correction.rows_accepted == 0
        assert correction.rows_duplicate == 2
        assert correction.rows_quarantined == 2
        counts = connection.execute(
            "SELECT row_count, accepted_count, duplicate_count, quarantined_count "
            "FROM ops.processed_files WHERE run_id = %s",
            (correction.run_id,),
        ).fetchone()
        assert counts == (4, 0, 2, 2)


def test_failed_file_rolls_back_and_records_failed_run(test_database, tmp_path):
    path = tmp_path / "users.csv"
    prefix = f"rollback_{uuid.uuid4().hex}"
    _write_users(path, [_user(f"{prefix}_{index}") for index in range(200)])
    with path.open("ab") as output:
        output.write(b"\xff\xfe\n")
    with psycopg.connect(test_database) as connection:
        with pytest.raises(UnicodeDecodeError):
            ingest_path(connection, path)
        assert (
            connection.execute(
                "SELECT count(*) FROM raw.users WHERE user_id LIKE %s", (f"{prefix}%",)
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT status FROM ops.pipeline_runs WHERE source_path = %s", (str(path),)
            ).fetchone()[0]
            == "failed"
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM ops.processed_files WHERE source_path = %s", (str(path),)
            ).fetchone()[0]
            == 0
        )


def test_overlapping_runs_load_identical_file_once(test_database, tmp_path):
    path = tmp_path / "users.csv"
    _write_users(path, [_user(f"concurrent_{uuid.uuid4().hex}")])

    def run():
        with psycopg.connect(test_database) as connection:
            return ingest_path(connection, path)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _: run(), range(2)))
    assert first.rows_accepted + second.rows_accepted == 1
    assert first.files_skipped + second.files_skipped == 1
