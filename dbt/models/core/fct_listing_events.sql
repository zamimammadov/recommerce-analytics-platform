{{ config(tags=["daily", "fact"]) }}

select
    e.event_id,
    md5(e.listing_id) as listing_key,
    e.listing_id,
    case when e.user_id is not null then md5(e.user_id) end as user_key,
    e.user_id,
    e.session_id,
    e.event_type,
    e.event_at,
    to_char(e.event_at::date, 'YYYYMMDD')::integer as event_date_key
from {{ ref("stg_events") }} e
