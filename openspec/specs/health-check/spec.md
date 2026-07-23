# Spec: Health Check

> **Capability:** C01 — `health-check`
> **Change:** `fundacion-plataforma`
> **Date:** 2026-07-16

## Description

FastAPI health check endpoint returning service status, plus application configuration via Pydantic `BaseSettings`. The health endpoint verifies the service is alive and the database is reachable. Configuration is loaded from environment variables with `.env` fallback.

## Requirements

### Functional

- F-HEALTH-01: The system SHALL expose a `GET /health` endpoint returning a JSON response with `{"status": "ok", "version": "0.1.0", "uptime_seconds": <float>}`.
- F-HEALTH-02: The system SHALL include a `database` field in the health response indicating whether the database connection is alive (`"connected"` or `"disconnected"`).
- F-HEALTH-03: The system SHALL load configuration from a `Settings` class using `pydantic-settings`.
- F-HEALTH-04: The system SHALL read environment variables from a `.env` file at the project root when present.
- F-HEALTH-05: The app factory `create_app()` SHALL accept optional `settings` parameter for test injection.
- F-HEALTH-06: The system SHALL expose configuration values: `DATABASE_URL`, `ENVIRONMENT`, `APP_NAME`, `APP_VERSION`, `CORS_ORIGINS`, `DEBUG`.
- F-HEALTH-07: The system SHALL register a startup event that records the application start time for uptime calculation.

### Non-Functional

- NF-HEALTH-01: The health endpoint SHALL respond in under 100ms (no DB query required for basic check).
- NF-HEALTH-02: Settings SHALL be immutable after application startup.
- NF-HEALTH-03: The health endpoint SHALL NOT require authentication (MVP only).

## API Contract

### `GET /health`

**Response `200 OK`:**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "uptime_seconds": 42.5,
  "database": "connected",
  "environment": "development"
}
```

**Response `503 Service Unavailable`** (DB down):
```json
{
  "status": "error",
  "version": "0.1.0",
  "uptime_seconds": 42.5,
  "database": "disconnected",
  "environment": "development"
}
```

## Configuration

```python
# app/config.py
class Settings(BaseSettings):
    app_name: str = "ProteccionInteligente360"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///data/proteccion360.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
```

`.env.example`:
```env
ENVIRONMENT=development
DATABASE_URL=sqlite+aiosqlite:///data/proteccion360.db
CORS_ORIGINS=["http://localhost:5173"]
DEBUG=true
```

## File Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # create_app() factory, startup event, lifespan
│   ├── config.py             # Settings via pydantic-settings
│   └── routers/
│       ├── __init__.py
│       └── health.py         # GET /health handler
```

## Dependencies

**Inter-capability:**
- `data-models` (C02) — database session reference for health DB check
- `docker-infrastructure` (C05) — service runs inside Docker, config via env vars

**External:**
- `fastapi>=0.115.0`
- `pydantic-settings>=2.7.0`
- `uvicorn[standard]>=0.34.0`

## Scenarios

### Scenario 1: Healthy service startup
**Given** the backend is starting up
**When** the app factory `create_app()` is called
**Then** settings are loaded from environment / `.env`
**And** the startup timestamp is recorded
**And** the health endpoint is registered at `/health`
**And** `GET /health` returns `{"status": "ok"}` with `database: "connected"`

### Scenario 2: Database unreachable
**Given** the database file is missing or permissions are wrong
**When** the health endpoint is called
**Then** the response status code SHALL be 503
**And** the response body SHALL contain `"database": "disconnected"`

### Scenario 3: Custom settings injection
**Given** a test caller
**When** `create_app(settings=test_settings)` is invoked
**Then** the app uses the injected settings instead of environment variables
