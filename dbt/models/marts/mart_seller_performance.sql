{{ config(tags=["daily", "marketplace_operations"]) }}

select
    seller_id,
    seller_country_code,
    count(*) as listing_count,
    count(*) filter (where current_status = 'active') as active_listing_count,
    count(*) filter (where reached_completed_stage) as sold_listing_count,
    sum(view_count) as total_views,
    sum(favorite_count) as total_favorites,
    sum(message_count) as total_messages,
    sum(item_gmv_eur)::numeric(14, 2) as item_gmv_eur,
    avg(hours_to_sale) filter (where reached_completed_stage)::numeric(12, 2) as avg_hours_to_sale,
    (
        count(*) filter (where reached_completed_stage)::numeric
        / nullif(count(*), 0)
    )::numeric(8, 4) as listing_sell_through_rate,
    (
        count(*) filter (where reached_completed_stage)::numeric
        / nullif(sum(view_count), 0)
    )::numeric(8, 4) as view_to_sale_rate
from {{ ref("mart_listing_funnel") }}
group by seller_id, seller_country_code
