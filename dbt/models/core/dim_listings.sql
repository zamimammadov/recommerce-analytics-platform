{{ config(tags=["daily", "dimension"]) }}

select
    md5(listing_id) as listing_key,
    listing_id,
    md5(seller_id) as seller_key,
    seller_id,
    category,
    brand_tier,
    item_condition,
    price_eur,
    status,
    created_at,
    updated_at
from {{ ref("stg_listings") }}
