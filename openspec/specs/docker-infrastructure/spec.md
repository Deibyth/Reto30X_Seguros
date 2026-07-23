# Spec: Docker Infrastructure

> **Capability:** C05 — `docker-infrastructure`
> **Change:** `fundacion-plataforma`
> **Date:** 2026-07-16

## Description

Multi-service Docker Compose orchestration with hot-reload development workflow. Two services (backend on :8000, frontend on :5173) with volume mounts for live code changes, plus root-level developer tooling (Makefile, .env.example, .gitignore, README).

## Requirements

### Functional

- F-DOCKER-01: The system SHALL provide a `docker-compose.yml` with two services: `backend` and `frontend`.
- F-DOCKER-02: The backend service SHALL build from `backend/Dockerfile` using `python:3.12-slim`.
- F-DOCKER-03: The frontend service SHALL build from `frontend/Dockerfile` using `node:20-alpine`.
- F-DOCKER-04: The backend SHALL expose port `8000` and run `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`.
- F-DOCKER-05: The frontend SHALL expose port `5173` and run `npm run dev -- --host 0.0.0.0`.
- F-DOCKER-06: Both services SHALL mount their source directories as volumes for hot-reload.
- F-DOCKER-07: The frontend SHALL have `depends_on: [backend]`.
- F-DOCKER-08: The backend Dockerfile SHALL copy `requirements.txt` and run `pip install` before copying the app source.
- F-DOCKER-09: The frontend Dockerfile SHALL copy `package.json` and `package-lock.json` and run `npm ci` before copying source.
- F-DOCKER-10: A `Makefile` SHALL provide targets: `dev`, `backend`, `frontend`, `build`, `shell`, `clean`.
- F-DOCKER-11: A `.env.example` SHALL document all environment variables.
- F-DOCKER-12: A `.gitignore` SHALL exclude Python (`__pycache__`, `.pyc`, `.egg-info`), Node (`node_modules/`, `dist/`), IDE (`.vscode/`, `.idea/`), and OS files (`.DS_Store`).
- F-DOCKER-13: A `README.md` SHALL document setup, `make dev`, and project overview.
- F-DOCKER-14: The backend Dockerfile SHALL create the `data/` directory.
- F-DOCKER-15: The database file SHALL persist using a named Docker volume `proteccion360_data` mounted at `/app/data/`.

### Non-Functional

- NF-DOCKER-01: First `docker compose up --build` SHALL complete in under 5 minutes on a standard connection.
- NF-DOCKER-02: Hot-reload SHALL reflect code changes within 2 seconds on Linux (poll mode fallback for non-Linux).
- NF-DOCKER-03: Docker images SHALL use `slim`/`alpine` variants to minimize size.
- NF-DOCKER-04: The backend service SHALL expose port `8000` only (no debug port in MVP).
- NF-DOCKER-05: All containers SHALL be removable with `docker compose down -v` without leaving orphaned state.

## Configuration

### `docker-compose.yml`

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
      - proteccion360_data:/app/data
    env_file:
      - .env
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///data/proteccion360.db
      - ENVIRONMENT=development
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    depends_on:
      - backend
    environment:
      - VITE_API_URL=http://localhost:8000
    command: npm run dev -- --host 0.0.0.0

volumes:
  proteccion360_data:
```

### `Makefile`

```makefile
.PHONY: dev backend frontend build shell clean

dev:          ## Start all services
	docker compose up --build

backend:      ## Start backend only
	docker compose up --build backend

frontend:     ## Start frontend only
	docker compose up --build frontend

build:        ## Build all images
	docker compose build

shell:        ## Open backend Python shell
	docker compose exec backend python

clean:        ## Stop and remove containers + volumes
	docker compose down -v
```

### `.env.example`

```env
ENVIRONMENT=development
DATABASE_URL=sqlite+aiosqlite:///data/proteccion360.db
CORS_ORIGINS=["http://localhost:5173"]
DEBUG=true
VITE_API_URL=http://localhost:8000
```

## File Structure

```
Reto30X/
├── .env.example              # Environment variable template
├── .gitignore                # Python, Node, IDE, OS excludes
├── .python-version           # "3.12" (optional, for pyenv)
├── .nvmrc                    # "20" (optional, for nvm/fnm)
├── Makefile                  # Dev task shortcuts
├── README.md                 # Project documentation
├── docker-compose.yml        # Multi-service orchestration
├── backend/
│   └── Dockerfile            # python:3.12-slim
└── frontend/
    └── Dockerfile            # node:20-alpine
```

## Dockerfile: Backend

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create data directory for SQLite
RUN mkdir -p data

# Copy application code
COPY app/ app/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

## Dockerfile: Frontend

```dockerfile
FROM node:20-alpine

WORKDIR /app

# Install dependencies (layer caching)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source code
COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

## Dependencies

**Inter-capability:**
- `health-check` (C01) — backend service runs health endpoint on :8000
- `data-models` (C02) — DB volume mount persists SQLite file
- `chat-api-stub` (C03) — Vite proxy routes `/api` to backend
- `fastmcp-server` (C04) — FastMCP embedded in backend service

**External:**
- Docker Engine >= 24
- Docker Compose v2

## Scenarios

### Scenario 1: Full stack startup
**Given** Docker and Docker Compose are installed
**When** `make dev` is run
**Then** both images build successfully
**And** the backend responds on `http://localhost:8000/health` with 200
**And** the frontend responds on `http://localhost:5173` with the React app

### Scenario 2: Hot-reload backend change
**Given** both services are running via `make dev`
**When** a Python file is modified in `backend/app/`
**Then** uvicorn detects the change (within 2 seconds on Linux)
**And** the backend process reloads automatically

### Scenario 3: Hot-reload frontend change
**Given** both services are running via `make dev`
**When** a file is modified in `frontend/src/`
**Then** Vite HMR pushes the update to the browser
**And** the page reflects the change without a full reload

### Scenario 4: Clean shutdown
**Given** services are running
**When** `make clean` is executed
**Then** containers stop
**And** volumes are removed
**And** `docker ps` shows no orphaned containers

### Scenario 5: Database persistence
**Given** the backend has written data
**When** `docker compose down` (without `-v`) is run
**And** `docker compose up` is run again
**Then** the previously written data is still available
