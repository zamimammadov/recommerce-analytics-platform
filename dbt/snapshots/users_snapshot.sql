{% snapshot users_snapshot %}

{{
    config(
      unique_key="user_id",
      strategy="timestamp",
      updated_at="updated_at",
      target_schema="snapshots",
      invalidate_hard_deletes=True
    )
}}

select
    user_id,
    country_code,
    signup_at,
    acquisition_channel,
    is_business,
    updated_at
from {{ ref("stg_users") }}

{% endsnapshot %}
