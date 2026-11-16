CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS quarantine;
CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS snapshots;

CREATE TABLE IF NOT EXISTS ops.pipeline_runs (
    run_id UUID PRIMARY KEY,
    pipeline_name TEXT NOT NULL,
    source_path TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    files_seen INTEGER NOT NULL DEFAULT 0 CHECK (files_seen >= 0),
    files_loaded INTEGER NOT NULL DEFAULT 0 CHECK (files_loaded >= 0),
    files_skipped INTEGER NOT NULL DEFAULT 0 CHECK (files_skipped >= 0),
    rows_accepted BIGINT NOT NULL DEFAULT 0 CHECK (rows_accepted >= 0),
    rows_quarantined BIGINT NOT NULL DEFAULT 0 CHECK (rows_quarantined >= 0),
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS ops.processed_files (
    entity TEXT NOT NULL CHECK (entity IN ('users', 'listings', 'events', 'orders')),
    file_checksum CHAR(64) NOT NULL,
    source_path TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL CHECK (file_size_bytes >= 0),
    row_count BIGINT NOT NULL CHECK (row_count >= 0),
    accepted_count BIGINT NOT NULL CHECK (accepted_count >= 0),
    quarantined_count BIGINT NOT NULL CHECK (quarantined_count >= 0),
    processed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_id UUID NOT NULL REFERENCES ops.pipeline_runs(run_id),
    PRIMARY KEY (entity, file_checksum)
);

CREATE TABLE IF NOT EXISTS ops.data_quality_results (
    result_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id UUID REFERENCES ops.pipeline_runs(run_id),
    check_name TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('warning', 'error')),
    status TEXT NOT NULL CHECK (status IN ('pass', 'fail')),
    observed_value NUMERIC,
    threshold TEXT,
    details JSONB NOT NULL DEFAULT '{}'::JSONB,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quarantine.invalid_records (
    quarantine_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ops.pipeline_runs(run_id),
    source_file TEXT NOT NULL,
    entity TEXT NOT NULL,
    row_number BIGINT NOT NULL CHECK (row_number >= 2),
    raw_payload JSONB NOT NULL,
    error_reasons TEXT[] NOT NULL,
    quarantined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw.users (
    user_id TEXT NOT NULL,
    country_code CHAR(2) NOT NULL,
    signup_at TIMESTAMPTZ NOT NULL,
    acquisition_channel TEXT NOT NULL,
    is_business BOOLEAN NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    source_file TEXT NOT NULL,
    row_hash CHAR(64) NOT NULL UNIQUE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_id UUID NOT NULL REFERENCES ops.pipeline_runs(run_id),
    UNIQUE (user_id, updated_at)
);

CREATE TABLE IF NOT EXISTS raw.listings (
    listing_id TEXT NOT NULL,
    seller_id TEXT NOT NULL,
    category TEXT NOT NULL,
    brand_tier TEXT NOT NULL,
    item_condition TEXT NOT NULL,
    price_eur NUMERIC(12, 2) NOT NULL CHECK (price_eur > 0),
    status TEXT NOT NULL CHECK (status IN ('active', 'reserved', 'sold', 'removed')),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    source_file TEXT NOT NULL,
    row_hash CHAR(64) NOT NULL UNIQUE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_id UUID NOT NULL REFERENCES ops.pipeline_runs(run_id),
    UNIQUE (listing_id, updated_at)
);

CREATE TABLE IF NOT EXISTS raw.events (
    event_id TEXT NOT NULL UNIQUE,
    listing_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('view', 'favorite', 'message', 'price_drop')),
    event_at TIMESTAMPTZ NOT NULL,
    source_file TEXT NOT NULL,
    row_hash CHAR(64) NOT NULL UNIQUE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_id UUID NOT NULL REFERENCES ops.pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS raw.orders (
    order_id TEXT NOT NULL,
    listing_id TEXT NOT NULL,
    buyer_id TEXT NOT NULL,
    seller_id TEXT NOT NULL,
    order_at TIMESTAMPTZ NOT NULL,
    item_price_eur NUMERIC(12, 2) NOT NULL CHECK (item_price_eur > 0),
    shipping_eur NUMERIC(12, 2) NOT NULL CHECK (shipping_eur >= 0),
    payment_method TEXT NOT NULL,
    order_status TEXT NOT NULL CHECK (
        order_status IN ('created', 'paid', 'shipped', 'completed', 'cancelled', 'refunded')
    ),
    updated_at TIMESTAMPTZ NOT NULL,
    source_file TEXT NOT NULL,
    row_hash CHAR(64) NOT NULL UNIQUE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_id UUID NOT NULL REFERENCES ops.pipeline_runs(run_id),
    UNIQUE (order_id, updated_at)
);

CREATE INDEX IF NOT EXISTS idx_raw_users_user_id ON raw.users (user_id);
CREATE INDEX IF NOT EXISTS idx_raw_listings_listing_id ON raw.listings (listing_id);
CREATE INDEX IF NOT EXISTS idx_raw_listings_seller_id ON raw.listings (seller_id);
CREATE INDEX IF NOT EXISTS idx_raw_events_listing_time ON raw.events (listing_id, event_at);
CREATE INDEX IF NOT EXISTS idx_raw_orders_order_id ON raw.orders (order_id);
CREATE INDEX IF NOT EXISTS idx_raw_orders_listing_id ON raw.orders (listing_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_run_id ON quarantine.invalid_records (run_id);

-- Additive migrations keep an existing local demo database usable.
ALTER TABLE ops.pipeline_runs
    ADD COLUMN IF NOT EXISTS rows_duplicate BIGINT NOT NULL DEFAULT 0;
ALTER TABLE ops.processed_files
    ADD COLUMN IF NOT EXISTS duplicate_count BIGINT NOT NULL DEFAULT 0;
