{{ config(tags=["daily", "dimension"]) }}

select
    md5(user_id) as user_key,
    user_id,
    country_code,
    signup_at,
    acquisition_channel,
    is_business,
    updated_at
from {{ ref("stg_users") }}
