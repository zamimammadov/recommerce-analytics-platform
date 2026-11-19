# Operations Runbook

This runbook explains what an operator should do, not merely which code exists.
Commands should be confirmed with `make help`, because Make targets are the
public local interface.

## Normal local run

1. Copy `.env.example` to `.env` and use a local-only password.
2. Start the database and wait for its health check.
3. Initialise the schemas.
4. Generate a batch for the requested logical date.
5. Ingest the partition.
6. Run dbt snapshots, models and tests.
7. Run persisted DQ checks.
8. Review valid/rejected counts and failed checks.

For the supplied deterministic demonstration, use:

```bash
make demo
```

The demo processes two dates separately, taking a snapshot after each one,
then replays the second partition. That replay should skip all its checksums.
Use `make replay` to repeat the checksum demonstration without rebuilding models.

For a verified route that runs Python/dbt locally and only PostgreSQL in
Docker, follow [verification.md](verification.md). That page records measured
results and the features that have not received live runtime testing.

On Linux, obtain your UID/GID with `id -u` and `id -g`. If either differs from
`1000`, set `APP_UID`, `APP_GID`, and `AIRFLOW_UID` in `.env` before starting
services so bind-mounted files remain writable.

### Corporate certificate authorities

The Dockerfile accepts an optional BuildKit secret containing a trusted CA
bundle. For example, use your organisation-approved bundle with:

```bash
docker build --target app --secret id=environment_ca,src=/path/to/approved-ca-bundle.crt -t recommerce-analytics-platform-app .
docker build --target dbt --secret id=environment_ca,src=/path/to/approved-ca-bundle.crt -t recommerce-analytics-platform-dbt .
```

This is only needed when HTTPS package downloads are intercepted by a trusted
corporate proxy. Keep certificate verification enabled; do not add package
hosts to an insecure trust exception.

## Backfill procedure

Use a backfill when a delivery for date `D` arrives after later partitions or
when transformation logic must be reapplied historically.

1. Confirm the source partition and expected entity files.
2. Record why the backfill is required.
3. Ingest the missing/repaired partition with logical date `D`.
4. Run `dbt build` to rebuild the current analytical tables and observe new
   snapshot states.
5. Run the cross-table DQ checks across the loaded data.
6. Compare restated KPI values with the previous published values.
7. Record the change and completion status.

Event time remains `D`; ingestion time reflects the actual later processing.
Never rewrite the event timestamp to make a delivery appear on time.

Example commands for a missing delivery:

```bash
docker compose run --rm app ingest --input-dir data/incoming/2026-10-01
make dbt-build
make quality
make export
```

This is delivery-scoped ingestion followed by a full analytics rebuild.
Old versions delivered after a newer current version remain in raw storage,
but the current-state timestamp snapshot does not automatically reconstruct
their missing historical validity intervals. Rebuilding all historical SCD2
states would need a separate, tested recovery procedure.

## Common failures

### PostgreSQL is unavailable

**Symptom:** connection refused or health check fails.

**Action:** check container status/logs and local port conflicts. Restore the
database before retrying. Because file ingestion is transactional and
idempotent, retry the original command; do not manually delete an uncertain
partial batch without first checking the processed-file status.

### File header changed

**Symptom:** contract/header validation fails before loading rows.

**Action:** do not rename columns silently in production. Compare the new
delivery with the documented contract, decide whether it is an upstream defect
or an approved schema evolution, update code/tests/docs, then replay it.

### Invalid rows were quarantined

**Symptom:** the pipeline succeeds with rejected rows and records their reasons.

**Action:** group quarantine reasons, inspect a small sample, and determine
whether good data can still be published. Corrected rows should arrive as a
new traceable delivery; the quarantine record is retained for audit.

### dbt test failed

**Symptom:** transformation build stops at a relationship, uniqueness or custom test.

**Action:** identify the first model where the invariant breaks. Determine
whether the source is invalid, staging selected the wrong version, or the
business rule is incorrect. Fix the earliest responsible layer, rebuild its
dependants, and record the incident. Do not weaken the test only to obtain green CI.

### File resent with a different filename

**Symptom:** upstream resent byte-identical content under a new path.

**Action:** checksum idempotency should recognise it. If content differs,
treat it as a new delivery/version and validate its business keys.

### Airflow task failed

**Symptom:** a task reaches failed state after retries.

**Action:** inspect the task log and run audit row. Resolve the dependency or
data issue, then clear only the affected task instance or rerun the same CLI
for the same logical date. Do not trigger an unrelated full-history rebuild.

## Recovery principles

- Retry before delete; the pipeline is designed for replay.
- Preserve evidence of failed and rejected work.
- Separate event time from processing time.
- In this version, rebuild the analytical tables after loading the selected delivery.
- Verify business totals after technical tests pass.
- Never expose `.env` or database URLs in screenshots and issue reports.

## Operational checks after a run

- All expected entity files have completed registry entries.
- Newly inserted + duplicate/skipped row counts + rejected count reconcile to the delivery.
- Review the rejection ratio; an automatic rejection-rate gate is not implemented.
- dbt tests pass.
- Current business keys are unique.
- No required relationship is orphaned.
- Review latest source date and pipeline completion time against the target below.
- Inspect the latest audit timestamp before presenting exported metrics.

## Local service objective

Local operating targets for the daily batch:

- daily partition completes within five minutes on the documented laptop class;
- failed transient database calls are retried by orchestration;
- data published to marts has zero failed critical DQ checks;
- a missed partition can be backfilled without deleting later partitions.

Benchmark results should be recorded only after measuring them.

Structured logs, run audit rows and persisted DQ results are implemented.
External alert routing, automated freshness gating, continuous monitoring and
backup/restore automation remain deployment work; the SLA above is a target,
not a claim of measured service availability.
