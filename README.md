# Nicotine Upload Geo Dashboard Pipeline

This project provides:

- A Nicotine+ plugin that records completed uploads (from you to peers)
- A PostgreSQL database schema and Docker Compose runtime
- Grafana-ready SQL queries for map and trend panels

Grafana is intentionally not bundled.

## Project structure

- `plugin/` - Nicotine+ plugin code and plugin docs
- `postgres/init/` - SQL initialization scripts
- `queries/` - SQL queries for Grafana panels
- `docker-compose.yml` - PostgreSQL runtime

## 1) Start PostgreSQL

```bash
cp .env.example .env
docker compose up -d
```

## 2) Install Nicotine+ plugin

1. Copy `plugin/nicotine_upload_geo/` into your Nicotine+ plugins directory (`~/.local/share/nicotine/plugins/` on Linux).
2. Enable the plugin in Nicotine+.
3. Configure plugin settings:
   - Required DB: `db_host`, `db_port`, `db_name`, `db_user`, `db_password`
   - Optional geo: `geoip_online_url_template`, `geoip_online_timeout_seconds`

## 3) Plugin dependencies

Install dependencies in the Python environment Nicotine+ uses:

- `psycopg[binary]` or `psycopg2` (required for PostgreSQL inserts)

If PostgreSQL driver is missing, plugin logs will show:

- `Install psycopg or psycopg2 to enable PostgreSQL writes`

## 4) Upload/IP/Country flow

The plugin uses:

1. `upload_finished_notification(user, virtual_path, real_path)` to detect completed uploads
2. `user_resolve_notification(user, ip_address, port, country)` to cache peer IP/country hints
3. Country resolution priority:
   - online IP lookup HTTP API (see `geoip_online_url_template`)
   - Nicotine metadata fallback
   - unknown

Default online lookup endpoint:

- `https://ipwho.is/{ip}`

## 5) Validate ingestion quickly

```bash
docker compose exec postgres psql -U nicotine -d nicotine -c "SELECT COUNT(*) FROM download_events;"
docker compose exec postgres psql -U nicotine -d nicotine -c "SELECT occurred_at, peer_username, peer_ip, country_code, country_name FROM download_events ORDER BY occurred_at DESC LIMIT 20;"
```

If table is missing (usually from an old volume before init script existed):

```bash
docker compose down -v
docker compose up -d
```

## 6) Grafana setup

1. Add a PostgreSQL datasource in Grafana pointing to this DB.
2. Use SQL examples from `queries/grafana_map_queries.sql`.
3. Build map/table/time-series panels from those queries.

## Notes

- Event table is append-only (`download_events`).
- Direction is fixed as `upload_from_me`.
- Store size and file path for drill-down reporting.
