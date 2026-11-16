{% macro postgres__snapshot_get_time() -%}
  {# Keep dbt metadata aligned with the UTC timestamptz source contract. #}
  now()::timestamptz
{%- endmacro %}
