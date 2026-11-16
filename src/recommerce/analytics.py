"""Pandas-based exports for recruiter-friendly business analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, create_engine, text

from recommerce.db import sqlalchemy_url


@dataclass(frozen=True)
class ExecutiveSummary:
    """Small, explainable set of marketplace outcome metrics."""

    period_start: str
    period_end: str
    new_listings: int
    total_orders: int
    gmv_eligible_orders: int
    completed_orders: int
    gross_merchandise_value_eur: float
    average_order_value_eur: float
    listing_sell_through_rate: float | None
    overall_view_to_order_rate: float


def _query(engine: Engine, relation: str) -> pd.DataFrame:
    allowed = {
        "analytics.mart_daily_marketplace_kpis",
        "analytics.mart_seller_performance",
        "analytics.mart_listing_funnel",
    }
    if relation not in allowed:
        raise ValueError(f"Unsupported analytics relation: {relation}")
    return pd.read_sql_query(text(f"SELECT * FROM {relation}"), engine)  # noqa: S608


def _column_total(frame: pd.DataFrame, *names: str) -> float:
    for name in names:
        if name in frame.columns:
            return float(pd.to_numeric(frame[name], errors="coerce").fillna(0).sum())
    return 0.0


def _date_column(frame: pd.DataFrame) -> str:
    for name in ("metric_date", "date_day", "order_date"):
        if name in frame.columns:
            return name
    raise ValueError("Daily KPI model has no recognised date column")


def build_executive_summary(
    daily_kpis: pd.DataFrame,
    listing_funnel: pd.DataFrame | None = None,
) -> ExecutiveSummary:
    """Aggregate daily facts without averaging daily ratios incorrectly."""

    if daily_kpis.empty:
        raise ValueError("daily_kpis cannot be empty")

    date_column = _date_column(daily_kpis)
    dates = pd.to_datetime(daily_kpis[date_column], utc=True)
    listings = _column_total(daily_kpis, "new_listings")
    total_orders = _column_total(daily_kpis, "orders")
    completed_orders = _column_total(daily_kpis, "completed_orders", "orders_completed")
    gmv_eligible_orders = _column_total(
        daily_kpis,
        "gmv_eligible_orders",
        "completed_orders",
    )
    gmv = _column_total(
        daily_kpis,
        "gross_merchandise_value_eur",
        "gmv_eur",
        "item_gmv_eur",
    )
    views = _column_total(daily_kpis, "listing_views", "views")
    listing_sell_through_rate: float | None = None
    if (
        listing_funnel is not None
        and not listing_funnel.empty
        and "reached_completed_stage" in listing_funnel
    ):
        completed_flags = listing_funnel["reached_completed_stage"].fillna(False).astype(bool)
        listing_sell_through_rate = round(float(completed_flags.mean()), 4)

    return ExecutiveSummary(
        period_start=dates.min().date().isoformat(),
        period_end=dates.max().date().isoformat(),
        new_listings=int(listings),
        total_orders=int(total_orders),
        gmv_eligible_orders=int(gmv_eligible_orders),
        completed_orders=int(completed_orders),
        gross_merchandise_value_eur=round(gmv, 2),
        average_order_value_eur=round(gmv / gmv_eligible_orders, 2) if gmv_eligible_orders else 0.0,
        listing_sell_through_rate=listing_sell_through_rate,
        overall_view_to_order_rate=round(total_orders / views, 4) if views else 0.0,
    )


def _summary_markdown(summary: ExecutiveSummary) -> str:
    sell_through = (
        f"{summary.listing_sell_through_rate:.2%}"
        if summary.listing_sell_through_rate is not None
        else "n/a"
    )
    return f"""# Marketplace executive summary

Period: **{summary.period_start} to {summary.period_end}**

| Metric | Value |
|---|---:|
| New listings | {summary.new_listings:,} |
| Orders | {summary.total_orders:,} |
| GMV-eligible orders | {summary.gmv_eligible_orders:,} |
| Completed orders | {summary.completed_orders:,} |
| GMV | EUR {summary.gross_merchandise_value_eur:,.2f} |
| Average order value | EUR {summary.average_order_value_eur:,.2f} |
| Listing sell-through rate | {sell_through} |
| View-to-order rate | {summary.overall_view_to_order_rate:.2%} |

## Interpretation guardrails

- GMV is marketplace volume, not company revenue.
- View-to-order is an activity ratio computed from totals, not a user-level
  conversion probability or an average of daily percentages.
- Sell-through is computed from listing-level outcomes, not by dividing flows
  from unrelated cohorts.
- Synthetic data demonstrates engineering behaviour; it is not evidence of a
  real marketplace's commercial performance.
"""


def export_business_metrics(database_url: str, output_dir: Path) -> dict[str, Path]:
    """Export marts and a human-readable summary from PostgreSQL."""

    if not database_url:
        raise ValueError("database_url must not be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(sqlalchemy_url(database_url))
    try:
        frames = {
            "daily_kpis": _query(engine, "analytics.mart_daily_marketplace_kpis"),
            "seller_performance": _query(engine, "analytics.mart_seller_performance"),
            "listing_funnel": _query(engine, "analytics.mart_listing_funnel"),
        }
    finally:
        engine.dispose()

    paths: dict[str, Path] = {}
    for name, frame in frames.items():
        path = output_dir / f"{name}.csv"
        frame.to_csv(path, index=False)
        paths[name] = path

    summary = build_executive_summary(frames["daily_kpis"], frames["listing_funnel"])
    summary_path = output_dir / "executive_summary.md"
    summary_path.write_text(_summary_markdown(summary), encoding="utf-8")
    paths["executive_summary"] = summary_path

    metadata_path = output_dir / "executive_summary.json"
    pd.Series(asdict(summary)).to_json(metadata_path, indent=2)
    paths["executive_summary_json"] = metadata_path
    return paths
