# Tasks: Fundación de la Plataforma (Fase 1)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,300 (37 files, all new) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Foundation + Data → PR 2: API + Tools → PR 3: Infra |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

```
Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High
```

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Backend structure + DB + models | PR 1 | `python -c "from app.models import Base; print('OK')"` | `docker compose up --build backend` | `git clean -fd backend/` + `docker compose down -v` |
| 2 | App factory, health, FastMCP, chat | PR 2 | `curl localhost:8000/health \| grep ok` | `docker compose up --build backend` | `git stash backend/app/main.py backend/app/routers/ backend/app/tools/` |
| 3 | Frontend + Dockerfiles + Makefile + docs | PR 3 | `docker compose build && docker compose up -d && curl localhost:8000/health` | `make dev` | `git clean -fd frontend/ root-files` + `docker compose down -v` |

## Phase 1: Foundation

- [ ] **T-001** — Create backend structure: `requirements.txt`, `app/__init__.py`, `app/config.py` (Settings via pydantic-settings), `.python-version`. Deps: none. [Small]
- [ ] **T-008** — Scaffold frontend: Vite 6 + React 18 + TypeScript 5 + TailwindCSS 3.4 + shadcn/ui (New York style), `package.json`, `vite.config.ts` with `/api` proxy, minimal App + Header. Deps: none. [Medium]
- [ ] **T-011** — Root files: `.gitignore` (Python/Node/IDE/OS), `.env.example`, `README.md` with setup guide. Deps: none. [Small]

## Phase 2: Data Layer

- [ ] **T-003** — Create `app/database.py`: `async_engine` (aiosqlite), `AsyncSession` factory, `get_db` async generator. Add `app/models/__init__.py` with `Base = declarative_base()`. Deps: T-001. [Small]
- [ ] **T-004** — Create 12 ORM models in `app/models/` (one file each): Customer, Product, Credit, Insurance, Policy, Claim, Application, Document, Conversation, Session, Opportunity, Notification. All use `Mapped`/`mapped_column`, UUID PKs, timestamps. Deps: T-003. [Medium]
- [ ] **T-005** — Wire `Base.metadata.create_all()` into app factory lifespan. Create `backend/data/.gitkeep`. Deps: T-004. [Small]

## Phase 3: API & Tools

- [ ] **T-002** — Implement `create_app()` factory with lifespan context manager, `GET /health` router (status/version/uptime/DB check), CORSMiddleware. Deps: T-001, T-003, T-005. [Medium]
- [ ] **T-006** — Create `app/tools/mcp_server.py`: `FastMCP("Proteccion360")` with `hello_world(name="Mundo")` tool returning greeting string. Deps: T-001. [Small]
- [ ] **T-007** — Create `POST /chat` router with `ChatRequest`/`ChatResponse` models (echo mock). Create `frontend/src/lib/api.ts` with `ApiClient` class (`sendMessage`, `checkHealth`). Deps: T-001, T-008. [Medium]

## Phase 4: Infrastructure

- [ ] **T-009** — Create `backend/Dockerfile` (python:3.12-slim, pip layer caching, mkdir data) and `docker-compose.yml` (backend:8000 + frontend:5173, volumes, named DB volume, depends_on). Deps: T-002. [Medium]
- [ ] **T-010** — Create `frontend/Dockerfile` (node:20-alpine, npm ci layer caching) and `Makefile` (dev/backend/frontend/build/shell/clean targets). Deps: T-008. [Small]

## Acceptance Checklist

- [ ] `make dev` starts both services without errors
- [ ] `curl localhost:8000/health` returns 200 with `{"status": "ok"}`
- [ ] All 12 tables created in SQLite on startup
- [ ] React app renders at localhost:5173 with branded header
- [ ] FastMCP `hello_world` tool responds via MCP protocol
- [ ] `POST /chat` returns `{"reply": "Echo: ..."}` with timestamp
