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
   - Optional: online country lookup URL template and HTTP timeout (see plugin docs)

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
   - online HTTP lookup for the peer IP (configurable URL template)
   - Nicotine metadata fallback
   - unknown

The default lookup URL is `https://ipwho.is/{ip}` unless you change it in plugin settings.

## 5) Validate ingestion quickly

```bash
docker compose exec postgres psql -U nicotine -d nicotine -c "SELECT COUNT(*) FROM download_events;"
docker compose exec postgres psql -U nicotine -d nicotine -c "SELECT occurred_at, peer_username, peer_ip, country_code, country_name FROM download_events ORDER BY occurred_at DESC LIMIT 20;"
```

## Notes

- Event table is append-only (`download_events`).
- Direction is fixed as `upload_from_me`.
- Store size and file path for drill-down reporting.
