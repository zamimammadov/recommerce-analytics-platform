"""Persisted data-quality checks for the marketplace pipeline.

The checks deliberately run against the latest raw entity state. Ingestion
validation answers "is this row structurally valid?"; these checks answer
cross-table questions such as "does this listing's seller exist?".
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import psycopg

LOGGER = logging.getLogger(__name__)


class Severity(StrEnum):
    """Operational importance of a failed check."""

    ERROR = "error"
    WARNING = "warning"


class CheckStatus(StrEnum):
    """Outcome stored in the quality-results table."""

    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True)
class CheckDefinition:
    """A query that must return one integer named ``failed_rows``."""

    name: str
    description: str
    sql: str
    severity: Severity = Severity.ERROR
    max_failed_rows: int = 0


@dataclass(frozen=True)
class CheckResult:
    """Serializable result of one data-quality check."""

    name: str
    description: str
    severity: Severity
    status: CheckStatus
    failed_rows: int
    max_failed_rows: int
    checked_at: datetime
    error_message: str | None = None


LATEST_USERS = """
    SELECT user_id
    FROM (
        SELECT user_id,
               row_number() OVER (
                   PARTITION BY user_id ORDER BY updated_at DESC, ingested_at DESC
               ) AS row_number
        FROM raw.users
    ) ranked
    WHERE row_number = 1
"""

LATEST_LISTINGS = """
    SELECT listing_id, seller_id, price_eur, status
    FROM (
        SELECT listing_id, seller_id, price_eur, status,
               row_number() OVER (
                   PARTITION BY listing_id ORDER BY updated_at DESC, ingested_at DESC
               ) AS row_number
        FROM raw.listings
    ) ranked
    WHERE row_number = 1
"""

LATEST_ORDERS = """
    SELECT order_id, listing_id, buyer_id, seller_id, item_price_eur, shipping_eur,
           order_status
    FROM (
        SELECT order_id, listing_id, buyer_id, seller_id, item_price_eur, shipping_eur,
               order_status,
               row_number() OVER (
                   PARTITION BY order_id ORDER BY updated_at DESC, ingested_at DESC
               ) AS row_number
        FROM raw.orders
    ) ranked
    WHERE row_number = 1
