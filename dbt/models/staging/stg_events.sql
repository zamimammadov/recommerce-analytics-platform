{{ config(tags=["daily", "staging"]) }}

with ranked as (
    select
        event_id,
        listing_id,
        user_id,
        session_id,
        lower(event_type) as event_type,
        event_at,
        source_file,
        run_id,
        ingested_at,
        row_number() over (
            partition by event_id
            order by ingested_at desc, row_hash desc
        ) as version_rank
    from {{ source("raw", "events") }}
)

select *
from ranked
where version_rank = 1
