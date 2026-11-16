import pandas as pd

from recommerce.analytics import build_executive_summary
from recommerce.db import sqlalchemy_url


def test_summary_uses_weighted_ratios_and_correct_gmv_denominator():
    daily = pd.DataFrame(
        {
            "metric_date": ["2026-10-01", "2026-10-02"],
            "new_listings": [10, 20],
            "orders": [10, 2],
            "gmv_eligible_orders": [8, 1],
            "completed_orders": [6, 1],
            "item_gmv_eur": [160, 40],
            "views": [100, 10],
        }
    )
    listings = pd.DataFrame({"reached_completed_stage": [True, False, False, False]})
    summary = build_executive_summary(daily, listings)
    assert summary.average_order_value_eur == 22.22  # 200 / 9, not 200 / 7 or 200 / 12
    assert summary.overall_view_to_order_rate == 0.1091  # 12 / 110, not mean(0.1, 0.2)
    assert summary.listing_sell_through_rate == 0.25


def test_sqlalchemy_uses_psycopg3_and_preserves_encoded_password():
    url = sqlalchemy_url("postgresql://analyst:p%40ss%2Fword@localhost/market")
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p@ss/word"
