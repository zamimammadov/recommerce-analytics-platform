# Interview Guide

## 60-second explanation

> I built an original batch data platform for a synthetic second-hand
> marketplace. A deterministic generator creates daily user, listing, event
> and order files. Python validates and loads them to PostgreSQL, preserving
> lineage and quarantining invalid rows. A file checksum and stable record keys
> make retries idempotent. dbt builds staging models, SCD Type 2 history and
> business marts, with tests for the analytical contracts. Airflow schedules
> the same CLI and supports retries and backfills. I focused on reproducibility
> and failure recovery rather than adding tools that the workload did not need.

Use that only after every stated feature works in the checked-out version.

## Strong follow-up answers

### Why did you not use pandas for ingestion?

The loader streams rows so memory usage does not grow with the complete file.
pandas is used after SQL aggregation, where its ergonomics help analysis and
the result size is appropriate.

### How is the pipeline idempotent?

It stores a file checksum and does not repeat a completed delivery. Stable
record/version constraints provide a second guard if identical business
records arrive under another filename. The complete file load is transactional.

### What is the difference between late data and a retry?

A retry repeats processing for input already expected at that time. Late data
is newly available input whose event time belongs to an earlier period. It may
require rebuilding downstream windows even though the earlier run succeeded.

### Why SCD Type 2?

Listings change price and status. Overwriting the row would answer only “what
is true now?” A snapshot after each batch preserves the versions observed over
those runs. This project stores the history separately; its analytical facts
still use current dimensions. It does not reconstruct versions missed between
snapshots or automatically provide historical as-of dimension attribution.

### What happens to invalid records?

They do not silently disappear and do not contaminate analytics. The loader
stores the source context, payload and validation reason in quarantine, and
the run audit records accepted/rejected counts.

### Why no Kafka or Kubernetes?

The requirement is a daily batch on a local reproducible environment. Kafka
would add streaming operations without a latency requirement; Kubernetes would
add cluster operations without a scaling or availability problem. I documented
the conditions under which each would become justified.

### How would you move it to production?

I would first clarify volume, freshness, recovery and security requirements.
Then I would use managed PostgreSQL/warehouse and object storage, workload
identity plus a secrets manager, encrypted networking, backup/restore testing,
central logs/metrics/alerts, controlled schema migrations, IaC and separate
environments. I would not claim that Docker Compose itself is production HA.

## Demonstration order

1. Explain the business decision and metric definition.
2. Show the source contract and one intentionally bad record.
3. Run the pipeline and show raw, quarantine and audit counts.
4. Repeat the same run to prove idempotency.
5. Show a historical listing change in the SCD2 snapshot.
6. Show dbt lineage/tests and one business mart.
7. Explain how to backfill a late order.
8. Finish with trade-offs and one measured next improvement.

This is stronger than beginning with a list of technologies.

## Claims to avoid

- Do not call the synthetic findings real marketplace insights.
- Do not call Docker Compose a highly available production deployment.
- Do not claim millions of records unless the benchmark actually ran.
- Do not claim production ownership from a personal portfolio project.
- Do not describe a planned feature as implemented.
- Do not claim the observed listing-stage flags are an ordered user funnel.
- Do not claim N-day cohort sell-through or historical active inventory is implemented.
- Explain AI assistance honestly and demonstrate the code changes you understand.

## Questions to ask the interviewer

- How do you separate ingestion contracts from analytical contracts?
- How are late data and historical restatements communicated to stakeholders?
- What are the most important reliability signals for your pipelines?
- How do analysts and engineers agree on metric definitions?
- Which parts of the platform currently create the highest operational cost?
