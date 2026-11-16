{{ config(tags=["daily", "fact"]) }}

select
    o.order_id,
    md5(o.listing_id) as listing_key,
    o.listing_id,
    md5(o.buyer_id) as buyer_key,
    o.buyer_id,
    md5(o.seller_id) as seller_key,
    o.seller_id,
    o.order_at,
    to_char(o.order_at::date, 'YYYYMMDD')::integer as order_date_key,
    o.item_price_eur,
    o.shipping_eur,
    o.item_price_eur + o.shipping_eur as total_paid_eur,
    o.payment_method,
    o.order_status,
    o.order_status in ('paid', 'shipped', 'completed') as is_gmv_eligible,
    o.order_status = 'completed' as is_completed,
    o.updated_at
from {{ ref("stg_orders") }} o