"""


DEFAULT_CHECKS: tuple[CheckDefinition, ...] = (
    CheckDefinition(
        name="listing_seller_exists",
        description="Every current listing must reference an existing user.",
        sql=f"""
            WITH users AS ({LATEST_USERS}), listings AS ({LATEST_LISTINGS})
            SELECT count(*)::bigint AS failed_rows
            FROM listings l
            LEFT JOIN users u ON u.user_id = l.seller_id
            WHERE u.user_id IS NULL
        """,
    ),
    CheckDefinition(
        name="event_listing_exists",
        description="Every engagement event must reference an existing listing.",
        sql=f"""
            WITH listings AS ({LATEST_LISTINGS})
            SELECT count(*)::bigint AS failed_rows
            FROM raw.events e
            LEFT JOIN listings l ON l.listing_id = e.listing_id
            WHERE l.listing_id IS NULL
        """,
    ),
    CheckDefinition(
        name="order_references_exist",
        description="Every order must reference its listing, buyer, and seller.",
        sql=f"""
            WITH users AS ({LATEST_USERS}), listings AS ({LATEST_LISTINGS}),
                 orders AS ({LATEST_ORDERS})
            SELECT count(*)::bigint AS failed_rows
            FROM orders o
            LEFT JOIN listings l ON l.listing_id = o.listing_id
            LEFT JOIN users buyer ON buyer.user_id = o.buyer_id
            LEFT JOIN users seller ON seller.user_id = o.seller_id
            WHERE l.listing_id IS NULL
               OR buyer.user_id IS NULL
               OR seller.user_id IS NULL
        """,
    ),
    CheckDefinition(
        name="buyer_is_not_seller",
        description="Marketplace users cannot buy their own listing.",
        sql=f"""
            WITH orders AS ({LATEST_ORDERS})
            SELECT count(*)::bigint AS failed_rows
            FROM orders
            WHERE buyer_id = seller_id
        """,
    ),
    CheckDefinition(
        name="positive_order_amounts",
        description="Order item and shipping amounts cannot be negative.",
        sql=f"""
            WITH orders AS ({LATEST_ORDERS})
            SELECT count(*)::bigint AS failed_rows
            FROM orders
            WHERE item_price_eur <= 0 OR shipping_eur < 0
        """,
    ),
    CheckDefinition(
        name="sold_listing_has_order",
        description="A sold listing should have at least one non-cancelled order.",
        sql=f"""
            WITH listings AS ({LATEST_LISTINGS}), orders AS ({LATEST_ORDERS})
            SELECT count(*)::bigint AS failed_rows
            FROM listings l
            LEFT JOIN orders o
              ON o.listing_id = l.listing_id
             AND o.order_status NOT IN ('cancelled', 'refunded')
            WHERE l.status = 'sold' AND o.order_id IS NULL
        """,
        severity=Severity.WARNING,
    ),
)


def classify_result(
    failed_rows: int,
    max_failed_rows: int,
    severity: Severity,
) -> CheckStatus:
    """Convert a failure count to an operational status."""

    if failed_rows <= max_failed_rows:
        return CheckStatus.PASS
    return CheckStatus.FAIL


def evaluate_check(
    definition: CheckDefinition,
    failed_rows: int,
    *,
    checked_at: datetime | None = None,
) -> CheckResult:
    """Build a result without a database, keeping unit tests fast."""

    if failed_rows < 0:
        raise ValueError("failed_rows cannot be negative")
    timestamp = checked_at or datetime.now(UTC)
    return CheckResult(
        name=definition.name,
        description=definition.description,
        severity=definition.severity,
        status=classify_result(
            failed_rows,
            definition.max_failed_rows,
            definition.severity,
        ),
        failed_rows=failed_rows,
        max_failed_rows=definition.max_failed_rows,
        checked_at=timestamp,
    )


def _persist_result(
    connection: Any,
    result: CheckResult,
    pipeline_run_id: str | None,
) -> None:
    details = json.dumps(
        {
            "description": result.description,
            "threshold": result.max_failed_rows,
            "error_message": result.error_message,
        }
    )
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO ops.data_quality_results (
                run_id,
                check_name,
                severity,
                status,
                observed_value,
                threshold,
                checked_at,
                details
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                pipeline_run_id,
                result.name,
                result.severity.value,
                result.status.value,
                result.failed_rows,
                str(result.max_failed_rows),
                result.checked_at,
                details,
            ),
        )


def _run_checks_on_connection(
    connection: Any,
    checks: tuple[CheckDefinition, ...],
    pipeline_run_id: str | None,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for definition in checks:
        try:
            # A savepoint keeps one broken query from poisoning the transaction
            # and hiding all subsequent checks.
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(definition.sql)
                row = cursor.fetchone()
            if row is None:
                raise RuntimeError("quality query returned no result")
            result = evaluate_check(definition, int(row[0]))
        except Exception as error:  # one broken check must not hide later checks
            LOGGER.exception("Data-quality check %s could not run", definition.name)
            result = CheckResult(
                name=definition.name,
                description=definition.description,
                severity=definition.severity,
                status=CheckStatus.FAIL,
                failed_rows=0,
                max_failed_rows=definition.max_failed_rows,
                checked_at=datetime.now(UTC),
                error_message=str(error),
            )
        with connection.transaction():
            _persist_result(connection, result, pipeline_run_id)
        results.append(result)
    return results


def run_quality_checks(
    database_url: str,
    *,
    pipeline_run_id: str | None = None,
    checks: tuple[CheckDefinition, ...] = DEFAULT_CHECKS,
) -> list[CheckResult]:
    """Execute, persist, and return all configured data-quality checks."""

    if not database_url:
        raise ValueError("database_url must not be empty")
    with psycopg.connect(database_url) as connection:
        results = _run_checks_on_connection(connection, checks, pipeline_run_id)
    counts = {status.value: 0 for status in CheckStatus}
    for result in results:
        counts[result.status.value] += 1
    LOGGER.info("Data-quality run completed: %s", counts)
    return results


def results_as_dicts(results: list[CheckResult]) -> list[dict[str, Any]]:
    """Return JSON-friendly results for CLI output or observability tooling."""

    serialized: list[dict[str, Any]] = []
    for result in results:
        item = asdict(result)
        item["severity"] = result.severity.value
        item["status"] = result.status.value
        item["checked_at"] = result.checked_at.isoformat()
        serialized.append(item)
    return serialized
