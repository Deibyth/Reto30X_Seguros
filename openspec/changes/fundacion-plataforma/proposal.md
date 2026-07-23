# Proposal: Fundación de la Plataforma (Fase 1)

## Intent

Greenfield foundation for Protección Inteligente 360° — a hackathon MVP enabling Colsubsidio affiliates to explore, apply, and manage credits and insurance via an AI-driven conversational interface. This monorepo base unblocks all subsequent phases (Chat, Form Engine, Opportunity Engine, OCR).

## Scope

### In Scope
- FastAPI backend with health endpoint and Pydantic settings
- SQLAlchemy async + aiosqlite with 12 ORM entities (Customer through Notification)
- React 18 + Vite 6 + TypeScript 5 + TailwindCSS 3.4 + shadcn/ui minimal layout
- FastMCP server (embedded) with hello_world tool
- Docker Compose (backend:8000 + frontend:5173) with volume-mounted hot-reload
- Makefile, .env.example, .gitignore, README
- ~45 files total

### Out of Scope
- Business logic for credits/insurance, intent router, OCR, form engine, opportunity engine
- Alembic migrations (deferred to MVP stabilization)
- PostgreSQL / sidecar FastMCP (deferred to scale need)
- Authentication, tests, CI/CD pipelines

## Capabilities

All capabilities are new — no existing specs to modify.

### New Capabilities
- `health-check`: GET /health endpoint returning service status
- `data-models`: 12 SQLAlchemy ORM entities across all 8 domains
- `chat-api-stub`: POST /chat endpoint returning echo mock (placeholder for Fase 2)
- `fastmcp-server`: FastMCP server with hello_world tool, embedded in FastAPI process
- `docker-infrastructure`: Docker Compose with 2 services, Dockerfiles, dev workflow

### Modified Capabilities
None

## Approach

Docker-first monorepo with two services:

1. **backend** — `python:3.12-slim` + FastAPI + uvicorn --reload on :8000. App factory pattern with startup event calling `Base.metadata.create_all()`. FastMCP embedded in-process. 12 models in `app/models/` package, routers in `app/routers/`.

2. **frontend** — `node:20-alpine` + Vite dev server on :5173 with HMR. Manual Vite setup (not template) for full shadcn/ui control — New York style. Tailwind theme uses Colsubsidio brand colors (neutral fallback if assets unavailable).

Volume mounts enable hot-reload in both services. DB at `backend/data/proteccion360.db` on a named Docker volume. Vite proxy forwards `/api` to backend.

## Affected Areas

All greenfield — no existing files modified.

| Area | Impact | Description |
|------|--------|-------------|
| `backend/` | New | ~15 files: app factory, 12 models, 2 routers, tools, config, Dockerfile |
| `frontend/` | New | ~18 files: Vite/TS/Tailwind config, shadcn/ui, layout components, API client |
| Root | New | docker-compose.yml, Makefile, .env.example, .gitignore, README |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| FastMCP <1.0 API churn | Med | Pin version; fallback to raw MCP protocol |
| shadcn/ui init changes | Med | Commit components.json; pin version |
| SQLite async concurrency | Low | Document as MVP-only; clear PostgreSQL path |
| Hot-reload failure on non-Linux | Med | Enable poll mode in uvicorn/vite |

## Rollback Plan

All files are new — `git clean -fd` removes everything. For Docker state: `docker compose down -v` stops services and destroys volumes.

## Dependencies

- Docker + Docker Compose v2
- npm registry (frontend deps)
- PyPI (backend deps)
- shadcn/ui CLI (one-time init)

## Success Criteria

- [ ] `make dev` starts both services without errors
- [ ] `curl localhost:8000/health` returns 200 with `{"status": "ok"}`
- [ ] React app renders at localhost:5173 with "Protección Inteligente 360°" header
- [ ] FastMCP server responds to hello_world tool call
- [ ] All 12 SQLAlchemy models created in SQLite on startup
- [ ] Frontend layout renders Header + Layout + ChatPanel placeholder
