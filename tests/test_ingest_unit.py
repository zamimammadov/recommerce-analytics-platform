from __future__ import annotations

from datetime import UTC
from pathlib import Path

import pytest

from recommerce.ingest import (
    REQUIRED_COLUMNS,
    _check_headers,
    discover_files,
    infer_entity,
    row_hash,
    sha256_file,
    validate_row,
)


def test_valid_order_is_converted_to_typed_values() -> None:
    result = validate_row(
        "orders",
        {
            "order_id": "ord_001",
            "listing_id": "lst_001",
            "buyer_id": "usr_002",
            "seller_id": "usr_001",
            "order_at": "2026-11-15T10:30:00Z",
            "item_price_eur": "42.50",
            "shipping_eur": "0.00",
            "payment_method": "card",
            "order_status": "paid",
            "updated_at": "2026-11-15T10:31:00+00:00",
        },
    )

    assert result.is_valid
    assert str(result.values["item_price_eur"]) == "42.50"
    assert result.values["order_at"].tzinfo is UTC


def test_order_rejects_same_buyer_and_seller_and_invalid_money() -> None:
    result = validate_row(
        "orders",
        {
            "order_id": "ord_bad",
            "listing_id": "lst_001",
            "buyer_id": "usr_001",
            "seller_id": "usr_001",
            "order_at": "2026-11-15T10:30:00Z",
            "item_price_eur": "-3.00",
            "shipping_eur": "free",
            "payment_method": "card",
            "order_status": "unknown",
            "updated_at": "2026-11-15T10:29:00Z",
        },
    )

    assert not result.is_valid
    assert "buyer_id: buyer and seller must be different" in result.errors
    assert "item_price_eur: must be greater than zero" in result.errors
    assert "shipping_eur: expected decimal money value" in result.errors
    assert any(error.startswith("order_status: unsupported") for error in result.errors)
    assert "updated_at: cannot precede order_at" in result.errors


def test_user_requires_timezone_and_valid_country() -> None:
    result = validate_row(
        "users",
        {
            "user_id": "usr_001",
            "country_code": "LTU",
            "signup_at": "2026-11-15T10:00:00",
            "acquisition_channel": "organic",
            "is_business": "maybe",
            "updated_at": "2026-11-15T11:00:00Z",
        },
    )

    assert not result.is_valid
    assert "country_code: expected two-letter code" in result.errors
    assert "signup_at: timezone is required" in result.errors
    assert "is_business: expected true or false" in result.errors


def test_hashes_are_stable_and_file_discovery_is_sorted(tmp_path: Path) -> None:
    first = tmp_path / "2026-11-15" / "users.csv"
    second = tmp_path / "2026-11-16" / "orders.csv"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("user_id\nusr_1\n", encoding="utf-8")
    second.write_text("order_id\nord_1\n", encoding="utf-8")

    assert discover_files(tmp_path) == [first, second]
    assert len(sha256_file(first)) == 64
    assert row_hash({"b": "2", "a": "1"}) == row_hash({"a": "1", "b": "2"})


def test_unknown_entity_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported CSV filename"):
        infer_entity(Path("payments.csv"))


@pytest.mark.parametrize("value", ["10000000000.00", "NaN", "Infinity", "12.345"])
def test_money_outside_storage_contract_is_rejected(value):
    row = {
        "listing_id": "lst_1",
        "seller_id": "usr_1",
        "category": "shoes",
        "brand_tier": "value",
        "item_condition": "good",
        "price_eur": value,
        "status": "active",
        "created_at": "2026-10-01T10:00:00Z",
        "updated_at": "2026-10-01T11:00:00Z",
    }
    assert not validate_row("listings", row).is_valid


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate"])
def test_header_contract_rejects_unapproved_changes(change):
    headers = list(REQUIRED_COLUMNS["users"])
    if change == "missing":
        headers.pop()
    elif change == "extra":
        headers.append("email")
    else:
        headers.append(headers[0])
    with pytest.raises(ValueError):
        _check_headers("users", headers)
