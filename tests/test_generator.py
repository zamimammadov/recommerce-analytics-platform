from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

import pytest

from recommerce.generator import GenerationConfig, generate_batch, generate_dataset, generate_range


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def test_generation_is_byte_for_byte_deterministic(tmp_path: Path) -> None:
    common = {
        "batch_date": date(2026, 11, 15),
        "seed": 99,
        "user_count": 20,
        "listing_count": 40,
        "event_count": 100,
        "order_count": 10,
    }
    first = generate_batch(GenerationConfig(output_root=tmp_path / "first", **common))
    second = generate_batch(GenerationConfig(output_root=tmp_path / "second", **common))

    assert first.keys() == second.keys()
    for entity in first:
        assert first[entity].read_bytes() == second[entity].read_bytes()


def test_valid_rows_have_consistent_marketplace_relationships(tmp_path: Path) -> None:
    paths = generate_batch(
        GenerationConfig(
            output_root=tmp_path,
            batch_date=date(2026, 11, 15),
            user_count=30,
            listing_count=60,
            event_count=200,
            order_count=20,
            inject_invalid=False,
        )
    )
    users = _rows(paths["users"])
    listings = _rows(paths["listings"])
    events = _rows(paths["events"])
    orders = _rows(paths["orders"])

    user_ids = {row["user_id"] for row in users}
    signup_by_user = {row["user_id"]: datetime.fromisoformat(row["signup_at"]) for row in users}
    listing_ids = {row["listing_id"] for row in listings}
    seller_by_listing = {row["listing_id"]: row["seller_id"] for row in listings}

    assert len(users) == 30
    assert len(listings) == 60
    assert len(events) == 200
    assert len(orders) == 20
    assert {row["seller_id"] for row in listings} <= user_ids
    assert {row["listing_id"] for row in events} <= listing_ids
    assert {row["user_id"] for row in events} <= user_ids
    session_users: dict[str, set[str]] = {}
    for event in events:
        session_users.setdefault(event["session_id"], set()).add(event["user_id"])
    assert all(len(user_ids) == 1 for user_ids in session_users.values())
    assert {row["listing_id"] for row in orders} <= listing_ids
    assert {row["buyer_id"] for row in orders} <= user_ids
    assert all(row["seller_id"] == seller_by_listing[row["listing_id"]] for row in orders)
    assert all(row["buyer_id"] != row["seller_id"] for row in orders)
    assert all(
        datetime.fromisoformat(row["created_at"]) >= signup_by_user[row["seller_id"]]
        for row in listings
    )
    assert all(
        datetime.fromisoformat(row["updated_at"]) >= datetime.fromisoformat(row["created_at"])
        for row in listings
    )
    assert all(
        datetime.fromisoformat(row["updated_at"]) >= datetime.fromisoformat(row["order_at"])
        for row in orders
    )


def test_generator_guarantees_quarantine_examples_and_late_facts(tmp_path: Path) -> None:
    batch_date = date(2026, 11, 15)
    paths = generate_batch(
        GenerationConfig(
            output_root=tmp_path,
            batch_date=batch_date,
            user_count=25,
            listing_count=50,
            event_count=80,
            order_count=20,
            late_arrival_rate=1.0,
            inject_invalid=True,
        )
    )
    listings = _rows(paths["listings"])
    events = _rows(paths["events"])
    orders = _rows(paths["orders"])

    assert any(row["listing_id"].startswith("bad_listing_") for row in listings)
    assert any(row["event_type"] == "click" for row in events)
    assert any(row["order_status"] == "lost" for row in orders)

    valid_events = [row for row in events if not row["event_id"].startswith("bad_")]
    valid_orders = [row for row in orders if not row["order_id"].startswith("bad_")]
    created_at = {
        row["listing_id"]: datetime.fromisoformat(row["created_at"])
        for row in listings
        if not row["listing_id"].startswith("bad_")
    }
    assert any(datetime.fromisoformat(row["event_at"]).date() < batch_date for row in valid_events)
    assert any(datetime.fromisoformat(row["order_at"]).date() < batch_date for row in valid_orders)
    assert all(
        datetime.fromisoformat(row["event_at"]) >= created_at[row["listing_id"]]
        for row in valid_events
    )
    assert all(
        datetime.fromisoformat(row["order_at"]) >= created_at[row["listing_id"]]
        for row in valid_orders
    )


