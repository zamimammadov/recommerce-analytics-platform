select
    seller_id,
    listing_sell_through_rate,
    view_to_sale_rate
from {{ ref("mart_seller_performance") }}
where listing_sell_through_rate not between 0 and 1
   or view_to_sale_rate not between 0 and 1
