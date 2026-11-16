-- Business questions a marketplace product/operations team could act on.
-- These queries aggregate the documented dbt metrics for presentation.
-- The category completed-order/view ratio differs from the daily all-order/view
-- activity ratio; neither is a time-ordered user conversion probability.

-- 1. How do weekly sales and new supply compare? This is not cohort sell-through.
SELECT
    date_trunc('week', metric_date)::date AS week_start,
    sum(new_listings) AS new_listings,
    sum(completed_orders) AS completed_orders,
    round(sum(item_gmv_eur), 2) AS gmv_eur,
    round(sum(completed_orders)::numeric / nullif(sum(new_listings), 0), 4)
        AS sales_to_new_supply_ratio
FROM analytics.mart_daily_marketplace_kpis
GROUP BY 1
ORDER BY 1;

-- 2. Which categories have many views relative to observed completed orders?
SELECT
    category,
    sum(view_count) AS listing_views,
    sum(favorite_count) AS favorites,
    sum(message_count) AS messages,
    sum(completed_order_count) AS completed_orders,
    round(sum(completed_order_count)::numeric / nullif(sum(view_count), 0), 4)
        AS view_to_order_rate
FROM analytics.mart_listing_funnel
GROUP BY category
HAVING sum(view_count) >= 100
ORDER BY view_to_order_rate ASC, listing_views DESC;

-- 3. Which sellers combine healthy conversion with dependable fulfilment?
SELECT
    seller_id,
    active_listing_count,
    sold_listing_count,
    item_gmv_eur,
    listing_sell_through_rate
FROM analytics.mart_seller_performance
WHERE sold_listing_count >= 3
ORDER BY listing_sell_through_rate DESC, item_gmv_eur DESC
LIMIT 25;

-- 4. Is time-to-sale improving by category and condition?
SELECT
    category,
    item_condition,
    count(*) AS sold_listings,
    round(avg(hours_to_sale), 1) AS average_time_to_sale_hours,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY hours_to_sale)
        AS median_time_to_sale_hours
FROM analytics.mart_listing_funnel
WHERE reached_completed_stage
GROUP BY 1, 2
HAVING count(*) >= 5
ORDER BY median_time_to_sale_hours;

-- 5. Data-product reconciliation: does mart GMV equal the order fact?
WITH fact AS (
    SELECT order_at::date AS metric_date,
           sum(item_price_eur) AS gmv_eur
    FROM analytics.fct_orders
    WHERE is_gmv_eligible
    GROUP BY 1
), mart AS (
    SELECT metric_date, item_gmv_eur AS gmv_eur
    FROM analytics.mart_daily_marketplace_kpis
)
SELECT
    coalesce(fact.metric_date, mart.metric_date) AS metric_date,
    fact.gmv_eur AS fact_gmv_eur,
    mart.gmv_eur AS mart_gmv_eur,
    coalesce(fact.gmv_eur, 0) - coalesce(mart.gmv_eur, 0) AS difference_eur
FROM fact
FULL JOIN mart USING (metric_date)
WHERE coalesce(fact.gmv_eur, 0) <> coalesce(mart.gmv_eur, 0)
ORDER BY 1;