def test_generate_range_and_cli_api_are_inclusive(tmp_path: Path) -> None:
    outputs = generate_range(
        tmp_path / "range",
        date(2026, 11, 13),
        date(2026, 11, 15),
        user_count=10,
        listing_count=10,
        event_count=10,
        order_count=2,
        inject_invalid=False,
    )
    assert len(outputs) == 3
    assert sorted(path.name for path in (tmp_path / "range").iterdir()) == [
        "2026-11-13",
        "2026-11-14",
        "2026-11-15",
    ]

    summary = generate_dataset(
        tmp_path / "dataset",
        date(2026, 11, 14),
        days=2,
        users=12,
        listings_per_day=20,
        seed=7,
        invalid_rate=0,
    )
    assert summary["days"] == 2
    assert summary["end_date"] == "2026-11-15"
    assert summary["valid_rows"]["events"] == 240
    assert summary["invalid_examples_per_day"] == 0


def test_adjacent_partitions_preserve_immutable_entity_attributes(tmp_path: Path) -> None:
    generate_range(
        tmp_path,
        date(2026, 11, 14),
        date(2026, 11, 15),
        user_count=40,
        listing_count=80,
        event_count=100,
        order_count=10,
        inject_invalid=False,
    )
    first_users = {row["user_id"]: row for row in _rows(tmp_path / "2026-11-14/users.csv")}
    next_users = {row["user_id"]: row for row in _rows(tmp_path / "2026-11-15/users.csv")}
    first_listings = {row["listing_id"]: row for row in _rows(tmp_path / "2026-11-14/listings.csv")}
    next_listings = {row["listing_id"]: row for row in _rows(tmp_path / "2026-11-15/listings.csv")}

    repeated_users = first_users.keys() & next_users.keys()
    repeated_listings = first_listings.keys() & next_listings.keys()
    assert repeated_users
    assert repeated_listings
    for user_id in repeated_users:
        assert first_users[user_id]["signup_at"] == next_users[user_id]["signup_at"]
        assert first_users[user_id]["country_code"] == next_users[user_id]["country_code"]
        assert (
            first_users[user_id]["acquisition_channel"]
            == next_users[user_id]["acquisition_channel"]
        )
    for listing_id in repeated_listings:
        assert first_listings[listing_id]["created_at"] == next_listings[listing_id]["created_at"]
        assert first_listings[listing_id]["seller_id"] == next_listings[listing_id]["seller_id"]
        assert first_listings[listing_id]["category"] == next_listings[listing_id]["category"]
        assert first_listings[listing_id]["price_eur"] != next_listings[listing_id]["price_eur"]


def test_listing_lifecycle_prevents_resale_and_matches_order_outcomes(tmp_path: Path) -> None:
    outputs = generate_range(
        tmp_path,
        date(2026, 10, 1),
        date(2026, 10, 14),
        user_count=100,
        listing_count=200,
        event_count=300,
        order_count=40,
        inject_invalid=False,
    )
    orders = [row for paths in outputs for row in _rows(paths["orders"])]
    listing_ids = [row["listing_id"] for row in orders]
    latest_listings = {
        row["listing_id"]: row for paths in outputs for row in _rows(paths["listings"])
    }
    expected_status = {
        "created": "reserved",
        "paid": "reserved",
        "shipped": "sold",
        "completed": "sold",
        "cancelled": "active",
        "refunded": "active",
    }

    assert len(orders) == 14 * 40
    assert len(listing_ids) == len(set(listing_ids))
    for order in orders:
        listing = latest_listings[order["listing_id"]]
        assert listing["status"] == expected_status[order["order_status"]]
        assert datetime.fromisoformat(listing["updated_at"]) >= datetime.fromisoformat(
            order["updated_at"]
        )
    sold_ids = {
        listing_id for listing_id, row in latest_listings.items() if row["status"] == "sold"
    }
    qualifying_order_ids = {
        row["listing_id"] for row in orders if row["order_status"] in {"shipped", "completed"}
    }
    assert sold_ids == qualifying_order_ids


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"order_count": 11, "listing_count": 10}, "order_count"),
        ({"late_arrival_rate": 1.1}, "late_arrival_rate"),
        ({"user_count": 1, "listing_count": 1}, "two users"),
    ],
)
def test_invalid_configuration_is_rejected(
    tmp_path: Path, overrides: dict[str, int | float], message: str
) -> None:
    base: dict[str, object] = {
        "output_root": tmp_path,
        "batch_date": date(2026, 11, 15),
        "user_count": 20,
        "listing_count": 10,
        "event_count": 10,
        "order_count": 2,
    }
    base.update(overrides)

    with pytest.raises(ValueError, match=message):
        GenerationConfig(**base)  # type: ignore[arg-type]
