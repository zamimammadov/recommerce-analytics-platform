# Analytics model

The dbt graph deliberately separates four responsibilities:

- `staging`: deduplicates append-only raw versions and standardises values.
- `snapshots`: records SCD Type 2 history for mutable users and listings.
- `core`: stable dimensions and facts with reusable keys and definitions.
- `marts`: business-facing funnel, seller, and daily marketplace metrics.

The daily KPI mart does not label `completed_orders / new_listings` as a
sell-through rate because those records belong to different cohorts. Cohort
sell-through is instead calculated at listing level in `mart_listing_funnel`
and aggregated in `mart_seller_performance`.
