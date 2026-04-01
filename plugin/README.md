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
- `unknown_country_name`: Fallback display name for unknown country

## Country resolution logic

1. Resolve country from peer IP using the primary online API (`geoip_online_url_template`).
2. If the request fails, the API reports failure (e.g. ipwho `success: false`), or no ISO country code is returned, try the backup URL (`geoip_online_url_template_backup`).
3. If both miss, fallback to Nicotine metadata when available.
4. If still unavailable, store country as unknown.

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
