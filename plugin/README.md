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
- Online lookup URL template: default `https://ipwho.is/{ip}`; must include `{ip}` (peer address)
- Online lookup timeout: seconds for the HTTP request
- `unknown_country_name`: Fallback display name for unknown country

## Country resolution logic

1. Resolve country from peer IP using the configured online HTTP API.
2. If that fails or returns no country, fallback to Nicotine metadata when available.
3. If still unavailable, store country as unknown.

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
