"""Streamlit dashboard backed only by curated dbt marts."""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text

from recommerce.db import sqlalchemy_url

st.set_page_config(page_title="Recommerce Marketplace", page_icon="♻️", layout="wide")
st.title("Recommerce marketplace health")
st.caption("Synthetic data · Curated dbt marts · UTC reporting")


@st.cache_resource
def database_engine():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        st.error("DATABASE_URL is not configured. Copy .env.example to .env first.")
        st.stop()
    return create_engine(sqlalchemy_url(database_url))


@st.cache_data(ttl=300)
def read_relation(relation: str) -> pd.DataFrame:
    allowed = {
        "analytics.mart_daily_marketplace_kpis",
        "analytics.mart_seller_performance",
        "analytics.mart_listing_funnel",
    }
    if relation not in allowed:
        raise ValueError("Relation is not allow-listed")
    with database_engine().connect() as connection:
        return pd.read_sql_query(text(f"SELECT * FROM {relation}"), connection)  # noqa: S608


try:
    daily = read_relation("analytics.mart_daily_marketplace_kpis")
    sellers = read_relation("analytics.mart_seller_performance")
    funnel = read_relation("analytics.mart_listing_funnel")
except Exception as error:
    st.error(f"Analytics marts are unavailable: {error}")
    st.info("Run `make demo` before starting the dashboard.")
    st.stop()

if daily.empty:
    st.warning("No KPI data is available yet.")
    st.stop()

date_column = next(column for column in ("metric_date", "date_day") if column in daily)
daily[date_column] = pd.to_datetime(daily[date_column])
minimum_date = daily[date_column].min().date()
maximum_date = daily[date_column].max().date()
st.caption(f"Latest observed business date: {maximum_date} · query cache: up to 5 minutes")
selected_dates = st.sidebar.date_input(
    "Reporting period",
    value=(minimum_date, maximum_date),
    min_value=minimum_date,
    max_value=maximum_date,
)

if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
    start_date, end_date = selected_dates
    selected = daily[daily[date_column].dt.date.between(start_date, end_date)].copy()
else:
    selected = daily.copy()


def total(*columns: str) -> float:
    for column in columns:
        if column in selected:
            return float(pd.to_numeric(selected[column], errors="coerce").fillna(0).sum())
    return 0.0


completed_orders = total("completed_orders", "orders_completed")
orders = total("orders")
gmv = total("gross_merchandise_value_eur", "gmv_eur", "item_gmv_eur")
new_listings = total("new_listings")
views = total("listing_views", "views")

kpi_columns = st.columns(4)
kpi_columns[0].metric("New listings", f"{new_listings:,.0f}")
kpi_columns[1].metric("Completed orders", f"{completed_orders:,.0f}")
kpi_columns[2].metric("GMV", f"€{gmv:,.2f}")
kpi_columns[3].metric(
    "View → order",
    f"{orders / views:.2%}" if views else "n/a",
)

trend_metric = st.selectbox(
    "Daily trend",
    [
        column
        for column in (
            "new_listings",
            "listing_views",
            "views",
            "completed_orders",
            "gross_merchandise_value_eur",
            "item_gmv_eur",
        )
        if column in selected
    ],
)
st.plotly_chart(
    px.line(selected, x=date_column, y=trend_metric, markers=True),
    use_container_width=True,
)

left, right = st.columns(2)
with left:
    st.subheader("Listing funnel")
    st.caption("All observed listings; this table is independent of the date filter above.")
    st.dataframe(funnel, hide_index=True, use_container_width=True)
with right:
    st.subheader("Seller performance")
    st.caption("All observed seller history; this table is independent of the date filter above.")
    st.dataframe(sellers.head(25), hide_index=True, use_container_width=True)

with st.expander("Metric definitions"):
    st.markdown(
        """
        - **GMV:** item value of paid, shipped, or completed orders, excluding shipping.
          It is marketplace transaction volume, not company revenue.
        - **View → order:** all order records divided by listing view events.
          This is an activity ratio, not a user-level conversion probability.
        - **Sell-through:** listings with a completed order divided by observed listings.
        - All records are generated and contain no real customer information.
        """
    )
