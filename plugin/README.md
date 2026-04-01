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
- `geoip_online_url_template`: Online lookup URL (default `https://ipwho.is/{ip}`; must include `{ip}`)
- `geoip_online_timeout_seconds`: Timeout for online lookup
- `unknown_country_name`: Fallback display name for unknown country

## Country resolution logic

1. Resolve country from peer IP using the configured online HTTP API.
2. If that fails or returns no country, fallback to Nicotine metadata when available.
3. If still unavailable, store country as unknown.

## Dependencies

Install Python packages in the environment Nicotine+ uses:

- `psycopg[binary]` (or `psycopg2`)

## Install

Copy the folder `nicotine_upload_geo/` into your Nicotine+ plugin directory:

- Linux user plugins path: `~/.local/share/nicotine/plugins/`
- Final path should be: `~/.local/share/nicotine/plugins/nicotine_upload_geo/`

The plugin folder must contain:

- `PLUGININFO`
- `__init__.py`

Restart Nicotine+, then enable the plugin from Plugin Settings.
