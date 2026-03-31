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
   - `db_host`, `db_port`, `db_name`, `db_user`, `db_password`
   - Optional: `geoip_mmdb_path`

## 3) Country logic

The plugin uses:

1. Country from Nicotine+ metadata (preferred)
2. Fallback to GeoLite2 by IP when metadata is unavailable
3. Unknown country if neither source is available

To enable fallback geolocation:

- Download MaxMind GeoLite2 Country database
- Set plugin `geoip_mmdb_path` to the `.mmdb` file path

## 4) Grafana setup

1. Add a PostgreSQL datasource in Grafana pointing to this DB.
2. Use SQL examples from `queries/grafana_map_queries.sql`.
3. Build map/table/time-series panels from those queries.

## Notes

- Event table is append-only (`download_events`).
- Direction is fixed as `upload_from_me`.
- Store size and file path for drill-down reporting.
