# Glossary

| Term | Plain-language meaning | Example in this project |
|---|---|---|
| Batch | Records processed together on a schedule | Files under one logical date |
| Business key | Stable identifier from the source domain | `listing_id` |
| Data contract | Agreed schema and rules between producer and consumer | Required columns and allowed listing statuses |
| Event time | When the business event actually happened | `order_at` |
| Processing time | When the platform handled the record | ingestion timestamp |
| Grain | What exactly one table row represents | One immutable event in the event fact |
| Idempotent | Safe to repeat without multiplying the result | Reingesting an identical checksum |
| Incremental load | Process only new or changed input | Daily partition ingestion |
| Late-arriving data | Data delivered after its business date | Monday order received on Thursday |
| Backfill | Process or recompute a historical period | Rebuild Monday after the late file |
| Quarantine | Separate storage for invalid records | Negative listing price plus reason |
| Lineage | Where a value came from and how it changed | Source file → raw → staging → mart |
| SCD Type 2 | Preserve old and current versions of changing attributes | Listing price/status history |
| Snapshot | dbt mechanism that records historical versions | Listing state changes |
| Fact | Measurable event at a declared grain | Order or marketplace event |
| Dimension | Descriptive entity used to slice facts | User or listing |
| Mart | Business-ready model for repeated analysis | Daily marketplace KPIs |
| DQ | Data quality | Uniqueness and relationship checks |
| SLA/SLO | Expected service level/objective | Daily batch completes within a target |
| Retry | Repeat a failed task after a delay | Temporary database connection failure |
| Recovery | Restore correct processing after failure | Replay same logical date safely |
| CI | Automatic checks on each code change | Ruff and pytest in GitHub Actions |
| IaC | Infrastructure declared as versioned code | Possible future Terraform deployment |
