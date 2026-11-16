select listing_id
from {{ ref("mart_listing_funnel") }}
where reached_completed_stage and not reached_order_stage
