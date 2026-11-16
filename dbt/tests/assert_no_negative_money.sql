select order_id, item_price_eur, shipping_eur
from {{ ref("fct_orders") }}
where item_price_eur <= 0
   or shipping_eur < 0
