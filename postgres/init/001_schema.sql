CREATE TABLE IF NOT EXISTS download_events (
    id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    peer_username TEXT NOT NULL,
    peer_ip INET,
    country_code TEXT,
    country_name TEXT,
    file_path TEXT,
    bytes_transferred BIGINT,
    transfer_direction TEXT NOT NULL DEFAULT 'upload_from_me'
);

CREATE INDEX IF NOT EXISTS idx_download_events_occurred_at
    ON download_events (occurred_at);

CREATE INDEX IF NOT EXISTS idx_download_events_country_code
    ON download_events (country_code);

CREATE INDEX IF NOT EXISTS idx_download_events_peer_ip
    ON download_events (peer_ip);
