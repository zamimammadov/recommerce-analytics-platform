select listing_id
from {{ ref("listings_snapshot") }}
where dbt_valid_to is null
group by listing_id
having count(*) > 1
