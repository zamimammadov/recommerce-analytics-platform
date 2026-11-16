{% snapshot listings_snapshot %}

{{
    config(
      unique_key="listing_id",
      strategy="timestamp",
      updated_at="updated_at",
      target_schema="snapshots",
      invalidate_hard_deletes=True
    )
}}

select
    listing_id,
    seller_id,
    category,
    brand_tier,
    item_condition,
    price_eur,
    status,
    created_at,
    updated_at
from {{ ref("stg_listings") }}

{% endsnapshot %}
