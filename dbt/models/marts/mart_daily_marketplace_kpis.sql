{{ config(tags=["daily", "executive_kpi"]) }}

with listings as (
    select
        created_at::date as metric_date,
        count(*) as new_listings,
        count(distinct seller_id) as listing_sellers
    from {{ ref("dim_listings") }}
    group by 1
),
events as (
    select
        event_at::date as metric_date,
        count(*) filter (where event_type = 'view') as views,
        count(*) filter (where event_type = 'favorite') as favorites,
        count(*) filter (where event_type = 'message') as messages,
        count(distinct user_id) filter (where event_type = 'view') as unique_viewers
    from {{ ref("fct_listing_events") }}
    group by 1
),
orders as (
    select
        order_at::date as metric_date,
        count(*) as orders,
        count(*) filter (where is_gmv_eligible) as gmv_eligible_orders,
        count(*) filter (where is_completed) as completed_orders,
        count(distinct buyer_id) as ordering_buyers,
        sum(item_price_eur) filter (where is_gmv_eligible) as item_gmv_eur,
        sum(total_paid_eur) filter (where is_gmv_eligible) as total_paid_eur
    from {{ ref("fct_orders") }}
    group by 1
),
activity_dates as (
    select metric_date from listings
    union all
    select metric_date from events
    union all
    select metric_date from orders
),
activity_bounds as (
    select min(metric_date) as min_date, max(metric_date) as max_date
    from activity_dates
),
date_spine as (
    select d.date_day as metric_date
    from {{ ref("dim_date") }} d
    cross join activity_bounds b
    where d.date_day between b.min_date and b.max_date
)

select
    d.metric_date,
    coalesce(l.new_listings, 0) as new_listings,
    coalesce(l.listing_sellers, 0) as listing_sellers,
    coalesce(e.views, 0) as views,
    coalesce(e.favorites, 0) as favorites,
    coalesce(e.messages, 0) as messages,
    coalesce(e.unique_viewers, 0) as unique_viewers,
    coalesce(o.orders, 0) as orders,
    coalesce(o.gmv_eligible_orders, 0) as gmv_eligible_orders,
    coalesce(o.completed_orders, 0) as completed_orders,
    coalesce(o.ordering_buyers, 0) as ordering_buyers,
    coalesce(o.item_gmv_eur, 0)::numeric(14, 2) as item_gmv_eur,
    coalesce(o.total_paid_eur, 0)::numeric(14, 2) as total_paid_eur,
    (
        o.item_gmv_eur / nullif(o.gmv_eligible_orders, 0)
    )::numeric(12, 2) as average_order_value_eur,
    (o.orders::numeric / nullif(e.views, 0))::numeric(8, 4) as view_to_order_rate,
    (e.favorites::numeric / nullif(e.views, 0))::numeric(8, 4) as view_to_favorite_rate,
    (
        o.completed_orders::numeric / nullif(o.orders, 0)
    )::numeric(8, 4) as order_completion_rate
from date_spine d
left join listings l using (metric_date)
left join events e using (metric_date)
left join orders o using (metric_date)
order by d.metric_date
