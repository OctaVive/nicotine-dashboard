# Nicotine Upload Geo Dashboard Pipeline

This project provides:

- A Nicotine+ plugin that records completed uploads (from you to peers)
- A PostgreSQL database schema and Docker Compose runtime

## Project structure

- `plugin/` - Nicotine+ plugin code and plugin docs
- `postgres/init/` - SQL initialization scripts
- `docker-compose.yml` - PostgreSQL runtime

## 1) Start PostgreSQL

PostgreSQL runs in **Docker** via Compose (see `docker-compose.yml`). From the project directory:

```bash
cp .env.example .env
docker compose up -d
```

## 2) Install Nicotine+ plugin

1. Copy `plugin/nicotine_upload_geo/` into your Nicotine+ plugins directory (`~/.local/share/nicotine/plugins/` on Linux).
2. Enable the plugin in Nicotine+.
3. Configure plugin settings:
   - Required DB: `db_host`, `db_port`, `db_name`, `db_user`, `db_password`
   - Optional: primary/backup online lookup URL templates and HTTP timeout (see `plugin/README.md`)

## 3) Plugin dependencies

The plugin **requires a PostgreSQL driver** so it can insert rows into your database. Install **`psycopg2`** (or **`psycopg`** v3 with the binary extra) into the **same Python environment that runs Nicotine+**. If the driver is missing, the plugin logs:

- `Install psycopg or psycopg2 to enable PostgreSQL writes`

### Linux: distro packages (system Python)

If Nicotine+ uses your distribution’s Python 3, install the packaged bindings:

**Ubuntu and Debian**

```bash
sudo apt update
sudo apt install python3-psycopg2
```

**Fedora**

```bash
sudo dnf install python3-psycopg2
```

### pip (venv, custom Python, or when the distro package does not match Nicotine’s Python)

```bash
pip install psycopg2-binary
```

(or `pip install 'psycopg[binary]'` for psycopg v3).

## 4) Upload/IP/Country flow

The plugin uses:

1. `upload_finished_notification(user, virtual_path, real_path)` to detect completed uploads
2. `user_resolve_notification(user, ip_address, port, country)` to cache peer IP/country hints
3. Country resolution priority:
   - primary online HTTP lookup (`geoip_online_url_template`, default `https://ipwho.is/{ip}`)
   - backup online lookup (`geoip_online_url_template_backup`, default ip-api.com over HTTP) if primary fails or returns no country
   - Nicotine metadata fallback
   - unknown

Clear the backup setting if you do not want a second HTTP request or non-HTTPS calls.

## 5) Validate ingestion quickly

```bash
docker compose exec postgres psql -U nicotine -d nicotine -c "SELECT COUNT(*) FROM download_events;"
docker compose exec postgres psql -U nicotine -d nicotine -c "SELECT occurred_at, peer_username, peer_ip, country_code, country_name FROM download_events ORDER BY occurred_at DESC LIMIT 20;"
```

## `download_events` columns

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `BIGSERIAL` | Primary key |
| `occurred_at` | `TIMESTAMPTZ` | When the upload finished (UTC) |
| `peer_username` | `TEXT` | Remote user |
| `peer_ip` | `INET` | Peer address |
| `country_code` | `TEXT` | ISO country code when known |
| `country_name` | `TEXT` | Country name when known |
| `file_path` | `TEXT` | Shared file path |
| `bytes_transferred` | `BIGINT` | Size in bytes |
| `transfer_direction` | `TEXT` | Always `upload_from_me` for this plugin |

Defined in `postgres/init/001_schema.sql`. The table is append-only.

## Notes

- Direction is fixed as `upload_from_me`.
- Store size and file path for drill-down reporting.
