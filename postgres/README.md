# PostgreSQL Runtime

This project runs PostgreSQL with Docker Compose and initializes the schema from `postgres/init/001_schema.sql`.

## Start

1. Copy env file:
   - `cp .env.example .env`
2. Update credentials in `.env` if needed.
3. Run:
   - `docker compose up -d`

## Verify

- `docker compose ps`
- `docker compose logs postgres`

## Connect

Use these values in the Nicotine+ plugin settings:

- host: your Docker host IP
- port: `POSTGRES_PORT` from `.env`
- db: `POSTGRES_DB`
- user: `POSTGRES_USER`
- password: `POSTGRES_PASSWORD`

If Nicotine+ runs on the same host, use `127.0.0.1` as DB host.
