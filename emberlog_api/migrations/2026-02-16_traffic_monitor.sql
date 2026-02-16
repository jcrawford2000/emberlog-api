CREATE TABLE IF NOT EXISTS tr_decode_rate_latest (
    instance_id TEXT NOT NULL,
    sys_num INTEGER NOT NULL,
    sys_name TEXT NOT NULL,

    decoderate_raw DOUBLE PRECISION NOT NULL,
    decoderate_pct DOUBLE PRECISION NOT NULL,

    decoderate_interval_s DOUBLE PRECISION,
    control_channel_hz BIGINT,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (instance_id, sys_num)
);

CREATE INDEX IF NOT EXISTS idx_tr_decode_rate_latest_sys_name
    ON tr_decode_rate_latest (sys_name);

CREATE TABLE IF NOT EXISTS tr_recorders_snapshot_latest (
    instance_id TEXT PRIMARY KEY,

    recorders_json JSONB NOT NULL,

    total_count INTEGER NOT NULL,
    recording_count INTEGER NOT NULL,
    idle_count INTEGER NOT NULL,
    available_count INTEGER NOT NULL,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tr_calls_active_snapshot_latest (
    instance_id TEXT PRIMARY KEY,

    calls_json JSONB NOT NULL,
    active_calls_count INTEGER NOT NULL,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
