"""Deterministic synthetic source data for the recommerce analytics platform.

The generator uses no real personal information. A daily partition contains
new records, updates to some previous-day records, late-arriving facts, and
optional bad records that exercise the ingestion quarantine path.
"""

from __future__ import annotations

import csv
import hashlib
import random
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Final

USER_FIELDS: Final = (
    "user_id",
    "country_code",
    "signup_at",
    "acquisition_channel",
    "is_business",
    "updated_at",
)
LISTING_FIELDS: Final = (
    "listing_id",
    "seller_id",
    "category",
    "brand_tier",
    "item_condition",
    "price_eur",
    "status",
    "created_at",
    "updated_at",
)
EVENT_FIELDS: Final = (
    "event_id",
    "listing_id",
    "user_id",
    "session_id",
    "event_type",
    "event_at",
)
ORDER_FIELDS: Final = (
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
)

COUNTRIES: Final = ("DE", "FR", "LT", "NL", "PL", "ES", "IT", "BE")
CHANNELS: Final = ("organic", "paid_search", "social", "referral", "partner")
CATEGORIES: Final = (
    "women_clothing",
    "men_clothing",
    "children",
    "shoes",
    "accessories",
    "home",
    "electronics",
)
BRAND_TIERS: Final = ("value", "mid_market", "premium", "luxury")
CONDITIONS: Final = ("new_with_tags", "very_good", "good", "satisfactory")
PAYMENT_METHODS: Final = ("card", "wallet", "apple_pay", "google_pay")


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    """Parameters for one daily source partition.

    Counts describe valid records. With ``inject_invalid=True``, one malformed
    listing, event, and order are appended to guarantee quarantine examples.
    """

    output_root: Path
    batch_date: date
    seed: int = 20261115
    user_count: int = 250
    listing_count: int = 800
    event_count: int = 5_000
    order_count: int = 120
    update_share: float = 0.15
    late_arrival_rate: float = 0.03
    inject_invalid: bool = True

    def __post_init__(self) -> None:
        counts = (self.user_count, self.listing_count, self.event_count, self.order_count)
        if any(count < 0 for count in counts):
            raise ValueError("record counts cannot be negative")
        if self.listing_count and self.user_count < 2:
            raise ValueError("at least two users are required when listings are generated")
        if self.order_count > self.listing_count:
            raise ValueError("order_count cannot exceed listing_count")
        for field_name, value in (
            ("update_share", self.update_share),
            ("late_arrival_rate", self.late_arrival_rate),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{field_name} must be between 0 and 1")


def generate_batch(config: GenerationConfig) -> dict[str, Path]:
    """Generate one deterministic daily partition and return its four paths."""

    rng = random.Random(f"{config.seed}:{config.batch_date.isoformat()}")
    partition = config.output_root / config.batch_date.isoformat()
    partition.mkdir(parents=True, exist_ok=True)

    users, current_user_ids, returning_user_ids = _generate_users(config, rng)
    listings = _generate_listings(config, rng, current_user_ids, returning_user_ids)
    events = _generate_events(config, rng, users, listings)
    orders = _generate_orders(config, rng, users, listings)

    if config.inject_invalid:
        token = _date_token(config.batch_date)
        listings.append(_invalid_listing(token, config.batch_date))
        events.append(_invalid_event(token, config.batch_date))
        orders.append(_invalid_order(token, config.batch_date))

    return {
        "users": _write_csv(partition / "users.csv", USER_FIELDS, users),
        "listings": _write_csv(partition / "listings.csv", LISTING_FIELDS, listings),
        "events": _write_csv(partition / "events.csv", EVENT_FIELDS, events),
        "orders": _write_csv(partition / "orders.csv", ORDER_FIELDS, orders),
    }


def generate_range(
    output_root: Path,
    start_date: date,
    end_date: date,
    **config_overrides: Any,
) -> list[dict[str, Path]]:
    """Generate inclusive daily partitions with a shared base configuration."""

    if end_date < start_date:
        raise ValueError("end_date cannot be earlier than start_date")
    outputs: list[dict[str, Path]] = []
    current_date = start_date
    while current_date <= end_date:
        outputs.append(
            generate_batch(
                GenerationConfig(
                    output_root=output_root,
                    batch_date=current_date,
                    **config_overrides,
                )
            )
        )
        current_date += timedelta(days=1)
    return outputs


def generate_dataset(
    output_dir: Path,
    start_date: date,
    days: int,
    users: int,
    listings_per_day: int,
    seed: int,
    invalid_rate: float = 0.01,
) -> dict[str, Any]:
    """Convenience API used by the CLI to generate a realistic demo dataset.

    The MVP guarantees one bad row per fact/entity file whenever
    ``invalid_rate`` is greater than zero. The returned metadata is safe to
    print as a run summary.
    """

    if days < 1:
        raise ValueError("days must be at least one")
    if not 0 <= invalid_rate <= 1:
        raise ValueError("invalid_rate must be between 0 and 1")
    end_date = start_date + timedelta(days=days - 1)
    event_count = max(listings_per_day * 6, 1 if listings_per_day else 0)
    order_count = min(listings_per_day, round(listings_per_day * 0.15))
    batches = generate_range(
        output_dir,
        start_date,
        end_date,
        seed=seed,
        user_count=users,
        listing_count=listings_per_day,
        event_count=event_count,
        order_count=order_count,
        inject_invalid=invalid_rate > 0,
    )
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "days": days,
        "partitions": [str(paths["users"].parent) for paths in batches],
        "valid_rows": {
            "users": users * days,
            "listings": listings_per_day * days,
            "events": event_count * days,
            "orders": order_count * days,
        },
        "invalid_examples_per_day": 3 if invalid_rate > 0 else 0,
    }


