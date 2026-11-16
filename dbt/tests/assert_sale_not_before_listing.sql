select listing_id, created_at, first_sale_at
from {{ ref("mart_listing_funnel") }}
where first_sale_at < created_at
