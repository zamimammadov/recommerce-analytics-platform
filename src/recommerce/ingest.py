"""Validated, idempotent CSV ingestion for marketplace batch files."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from psycopg import Connection

LOGGER = logging.getLogger(__name__)

ALLOWED_LISTING_STATUSES = {"active", "reserved", "sold", "removed"}
ALLOWED_EVENT_TYPES = {"view", "favorite", "message", "price_drop"}
ALLOWED_ORDER_STATUSES = {"created", "paid", "shipped", "completed", "cancelled", "refunded"}

REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "users": (
        "user_id",
        "country_code",
        "signup_at",
        "acquisition_channel",
        "is_business",
        "updated_at",
    ),
    "listings": (
        "listing_id",
        "seller_id",
        "category",
        "brand_tier",
        "item_condition",
        "price_eur",
        "status",
        "created_at",
        "updated_at",
    ),
    "events": ("event_id", "listing_id", "user_id", "session_id", "event_type", "event_at"),
    "orders": (
        "order_id",
        "listing_id",
        "buyer_id",
        "seller_id",
        "order_at",
        "item_price_eur",
        "shipping_eur",
        "payment_method",
        "order_status",
        "updated_at",
    ),
}

INSERT_SQL: dict[str, str] = {
    "users": """
        INSERT INTO raw.users (
            user_id, country_code, signup_at, acquisition_channel, is_business, updated_at,
            source_file, row_hash, run_id
        ) VALUES (
            %(user_id)s, %(country_code)s, %(signup_at)s, %(acquisition_channel)s,
            %(is_business)s, %(updated_at)s, %(source_file)s, %(row_hash)s, %(run_id)s
        ) ON CONFLICT DO NOTHING
    """,
    "listings": """
        INSERT INTO raw.listings (
            listing_id, seller_id, category, brand_tier, item_condition, price_eur, status,
            created_at, updated_at, source_file, row_hash, run_id
        ) VALUES (
            %(listing_id)s, %(seller_id)s, %(category)s, %(brand_tier)s, %(item_condition)s,
            %(price_eur)s, %(status)s, %(created_at)s, %(updated_at)s, %(source_file)s,
            %(row_hash)s, %(run_id)s
        ) ON CONFLICT DO NOTHING
    """,
    "events": """
        INSERT INTO raw.events (
            event_id, listing_id, user_id, session_id, event_type, event_at,
            source_file, row_hash, run_id
        ) VALUES (
            %(event_id)s, %(listing_id)s, %(user_id)s, %(session_id)s, %(event_type)s,
            %(event_at)s, %(source_file)s, %(row_hash)s, %(run_id)s
        ) ON CONFLICT DO NOTHING
    """,
    "orders": """
        INSERT INTO raw.orders (
            order_id, listing_id, buyer_id, seller_id, order_at, item_price_eur,
            shipping_eur, payment_method, order_status, updated_at, source_file, row_hash, run_id
        ) VALUES (
            %(order_id)s, %(listing_id)s, %(buyer_id)s, %(seller_id)s, %(order_at)s,
            %(item_price_eur)s, %(shipping_eur)s, %(payment_method)s, %(order_status)s,
            %(updated_at)s, %(source_file)s, %(row_hash)s, %(run_id)s
        ) ON CONFLICT DO NOTHING
    """,
}


@dataclass(frozen=True)
class ValidationResult:
    values: dict[str, Any]
    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class FileLoadResult:
    entity: str
    path: Path
    checksum: str
    rows_seen: int
    accepted: int
    quarantined: int
    skipped: bool = False
    duplicates: int = 0


@dataclass(frozen=True)
class PipelineResult:
    run_id: uuid.UUID
    files_seen: int
    files_loaded: int
    files_skipped: int
    rows_accepted: int
    rows_quarantined: int
    rows_duplicate: int = 0


def _text(row: dict[str, str | None], field: str, errors: list[str]) -> str:
    value = (row.get(field) or "").strip()
    if not value:
        errors.append(f"{field}: required")
    return value


def _timestamp(row: dict[str, str | None], field: str, errors: list[str]) -> datetime | None:
    value = _text(row, field, errors)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field}: expected ISO-8601 timestamp")
        return None
    if parsed.tzinfo is None:
        errors.append(f"{field}: timezone is required")
        return None
    return parsed.astimezone(UTC)


def _money(
    row: dict[str, str | None],
    field: str,
    errors: list[str],
    *,
    allow_zero: bool = False,
) -> Decimal | None:
    value = _text(row, field, errors)
    if not value:
        return None
    try:
        amount = Decimal(value)
    except InvalidOperation:
        errors.append(f"{field}: expected decimal money value")
        return None
    if not amount.is_finite():
        errors.append(f"{field}: must be a finite amount")
        return amount
    if amount < 0 or (amount == 0 and not allow_zero):
        comparator = "non-negative" if allow_zero else "greater than zero"
        errors.append(f"{field}: must be {comparator}")
    if abs(amount) > Decimal("9999999999.99"):
        errors.append(f"{field}: exceeds NUMERIC(12,2) range")
    if amount.as_tuple().exponent < -2:
        errors.append(f"{field}: maximum two decimal places")
    return amount


def _boolean(row: dict[str, str | None], field: str, errors: list[str]) -> bool | None:
    value = _text(row, field, errors).lower()
    if value in {"true", "1", "yes"}:
        return True
    if value in {"false", "0", "no"}:
        return False
    if value:
        errors.append(f"{field}: expected true or false")
    return None


def _choice(row: dict[str, str | None], field: str, allowed: set[str], errors: list[str]) -> str:
    value = _text(row, field, errors).lower()
    if value and value not in allowed:
        errors.append(f"{field}: unsupported value '{value}'")
    return value


def _validate_users(row: dict[str, str | None]) -> ValidationResult:
    errors: list[str] = []
    country = _text(row, "country_code", errors).upper()
    if country and (len(country) != 2 or not country.isalpha()):
        errors.append("country_code: expected two-letter code")
    signup_at = _timestamp(row, "signup_at", errors)
    updated_at = _timestamp(row, "updated_at", errors)
    if signup_at and updated_at and updated_at < signup_at:
        errors.append("updated_at: cannot precede signup_at")
    values = {
        "user_id": _text(row, "user_id", errors),
        "country_code": country,
        "signup_at": signup_at,
        "acquisition_channel": _text(row, "acquisition_channel", errors).lower(),
        "is_business": _boolean(row, "is_business", errors),
        "updated_at": updated_at,
    }
    return ValidationResult(values, tuple(errors))


def _validate_listings(row: dict[str, str | None]) -> ValidationResult:
    errors: list[str] = []
    created_at = _timestamp(row, "created_at", errors)
    updated_at = _timestamp(row, "updated_at", errors)
    if created_at and updated_at and updated_at < created_at:
        errors.append("updated_at: cannot precede created_at")
    values = {
        "listing_id": _text(row, "listing_id", errors),
        "seller_id": _text(row, "seller_id", errors),
        "category": _text(row, "category", errors).lower(),
        "brand_tier": _text(row, "brand_tier", errors).lower(),
        "item_condition": _text(row, "item_condition", errors).lower(),
        "price_eur": _money(row, "price_eur", errors),
        "status": _choice(row, "status", ALLOWED_LISTING_STATUSES, errors),
        "created_at": created_at,
        "updated_at": updated_at,
    }
    return ValidationResult(values, tuple(errors))


def _validate_events(row: dict[str, str | None]) -> ValidationResult:
    errors: list[str] = []
    values = {
        "event_id": _text(row, "event_id", errors),
        "listing_id": _text(row, "listing_id", errors),
        "user_id": _text(row, "user_id", errors),
        "session_id": _text(row, "session_id", errors),
        "event_type": _choice(row, "event_type", ALLOWED_EVENT_TYPES, errors),
        "event_at": _timestamp(row, "event_at", errors),
    }
    return ValidationResult(values, tuple(errors))


def _validate_orders(row: dict[str, str | None]) -> ValidationResult:
    errors: list[str] = []
    buyer_id = _text(row, "buyer_id", errors)
    seller_id = _text(row, "seller_id", errors)
    if buyer_id and seller_id and buyer_id == seller_id:
        errors.append("buyer_id: buyer and seller must be different")
    order_at = _timestamp(row, "order_at", errors)
    updated_at = _timestamp(row, "updated_at", errors)
    if order_at and updated_at and updated_at < order_at:
        errors.append("updated_at: cannot precede order_at")
    values = {
        "order_id": _text(row, "order_id", errors),
        "listing_id": _text(row, "listing_id", errors),
        "buyer_id": buyer_id,
        "seller_id": seller_id,
        "order_at": order_at,
        "item_price_eur": _money(row, "item_price_eur", errors),
        "shipping_eur": _money(row, "shipping_eur", errors, allow_zero=True),
        "payment_method": _text(row, "payment_method", errors).lower(),
        "order_status": _choice(row, "order_status", ALLOWED_ORDER_STATUSES, errors),
        "updated_at": updated_at,
    }
    return ValidationResult(values, tuple(errors))


VALIDATORS: dict[str, Callable[[dict[str, str | None]], ValidationResult]] = {
    "users": _validate_users,
    "listings": _validate_listings,
    "events": _validate_events,
    "orders": _validate_orders,
}


def validate_row(entity: str, row: dict[str, str | None]) -> ValidationResult:
    """Validate and convert a raw CSV row to database-ready values."""

    try:
        validator = VALIDATORS[entity]
    except KeyError as exc:
        raise ValueError(f"Unsupported entity: {entity}") from exc
    return validator(row)


def sha256_file(path: Path) -> str:
    """Calculate a checksum without reading the whole file into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def row_hash(row: dict[str, str | None]) -> str:
    canonical = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def infer_entity(path: Path) -> str:
    entity = path.stem.lower()
    if entity not in REQUIRED_COLUMNS:
        raise ValueError(
            f"Unsupported CSV filename '{path.name}'; expected users/listings/events/orders"
        )
    return entity