def _generate_users(
    config: GenerationConfig, rng: random.Random
) -> tuple[list[dict[str, str]], list[str], list[str]]:
    token = _date_token(config.batch_date)
    previous_token = _date_token(config.batch_date - timedelta(days=1))
    returning_count = _portion(config.user_count, config.update_share)
    new_count = config.user_count - returning_count
    returning_ids = [f"usr_{previous_token}_{i:06d}" for i in range(returning_count)]
    current_ids = [f"usr_{token}_{i:06d}" for i in range(new_count)]
    rows: list[dict[str, str]] = []

    for user_id in returning_ids:
        rows.append(
            _user_row(
                user_id=user_id,
                signup_day=_origin_day(user_id, min_age_days=31, max_age_days=365),
                updated_day=config.batch_date,
                seed=config.seed,
            )
        )

    for user_id in current_ids:
        rows.append(
            _user_row(
                user_id=user_id,
                signup_day=_origin_day(user_id, min_age_days=31, max_age_days=365),
                updated_day=config.batch_date,
                seed=config.seed,
            )
        )
    return rows, current_ids, returning_ids


def _user_row(
    *,
    user_id: str,
    signup_day: date,
    updated_day: date,
    seed: int,
) -> dict[str, str]:
    """Create stable user attributes that survive later daily updates."""

    identity_rng = random.Random(f"{seed}:user:{user_id}")
    signup_at = _stable_timestamp(signup_day, f"{seed}:signup:{user_id}")
    updated_at = (
        signup_at
        if updated_day == signup_day
        else _stable_timestamp(updated_day, f"{seed}:user-update:{user_id}:{updated_day}")
    )
    return {
        "user_id": user_id,
        "country_code": identity_rng.choice(COUNTRIES),
        "signup_at": signup_at,
        "acquisition_channel": identity_rng.choices(
            CHANNELS,
            weights=(42, 18, 17, 16, 7),
            k=1,
        )[0],
        "is_business": "true" if identity_rng.random() < 0.04 else "false",
        "updated_at": updated_at,
    }


def _generate_listings(
    config: GenerationConfig,
    rng: random.Random,
    current_user_ids: list[str],
    returning_user_ids: list[str],
) -> list[dict[str, str]]:
    token = _date_token(config.batch_date)
    previous_token = _date_token(config.batch_date - timedelta(days=1))
    update_count = _listing_update_count(config)
    new_count = config.listing_count - update_count
    rows: list[dict[str, str]] = []

    for index in range(update_count):
        base_price = _price_for(index, previous_token)
        rows.append(
            _listing_row(
                listing_id=f"lst_{previous_token}_{index:07d}",
                seller_id=returning_user_ids[index],
                created_day=_origin_day(
                    f"lst_{previous_token}_{index:07d}",
                    min_age_days=0,
                    max_age_days=30,
                ),
                updated_day=config.batch_date,
                price=(base_price * Decimal("0.90")).quantize(Decimal("0.01")),
                status=rng.choices(
                    ("active", "removed"),
                    weights=(95, 5),
                    k=1,
                )[0],
                rng=rng,
            )
        )

    seller_pool = current_user_ids or returning_user_ids
    for index in range(new_count):
        listing_id = f"lst_{token}_{index:07d}"
        rows.append(
            _listing_row(
                listing_id=listing_id,
                seller_id=seller_pool[index % len(seller_pool)],
                created_day=_origin_day(listing_id, min_age_days=0, max_age_days=30),
                updated_day=config.batch_date,
                price=_price_for(index, token),
                status="active",
                rng=rng,
            )
        )
    return rows


