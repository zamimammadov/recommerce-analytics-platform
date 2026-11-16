select order_id, buyer_id, seller_id
from {{ ref("fct_orders") }}
where buyer_id = seller_id
