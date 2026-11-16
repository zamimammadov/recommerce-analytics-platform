{{ config(tags=["daily", "product_analytics"]) }}

with event_counts as (
    select
        listing_id,
        count(*) filter (where event_type = 'view') as view_count,
        count(distinct user_id) filter (where event_type = 'view') as unique_viewer_count,
        count(*) filter (where event_type = 'favorite') as favorite_count,
        count(*) filter (where event_type = 'message') as message_count,
        min(event_at) filter (where event_type = 'view') as first_view_at
    from {{ ref("fct_listing_events") }}
    group by listing_id
),
order_outcomes as (
    select
        listing_id,
        count(*) as order_count,
        count(*) filter (where is_completed) as completed_order_count,
        min(order_at) filter (where is_gmv_eligible) as first_sale_at,
        sum(item_price_eur) filter (where is_gmv_eligible) as item_gmv_eur
    from {{ ref("fct_orders") }}
    group by listing_id
)

select
    l.listing_id,
    l.seller_id,
    u.country_code as seller_country_code,
    l.category,
    l.brand_tier,
    l.item_condition,
    l.price_eur as current_price_eur,
    l.status as current_status,
    l.created_at,
    coalesce(e.view_count, 0) as view_count,
    coalesce(e.unique_viewer_count, 0) as unique_viewer_count,
    coalesce(e.favorite_count, 0) as favorite_count,
    coalesce(e.message_count, 0) as message_count,
    coalesce(o.order_count, 0) as order_count,
    coalesce(o.completed_order_count, 0) as completed_order_count,
    e.first_view_at,
    o.first_sale_at,
    case
        when o.first_sale_at is not null
        then extract(epoch from (o.first_sale_at - l.created_at)) / 3600.0
    end as hours_to_sale,
    coalesce(o.item_gmv_eur, 0)::numeric(14, 2) as item_gmv_eur,
    coalesce(e.view_count, 0) > 0 as reached_view_stage,
    coalesce(e.favorite_count, 0) > 0 as reached_favorite_stage,
    coalesce(e.message_count, 0) > 0 as reached_message_stage,
    coalesce(o.order_count, 0) > 0 as reached_order_stage,
    coalesce(o.completed_order_count, 0) > 0 as reached_completed_stage
from {{ ref("dim_listings") }} l
left join event_counts e using (listing_id)
left join order_outcomes o using (listing_id)
left join {{ ref("dim_users") }} u on l.seller_id = u.user_id