def _listing_row(
    *,
    listing_id: str,
    seller_id: str,
    created_day: date,
    updated_day: date,
    price: Decimal,
    status: str,
    rng: random.Random,
) -> dict[str, str]:
    identity_rng = random.Random(f"listing:{listing_id}")
    created_at = _stable_timestamp(created_day, f"listing-created:{listing_id}")
    updated_at = _timestamp_at_or_after(updated_day, datetime.fromisoformat(created_at), rng)
    return {
        "listing_id": listing_id,
        "seller_id": seller_id,
        "category": identity_rng.choices(
            CATEGORIES,
            weights=(25, 18, 18, 12, 11, 9, 7),
            k=1,
        )[0],
        "brand_tier": identity_rng.choices(
            BRAND_TIERS,
            weights=(32, 45, 19, 4),
            k=1,
        )[0],
        "item_condition": identity_rng.choices(
            CONDITIONS,
            weights=(9, 48, 35, 8),
            k=1,
        )[0],
        "price_eur": _money(price),
        "status": status,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _generate_events(
    config: GenerationConfig,
    rng: random.Random,
    users: list[dict[str, str]],
    listings: list[dict[str, str]],
) -> list[dict[str, str]]:
    if not users or not listings:
        return []
    token = _date_token(config.batch_date)
    user_ids = [row["user_id"] for row in users]
    candidates = [row for row in listings if row["status"] != "removed"] or listings
    rows: list[dict[str, str]] = []
    for index in range(config.event_count):
        listing = rng.choice(candidates)
        user_id = rng.choice(user_ids)
        if user_id == listing["seller_id"] and len(user_ids) > 1:
            user_id = user_ids[(user_ids.index(user_id) + 1) % len(user_ids)]
        listing_created_at = datetime.fromisoformat(listing["created_at"])
        event_day = max(
            _fact_day(config.batch_date, config.late_arrival_rate, rng),
            listing_created_at.date(),
        )
        rows.append(
            {
                "event_id": f"evt_{token}_{index:09d}",
                "listing_id": listing["listing_id"],
                "user_id": user_id,
                "session_id": (
                    f"ses_{token}_{user_id}_"
                    f"{rng.randrange(max(1, config.event_count // max(1, len(user_ids)))):04d}"
                ),
                "event_type": rng.choices(
                    ("view", "favorite", "message", "price_drop"),
                    weights=(78, 13, 7, 2),
                    k=1,
                )[0],
                "event_at": _timestamp_at_or_after(event_day, listing_created_at, rng),
            }
        )
    return rows


def _generate_orders(
    config: GenerationConfig,
    rng: random.Random,
    users: list[dict[str, str]],
    listings: list[dict[str, str]],
) -> list[dict[str, str]]:
    if not users or not listings:
        return []
    token = _date_token(config.batch_date)
    user_ids = [row["user_id"] for row in users]
    # Reserve a stable, unsold prefix for next-day price updates. Other fresh
    # listings can be purchased once; old listing versions are never resold.
    update_count = _listing_update_count(config)
    candidates = [
        row
        for row in listings
        if row["listing_id"].startswith(f"lst_{token}_")
        and int(row["listing_id"].rsplit("_", 1)[1]) >= update_count
    ]
    selected = rng.sample(candidates, k=config.order_count)
    rows: list[dict[str, str]] = []
    for index, listing in enumerate(selected):
        buyer_id = rng.choice(user_ids)
        while buyer_id == listing["seller_id"]:
            buyer_id = rng.choice(user_ids)
        listing_created_at = datetime.fromisoformat(listing["created_at"])
        order_day = max(
            _fact_day(config.batch_date, config.late_arrival_rate, rng),
            listing_created_at.date(),
        )
        order_at = _timestamp_at_or_after(order_day, listing_created_at, rng)
        updated_at = _timestamp_at_or_after(
            config.batch_date,
            datetime.fromisoformat(order_at),
            rng,
        )
        order_status = rng.choices(
            ("created", "paid", "shipped", "completed", "cancelled", "refunded"),
            weights=(4, 11, 20, 57, 5, 3),
            k=1,
        )[0]
        listing["status"] = {
            "created": "reserved",
            "paid": "reserved",
            "shipped": "sold",
            "completed": "sold",
            "cancelled": "active",
            "refunded": "active",
        }[order_status]
        listing["updated_at"] = max(listing["updated_at"], updated_at)
        rows.append(
            {
                "order_id": f"ord_{token}_{index:08d}",
                "listing_id": listing["listing_id"],
                "buyer_id": buyer_id,
                "seller_id": listing["seller_id"],
                "order_at": order_at,
                "item_price_eur": listing["price_eur"],
                "shipping_eur": _money(
                    rng.choice((Decimal("2.99"), Decimal("3.49"), Decimal("4.99")))
                ),
                "payment_method": rng.choices(PAYMENT_METHODS, weights=(67, 18, 9, 6), k=1)[0],
                "order_status": order_status,
                "updated_at": updated_at,
            }
        )
    return rows


def _listing_update_count(config: GenerationConfig) -> int:
    """Keep enough fresh listings for orders and an unsold update cohort."""

    return min(
        _portion(config.listing_count, config.update_share),
        _portion(config.user_count, config.update_share),
        (config.listing_count - config.order_count) // 2,
    )


def _portion(total: int, share: float) -> int:
    if total == 0 or share == 0:
        return 0
    return min(total, max(1, round(total * share)))


def _price_for(index: int, token: str) -> Decimal:
    cents = 500 + ((index * 1_943 + int(token[-4:]) * 37) % 49_500)
    return (Decimal(cents) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _fact_day(batch_date: date, late_rate: float, rng: random.Random) -> date:
    if rng.random() < late_rate:
        return batch_date - timedelta(days=rng.randint(1, 7))
    return batch_date


def _stable_timestamp(day: date, key: str) -> str:
    """Derive an immutable UTC timestamp from an entity key."""

    digest = hashlib.sha256(key.encode("utf-8")).digest()
    seconds = int.from_bytes(digest[:8], "big") % (24 * 60 * 60)
    value = datetime.combine(day, time.min, tzinfo=UTC) + timedelta(seconds=seconds)
    return value.isoformat()


def _origin_day(identifier: str, *, min_age_days: int, max_age_days: int) -> date:
    """Derive a stable historical business date from an entity identifier."""

    if min_age_days < 0 or max_age_days < min_age_days:
        raise ValueError("invalid age range")
    try:
        token = identifier.split("_")[1]
        first_seen_day = datetime.strptime(token, "%Y%m%d").date()
    except (IndexError, ValueError) as error:
        raise ValueError(f"identifier has no YYYYMMDD token: {identifier}") from error
    span = max_age_days - min_age_days + 1
    digest = hashlib.sha256(f"origin:{identifier}".encode()).digest()
    age_days = min_age_days + (int.from_bytes(digest[:4], "big") % span)
    return first_seen_day - timedelta(days=age_days)


def _timestamp_at_or_after(
    day: date,
    minimum: datetime,
    rng: random.Random,
) -> str:
    """Choose a UTC time on ``day`` that is not earlier than ``minimum``."""

    day_start = datetime.combine(day, time.min, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    lower_bound = max(day_start, minimum.astimezone(UTC))
    if lower_bound >= day_end:
        raise ValueError("day must be on or after the minimum timestamp's date")
    available_seconds = int((day_end - lower_bound).total_seconds())
    value = lower_bound + timedelta(seconds=rng.randrange(max(1, available_seconds)))
    return value.isoformat()


def _date_token(value: date) -> str:
    return value.strftime("%Y%m%d")


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _write_csv(path: Path, fields: Iterable[str], rows: list[dict[str, str]]) -> Path:
    temporary_path = path.with_suffix(".csv.tmp")
    with temporary_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(fields), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    temporary_path.replace(path)
    return path


def _invalid_listing(token: str, batch_date: date) -> dict[str, str]:
    timestamp = datetime.combine(batch_date, time.min, tzinfo=UTC).isoformat()
    return {
        "listing_id": f"bad_listing_{token}",
        "seller_id": "",
        "category": "unknown_category",
        "brand_tier": "value",
        "item_condition": "broken",
        "price_eur": "-10.00",
        "status": "unknown",
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def _invalid_event(token: str, batch_date: date) -> dict[str, str]:
    timestamp = datetime.combine(batch_date, time.min, tzinfo=UTC).isoformat()
    return {
        "event_id": f"bad_event_{token}",
        "listing_id": "missing_listing",
        "user_id": "missing_user",
        "session_id": f"bad_session_{token}",
        "event_type": "click",
        "event_at": timestamp,
    }


def _invalid_order(token: str, batch_date: date) -> dict[str, str]:
    timestamp = datetime.combine(batch_date, time.min, tzinfo=UTC).isoformat()
    return {
        "order_id": f"bad_order_{token}",
        "listing_id": "missing_listing",
        "buyer_id": "same_user",
        "seller_id": "same_user",
        "order_at": timestamp,
        "item_price_eur": "-25.00",
        "shipping_eur": "-1.00",
        "payment_method": "cash",
        "order_status": "lost",
        "updated_at": timestamp,
    }
