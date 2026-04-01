# Nicotine+ Upload Geo Plugin

This plugin records completed uploads from your Nicotine+ client to PostgreSQL.

## What it stores

- Peer username
- Peer IP address
- Country code/name
- File path
- Bytes transferred
- Timestamp

## Settings

Configure in Nicotine+ plugin settings:

- `db_host`: PostgreSQL IP/hostname
- `db_port`: PostgreSQL port (default `5432`)
- `db_name`: PostgreSQL database name
- `db_user`: PostgreSQL username
- `db_password`: PostgreSQL password
- `db_sslmode`: PostgreSQL SSL mode (`prefer` by default)
- `geoip_online_url_template`: primary online lookup; default `https://ipwho.is/{ip}`; must include `{ip}`
- `geoip_online_url_template_backup`: second provider if primary fails or returns no country; default ip-api.com (HTTP); clear to disable
- `geoip_online_timeout_seconds`: HTTP timeout per request
- `geoip_resolve_wait_seconds`: Seconds to wait before a second pass (default `0.8`). Nicotine+ often delivers `user_resolve_notification` **after** `upload_finished_notification`; the worker uses this delay so the peer IP can land in cache before lookup.
- `geoip_online_retry_count`: Extra full lookup rounds after HTTP/API failure (default `2`, i.e. three attempts total with spacing).
- `geoip_online_retry_delay_seconds`: Pause between those retries (default `0.5`)
- `unknown_country_name`: Fallback display name for unknown country
- `backfill_enabled`: If true, a **second background thread** periodically `UPDATE`s old rows where `peer_ip` is set but country is still unknown (`country_code` NULL or `country_name` matches `unknown_country_name`, case-insensitive). **Runs only while Nicotine+ is open.**
- `backfill_interval_seconds`: Seconds between batches (default `3600`, min `30`)
- `backfill_batch_limit`: Max rows per batch (default `50`, max `500`)
- `backfill_sleep_seconds`: Delay between geo API calls within a batch (default `0.3`) to respect free API limits

Enable `backfill_enabled` **before** loading the plugin (or disable/re-enable the plugin) so the backfill thread starts. Turning it on later may require a plugin reload depending on Nicotine+ behavior.

## Periodic backfill

Eligible rows: `peer_ip IS NOT NULL` and (`country_code IS NULL` OR trimmed lower `country_name` equals trimmed lower `unknown_country_name`). Oldest rows first (`ORDER BY occurred_at ASC`).

Each row uses the same online lookup chain as uploads (`_country_from_online_ip_with_retries`: primary URL, backup URL, retries). Rows without a resolvable public IP stay unchanged.

## Country resolution logic

When an upload finishes, the plugin queues an event. **Before each database insert**, a background worker:

1. Refreshes `peer_ip` from the resolve cache and `core.users` (same sources as at notify time).
2. Runs online geo lookup (primary URL, then backup) with configurable retries.
3. Falls back to Nicotine country metadata from cache / user object if still missing.
4. If `peer_ip` or `country_code` is still missing after step 1–3, waits `geoip_resolve_wait_seconds` and repeats steps 1–3 once.

This reduces NULL `country_code` / “Unknown” rows caused by timing, not by bad data.

Resolution order within each pass:

1. Primary online API (`geoip_online_url_template`).
2. Backup URL (`geoip_online_url_template_backup`) if primary fails or returns no ISO code.
3. Nicotine metadata when available.
4. Unknown (`unknown_country_name`) if nothing else works.

## Dependencies

The plugin **requires `psycopg2`** (the PostgreSQL adapter) in the **same Python environment as Nicotine+**, or alternatively **`psycopg`** v3 with the binary extra. Without it, PostgreSQL writes are disabled.

**Ubuntu and Debian**

```bash
sudo apt update
sudo apt install python3-psycopg2
```

**Fedora**

```bash
sudo dnf install python3-psycopg2
```

If Nicotine+ does not use the system Python, install into that environment instead, for example:

```bash
pip install psycopg2-binary
```

## Install

Copy the folder `nicotine_upload_geo/` into your Nicotine+ plugin directory:

- Linux user plugins path: `~/.local/share/nicotine/plugins/`
- Final path should be: `~/.local/share/nicotine/plugins/nicotine_upload_geo/`

The plugin folder must contain:

- `PLUGININFO`
- `__init__.py`

Restart Nicotine+, then enable the plugin from Plugin Settings.
