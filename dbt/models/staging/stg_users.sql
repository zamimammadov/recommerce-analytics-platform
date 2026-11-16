{{ config(tags=["daily", "staging"]) }}

with ranked as (
    select
        user_id,
        upper(country_code) as country_code,
        signup_at,
        lower(acquisition_channel) as acquisition_channel,
        is_business,
        updated_at,
        source_file,
        run_id,
        ingested_at,
        row_number() over (
            partition by user_id
            order by updated_at desc, ingested_at desc, row_hash desc
        ) as version_rank
    from {{ source("raw", "users") }}
)

select *
from ranked
where version_rank = 1
