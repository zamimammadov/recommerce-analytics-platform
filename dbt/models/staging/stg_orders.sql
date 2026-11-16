{{ config(tags=["daily", "staging"]) }}

with ranked as (
    select
        order_id,
        listing_id,
        buyer_id,
        seller_id,
        order_at,
        item_price_eur,
        shipping_eur,
        lower(payment_method) as payment_method,
        lower(order_status) as order_status,
        updated_at,
        source_file,
        run_id,
        ingested_at,
        row_number() over (
            partition by order_id
            order by updated_at desc, ingested_at desc, row_hash desc
        ) as version_rank
    from {{ source("raw", "orders") }}
)

select *
from ranked
where version_rank = 1