def _check_headers(entity: str, fieldnames: list[str] | None) -> None:
    headers = fieldnames or []
    if len(headers) != len(set(headers)):
        raise ValueError(f"{entity}.csv has duplicate column names")
    missing = set(REQUIRED_COLUMNS[entity]) - set(headers)
    if missing:
        raise ValueError(f"{entity}.csv is missing required columns: {', '.join(sorted(missing))}")
    unexpected = set(headers) - set(REQUIRED_COLUMNS[entity])
    if unexpected:
        raise ValueError(f"{entity}.csv has unexpected columns: {', '.join(sorted(unexpected))}")


def discover_files(source_path: Path) -> list[Path]:
    """Return input CSVs in deterministic partition/entity order."""

    if source_path.is_file():
        return [source_path]
    return sorted(path for path in source_path.rglob("*.csv") if path.is_file())


def ingest_file(connection: Connection[Any], path: Path, run_id: uuid.UUID) -> FileLoadResult:
    """Load one file atomically, or skip it when its checksum was processed."""

    from psycopg.types.json import Jsonb

    entity = infer_entity(path)
    checksum = sha256_file(path)
    with connection.transaction(), connection.cursor() as cursor:
        # Serialize each entity's file transactions across overlapping runs.
        # PostgreSQL releases the lock on commit/rollback, including process failure.
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"recommerce:{entity}",))
        cursor.execute(
            "SELECT 1 FROM ops.processed_files WHERE entity = %s AND file_checksum = %s",
            (entity, checksum),
        )
        if cursor.fetchone():
            LOGGER.info("Skipping previously processed file", extra={"path": str(path)})
            return FileLoadResult(entity, path, checksum, 0, 0, 0, skipped=True)

        rows_seen = accepted = quarantined = duplicates = 0
        with path.open("r", encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            _check_headers(entity, reader.fieldnames)
            for row_number, row in enumerate(reader, start=2):
                rows_seen += 1
                if None in row:
                    extra_fields = row.pop(None)
                    row["_extra_fields"] = json.dumps(extra_fields)
                    validation = ValidationResult({}, ("row: more values than header columns",))
                else:
                    validation = validate_row(entity, row)
                if not validation.is_valid:
                    cursor.execute(
                        """
                        INSERT INTO quarantine.invalid_records (
                            run_id, source_file, entity, row_number, raw_payload, error_reasons
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            run_id,
                            str(path),
                            entity,
                            row_number,
                            Jsonb(row),
                            list(validation.errors),
                        ),
                    )
                    quarantined += 1
                    continue

                parameters = {
                    **validation.values,
                    "source_file": str(path),
                    "row_hash": row_hash(row),
                    "run_id": run_id,
                }
                cursor.execute(INSERT_SQL[entity], parameters)
                if cursor.rowcount:
                    accepted += 1
                else:
                    # A repeated row is harmless; a changed payload reusing the
                    # same business key/version is an ambiguous correction.
                    from psycopg import sql

                    cursor.execute(
                        sql.SQL("SELECT 1 FROM raw.{} WHERE row_hash = %s").format(
                            sql.Identifier(entity)
                        ),
                        (parameters["row_hash"],),
                    )
                    if cursor.fetchone():
                        duplicates += 1
                    else:
                        cursor.execute(
                            """
                            INSERT INTO quarantine.invalid_records (
                                run_id, source_file, entity, row_number, raw_payload, error_reasons
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                run_id,
                                str(path),
                                entity,
                                row_number,
                                Jsonb(row),
                                ["business key/version conflicts with an existing payload"],
                            ),
                        )
                        quarantined += 1

        if sha256_file(path) != checksum:
            raise ValueError(f"Source file changed while loading: {path}")

        cursor.execute(
            """
            INSERT INTO ops.processed_files (
                entity, file_checksum, source_path, file_size_bytes, row_count,
                accepted_count, quarantined_count, duplicate_count, run_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                entity,
                checksum,
                str(path),
                path.stat().st_size,
                rows_seen,
                accepted,
                quarantined,
                duplicates,
                run_id,
            ),
        )
    LOGGER.info(
        "File loaded",
        extra={"entity": entity, "accepted": accepted, "quarantined": quarantined},
    )
    return FileLoadResult(
        entity, path, checksum, rows_seen, accepted, quarantined, duplicates=duplicates
    )


def ingest_path(
    connection: Connection[Any],
    source_path: Path,
    *,
    pipeline_name: str = "marketplace_daily_batch",
) -> PipelineResult:
    """Ingest a file or partition tree and persist run-level audit metadata."""

    files = discover_files(source_path)
    if not files:
        raise ValueError(f"No CSV files found under {source_path}")

    run_id = uuid.uuid4()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO ops.pipeline_runs (run_id, pipeline_name, source_path, status, files_seen)
            VALUES (%s, %s, %s, 'running', %s)
            """,
            (run_id, pipeline_name, str(source_path), len(files)),
        )
    connection.commit()

    results: list[FileLoadResult] = []
    try:
        for path in files:
            results.append(ingest_file(connection, path, run_id))
    except Exception as exc:
        LOGGER.exception("Pipeline run failed", extra={"run_id": str(run_id)})
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ops.pipeline_runs
                SET status = 'failed', finished_at = CURRENT_TIMESTAMP, error_message = %s
                WHERE run_id = %s
                """,
                (str(exc)[:4000], run_id),
            )
        connection.commit()
        raise

    loaded = sum(not result.skipped for result in results)
    skipped = sum(result.skipped for result in results)
    accepted = sum(result.accepted for result in results)
    quarantined = sum(result.quarantined for result in results)
    duplicates = sum(result.duplicates for result in results)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE ops.pipeline_runs
            SET status = 'succeeded', finished_at = CURRENT_TIMESTAMP,
                files_loaded = %s, files_skipped = %s,
                rows_accepted = %s, rows_quarantined = %s, rows_duplicate = %s
            WHERE run_id = %s
            """,
            (loaded, skipped, accepted, quarantined, duplicates, run_id),
        )
    connection.commit()
    return PipelineResult(run_id, len(files), loaded, skipped, accepted, quarantined, duplicates)


def ingest_directory(source_path: Path, database_url: str | None = None) -> PipelineResult:
    """Convenience API used by the CLI and Airflow DAG."""

    from recommerce.db import bootstrap, connect

    with connect(database_url) as connection:
        bootstrap(connection)
        return ingest_path(connection, source_path)
