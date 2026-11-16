with fact_total as (
    select coalesce(sum(item_price_eur) filter (where is_gmv_eligible), 0) as item_gmv_eur
    from {{ ref("fct_orders") }}
),
mart_total as (
    select coalesce(sum(item_gmv_eur), 0) as item_gmv_eur
    from {{ ref("mart_daily_marketplace_kpis") }}
)

select
    f.item_gmv_eur as fact_item_gmv_eur,
    m.item_gmv_eur as mart_item_gmv_eur
from fact_total f
cross join mart_total m
where abs(f.item_gmv_eur - m.item_gmv_eur) > 0.01
