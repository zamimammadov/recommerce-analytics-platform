# Architecture Trade-offs

Good engineering is not the maximum number of logos. Each component must earn
its operational cost.

## Why PostgreSQL?

The portfolio workload fits comfortably on one relational engine, and the
target roles value SQL/PostgreSQL. PostgreSQL provides transactions, numeric
types, constraints, query plans and schemas while keeping the project locally
reproducible.

**Trade-off:** it is not an elastic analytical warehouse. At materially larger
scale, marts could move to BigQuery, Snowflake or Redshift while operational
metadata remains relational.

## Why dbt?

Transformation logic becomes versioned SQL with lineage, tests and generated
documentation. It cleanly separates ingestion from business modelling.

**Trade-off:** dbt is not an ingestion or general workflow engine. Python and
Airflow keep those responsibilities.

## Why Airflow?

The project needs ordered batch steps, retry and historical backfill. Airflow
makes those behaviours explicit and is common in data-engineering teams.

**Trade-off:** it adds services and metadata. The CLI remains usable without
Airflow so that orchestration never becomes the only way to test business code.

## Why not Kafka?

The stated input is a daily file delivery. Adding Kafka would not make that
batch contract real-time; it would create brokers, schemas, offsets and failure
modes without a business latency requirement.

Kafka becomes justified if the product requires second/minute latency, events
are naturally emitted continuously, and downstream consumers need independent
replayable subscriptions.

## Why not Kubernetes?

The MVP runs on one developer machine. Docker Compose already supplies
repeatable services and health checks. Kubernetes would add manifests,
networking, storage, secrets and cluster operations without solving a measured
scheduling or scaling constraint.

Kubernetes becomes reasonable when multiple independently scaled workloads,
high availability, workload isolation or an existing organisational platform
justify its operational cost.

## Why CSV rather than an API?

File-based batch ingestion makes logical partitions, replays, checksums and
late delivery easy to demonstrate. Those are core data-engineering behaviours.

**Trade-off:** CSV has weak typing and no nested schema. A production evolution
could use Parquet in object storage with an explicit schema registry or data contract.

## Why synthetic data?

Synthetic data removes privacy and redistribution risk and lets tests inject
known failure scenarios deterministically.

**Trade-off:** generated behaviour is never proof of actual marketplace
behaviour. Analytical findings demonstrate method, not real commercial insight.

## Why pandas only after modelling?

SQL engines efficiently filter and aggregate relational data. pandas is used
for result-sized analysis and presentation, rather than copying complete raw
tables into memory.

This deliberately demonstrates choosing a tool by workload instead of using
pandas for every step.

## Planned evolution, if evidence justifies it

1. Measure ingestion/query performance and add indexes or partitioning based on plans.
2. Add object storage when file retention and volume require it.
3. Add cloud IaC after selecting one concrete deployment target.
4. Add event streaming only for a defined low-latency use case.

These are extensions, not claims about the current MVP.
