{{ config(tags=["daily", "staging"]) }}

with ranked as (
    select
        listing_id,
        seller_id,
        lower(category) as category,
        lower(brand_tier) as brand_tier,
        lower(item_condition) as item_condition,
        price_eur,
        lower(status) as status,
        created_at,
        updated_at,
        source_file,
        run_id,
        ingested_at,
        row_number() over (
            partition by listing_id
            order by updated_at desc, ingested_at desc, row_hash desc
        ) as version_rank
    from {{ source("raw", "listings") }}
)

select *
from ranked
where version_rank = 1
