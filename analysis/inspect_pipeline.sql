-- Run after the two-day demo. All timestamps are UTC.

-- 1. What did each run do? Replay should have zero accepted rows.
SELECT started_at, status, files_loaded, files_skipped,
       rows_accepted, rows_quarantined, rows_duplicate
FROM ops.pipeline_runs
ORDER BY started_at DESC
LIMIT 10;

-- 2. Do observed file rows reconcile to all possible outcomes?
SELECT entity, source_path, row_count, accepted_count, quarantined_count, duplicate_count,
       row_count = accepted_count + quarantined_count + duplicate_count AS reconciled
FROM ops.processed_files
ORDER BY source_path;

-- 3. Why were rows rejected? Original payloads remain available for correction.
SELECT entity, reason, count(*) AS rejected_rows
FROM quarantine.invalid_records
CROSS JOIN LATERAL unnest(error_reasons) AS reason
GROUP BY entity, reason
ORDER BY rejected_rows DESC, entity;

-- 4. Show the old and current price of one updated listing.
WITH changed_listing AS (
    SELECT listing_id
    FROM snapshots.listings_snapshot
    GROUP BY listing_id
    HAVING count(*) > 1
    ORDER BY listing_id
    LIMIT 1
)
SELECT listing_id, price_eur, status, dbt_valid_from, dbt_valid_to,
       dbt_valid_to IS NULL AS is_current
FROM snapshots.listings_snapshot
JOIN changed_listing USING (listing_id)
ORDER BY dbt_valid_from;

-- 5. Event time differs from processing time for late/historical inputs.
-- The source path identifies delivery day; ingested_at is the actual load time.
SELECT event_id, event_at, ingested_at, source_file
FROM raw.events
WHERE event_at::date < substring(source_file FROM '(\d{4}-\d{2}-\d{2})')::date
ORDER BY event_at
LIMIT 5;

-- 6. Quality results are stored independently of console output.
SELECT check_name, severity, status, observed_value, checked_at
FROM ops.data_quality_results
ORDER BY checked_at DESC
LIMIT 6;
