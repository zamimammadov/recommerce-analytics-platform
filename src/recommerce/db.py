"""Database configuration and bootstrap helpers."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy.engine import URL, make_url

if TYPE_CHECKING:
    from psycopg import Connection


def database_url() -> str:
    """Return the configured URL without embedding a password fallback in code."""

    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and provide local credentials."
        )
    return url


def sqlalchemy_url(url: str) -> URL:
    """Select the installed psycopg 3 driver without altering credentials."""

    parsed = make_url(url)
    if parsed.drivername in {"postgres", "postgresql"}:
        return parsed.set(drivername="postgresql+psycopg")
    return parsed


@contextmanager
def connect(url: str | None = None) -> Iterator[Connection[Any]]:
    """Yield a psycopg connection and always close it."""

    import psycopg

    connection = psycopg.connect(url or database_url())
    try:
        yield connection
    finally:
        connection.close()


def bootstrap(connection: Connection[Any], sql_path: Path | None = None) -> None:
    """Create the schemas and operational/raw tables idempotently."""

    sql = sql_path.read_text(encoding="utf-8") if sql_path is not None else bootstrap_sql()
    with connection.cursor() as cursor:
        cursor.execute(sql)
    connection.commit()


def bootstrap_sql() -> str:
    """Read packaged DDL, with a source-tree fallback for editable installs."""

    resource = files("recommerce").joinpath("resources", "bootstrap.sql")
    if resource.is_file():
        return resource.read_text(encoding="utf-8")
    source_path = Path(__file__).resolve().parents[2] / "sql" / "bootstrap.sql"
    return source_path.read_text(encoding="utf-8")


def initialize_database(url: str | None = None) -> None:
    """Open a connection and apply the bootstrap DDL."""

    with connect(url) as connection:
        bootstrap(connection)
