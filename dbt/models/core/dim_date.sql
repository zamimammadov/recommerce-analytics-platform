{{ config(tags=["daily", "dimension"]) }}

with bounds as (
    select
        least(
            coalesce((select min(signup_at)::date from {{ ref("stg_users") }}), current_date),
            coalesce((select min(created_at)::date from {{ ref("stg_listings") }}), current_date),
            coalesce((select min(event_at)::date from {{ ref("stg_events") }}), current_date),
            coalesce((select min(order_at)::date from {{ ref("stg_orders") }}), current_date)
        ) as min_date,
        greatest(
            coalesce((select max(signup_at)::date from {{ ref("stg_users") }}), current_date),
            coalesce((select max(created_at)::date from {{ ref("stg_listings") }}), current_date),
            coalesce((select max(event_at)::date from {{ ref("stg_events") }}), current_date),
            coalesce((select max(order_at)::date from {{ ref("stg_orders") }}), current_date)
        ) as max_date
),
dates as (
    select generate_series(min_date, max_date, interval '1 day')::date as date_day
    from bounds
)

select
    to_char(date_day, 'YYYYMMDD')::integer as date_key,
    date_day,
    extract(isodow from date_day)::smallint as iso_day_of_week,
    trim(to_char(date_day, 'Day')) as day_name,
    extract(week from date_day)::smallint as week_of_year,
    extract(month from date_day)::smallint as month_number,
    trim(to_char(date_day, 'Month')) as month_name,
    extract(quarter from date_day)::smallint as quarter_number,
    extract(year from date_day)::smallint as year_number,
    (extract(isodow from date_day) in (6, 7)) as is_weekend
from dates
