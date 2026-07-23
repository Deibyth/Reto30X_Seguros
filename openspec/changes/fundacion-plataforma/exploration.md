# Exploration: Fundación de la Plataforma (Fase 1)

> **Change:** fundacion-plataforma
> **WI-001:** Fundación de la plataforma — Repositorio, backend, frontend e infraestructura base
> **Date:** 2026-07-16
> **Explorer:** sdd-explore sub-agent

---

## Current State

**Greenfield — no code exists.** The project has thorough knowledge artifacts (product vision, architecture, domains, tech stack, roadmap, work items) but zero implementation. The working directory contains only:

```
.atl/          — Atlassian/tooling config
.git/          — Git metadata
.kaddo/        — Kaddo knowledge artifacts
knowledge/     — Product, architecture, domain, roadmap, tech docs
openspec/      — SDD config (config.yaml, specs/, changes/)
```

No `backend/`, `frontend/`, `docker-compose.yml`, or code files exist.

---

## Affected Areas

Since this is greenfield, the entire project structure is being created. No existing files are modified.

| Path | Role |
|------|------|
| `backend/` | Python FastAPI application root |
| `backend/app/` | Application package |
| `backend/app/main.py` | FastAPI entry point, app factory |
| `backend/app/config.py` | Pydantic Settings configuration |
| `backend/app/database.py` | SQLAlchemy async engine + session |
| `backend/app/models/` | SQLAlchemy ORM models (12 entities) |
| `backend/app/routers/` | FastAPI route handlers |
| `backend/app/tools/` | FastMCP server definition |
| `backend/requirements.txt` | Python dependencies |
| `backend/Dockerfile` | Python container image |
| `frontend/` | React + Vite + TS application root |
| `frontend/src/` | TypeScript source code |
| `frontend/src/components/` | React components (layout/, chat/) |
| `frontend/src/lib/` | Utilities (api.ts) |
| `frontend/package.json` | Node dependencies |
| `frontend/vite.config.ts` | Vite build configuration |
| `frontend/tailwind.config.ts` | TailwindCSS configuration |
| `frontend/Dockerfile` | Node container image |
| `docker-compose.yml` | Multi-service orchestration |
| `Makefile` | Developer task shortcuts |
| `.env.example` | Environment variable template |
| `.gitignore` | Git exclusion rules |
| `README.md` | Project documentation |

---

## Investigation Findings

### Python Version Strategy

**Host has Python 3.14.6** — but 3.14 is too new for stable package ecosystem support.

**Recommendation:** Pin `python:3.12-slim` in the Dockerfile. Python 3.12 is the widely-supported LTS-like version with full FastAPI/SQLAlchemy ecosystem compatibility. Use 3.12 for both Docker and local `.python-version` (for pyenv/uv/poetry users). Projects that need to run natively on the host (without Docker) should note Python 3.12 as the target.

For the Docker image specifically: `python:3.12-slim` keeps the image small (~120MB) and avoids the build-essential overhead of the full image.

### Node Version Strategy

**Host has Node 24.18.0** and **npm 11.16.0**. Node 24 is current. But for reproducibility:

**Recommendation:** Use `node:20-alpine` in the Dockerfile (Active LTS through April 2026). Node 20 has the widest ecosystem compatibility. The Docker Compose setup uses the containerized Node, so the host version is irrelevant for deployments. For local development without Docker, recommend nvm or fnm with `.nvmrc` = `20`.

### FastMCP Integration Approach

FastMCP is an MCP (Model Context Protocol) server library that exposes Python functions as tools consumable by AI models. In this architecture:

1. **FastMCP runs as a separate ASGI/WSGI process** within the same container (or as a sub-process)
2. Each domain gets tool functions decorated with `@mcp.tool()`
3. The Conversation Hub/AI layer connects to FastMCP via the MCP protocol (stdio or SSE)
4. For Fase 1, the MCP server needs only a `ping` or `hello_world` tool to prove connectivity

**Key decision:** Should FastMCP run embedded in the FastAPI process or as a sidecar?

| Approach | Pros | Cons |
|----------|------|------|
| **Embedded** (same process) | Simpler deployment, shared DB session, no network overhead | Tight coupling, cannot scale independently |
| **Sidecar** (separate container) | Independent scaling, clear boundary, deploy separately | More complex networking, serialization overhead, extra container |

**Recommendation for MVP:** **Embedded** — FastMCP starts inside the FastAPI process on a separate port or path. This reduces complexity for a single-person hackathon team. The MCP server is instantiated in `backend/app/tools/mcp_server.py` and mounted as a sub-application or started as a background task. If time allows, expose it on a separate port for future sidecar extraction.

### Data Model Entity Map

From domain analysis, **12 entities** are needed. Below is the entity-relationship map:

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Customer   │────>│   Application    │────>│     Credit      │
│             │     │  (polymorphic)   │     │                 │
│ documento PK│     │                  │     │ monto_solicitado│
│ nombre      │     │ customer_id FK   │     │ plazo_meses     │
│ email       │     │ product_id FK    │     │ destino         │
│ salario     │     │ estado (state    │     │ modalidad       │
│ tipo_contr. │     │   machine)       │     └─────────────────┘
│ antiguedad  │     │ form_data (JSON) │
│ score       │     └──────────────────┘
└──────┬──────┘              │
       │                     │
       │              ┌──────┴───────┐       ┌─────────────┐
       │              │  Document    │       │   Policy    │
       │              │              │       │             │
       │              │ application/ │       │ customer FK │
       │              │  claim FK    │       │ insurance FK│
       │              │ tipo_doc     │       │ prima       │
       │              │ file_path    │       │ estado      │
       │              │ extracted_   │       │ fechas      │
       │              │   text (OCR) │       └─────────────┘
       │              └──────────────┘
       │
       │     ┌──────────────────┐     ┌─────────────┐
       │     │   Conversation   │────>│   Session   │
       │     │                  │     │             │
       │     │ session_id FK    │     │ customer FK │
       │     │ mensajes (JSON)  │     │ estado_act  │
       │     │ created_at       │     │ campos_json │
       │     └──────────────────┘     │ ultima_int  │
       │                              └─────────────┘
       │     ┌──────────────────┐     ┌──────────────┐
       │     │   Opportunity    │     │ Notification │
       │     │                  │     │              │
       │     │ customer_id FK   │     │ customer FK  │
       │     │ producto_id FK   │     │ tipo (wpp/   │
       │     │ estado           │     │   email)     │
       │     │ descripcion      │     │ estado       │
       │     └──────────────────┘     └──────────────┘

Additional standalone entities:
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │   Product    │     │  Insurance   │     │    Claim     │
  │              │     │              │     │              │
  │ nombre       │     │ nombre       │     │ policy_id FK │
  │ tipo         │     │ cobertura    │     │ customer FK  │
  │ descripcion  │     │ publico      │     │ estado       │
  │ monto_maximo │     │ activo       │     └──────────────┘
  │ modalidad    │     └──────────────┘
  │ activo       │
  └──────────────┘
```

**Key modeling decisions:**
1. **Application** is the generic form/submission entity with a `tipo` discriminator and JSON `form_data`. Credit-specific fields go in the `Credit` model.
2. **Product** is the catalog. **Insurance** extends the concept for insurance-specific fields (coverage, target audience).
3. **Policy** is the issued insurance contract (result of a completed insurance application).
4. **Session** carries the conversation state machine context (`estado_actual`, `campos_diligenciados`, `ultima_intencion`).
5. **Document** references either an application OR a claim (polymorphic via nullable FKs).
6. Use **SQLAlchemy 2.0 `Mapped`/`mapped_column`** style (not the legacy `declarative_base()`).
7. Use **async SQLAlchemy** with `aiosqlite` for async DB operations compatible with FastAPI's async handlers.

### SQLAlchemy + Persistence Approach

**Decision: async with auto-create for MVP**

- Use `sqlalchemy[asyncio]` + `aiosqlite` for async database operations
- For the hackathon MVP, use `Base.metadata.create_all()` on startup instead of Alembic migrations
- This avoids the overhead of managing migration scripts while the schema is rapidly evolving
- Add Alembic as a post-MVP improvement when the schema stabilizes
- Database file location: `backend/data/proteccion360.db` (create the `data/` directory with a `.gitkeep`)

### Frontend Bootstrapping Approach

**Decision: Manual setup (not Vite template)**

shadcn/ui requires specific configuration that differs from the default Vite React template:

1. Create the Vite project structure manually with `package.json`
2. Install dependencies: `react`, `react-dom`, `typescript`, `tailwindcss`, `postcss`, `autoprefixer`, `@vitejs/plugin-react`
3. Initialize shadcn/ui via `npx shadcn@latest init` — this creates `components.json` and configures CSS variables
4. Install base shadcn/ui components: `button`, `card`, `input`, `avatar`, `scroll-area`
5. Configure the TailwindCSS theme to use Colsubsidio institutional colors:
   - Primary: Colsubsidio red/burgundy (to be confirmed)
   - Neutrals for hierarchy
   - White backgrounds with subtle borders

**Structure within `frontend/src/`:**

```
src/
├── main.tsx              — React DOM entry
├── App.tsx               — Root component with layout
├── index.css             — Tailwind directives + CSS variables
├── components/
│   ├── ui/               — shadcn/ui components (auto-generated)
│   ├── layout/
│   │   ├── Header.tsx    — App header with logo and title
│   │   └── Layout.tsx    — Main layout wrapper
│   └── chat/
│       └── ChatPanel.tsx — Chat interface placeholder (for Fase 2)
└── lib/
    └── api.ts            — API client (fetch wrapper for backend)
```

### Docker Compose Architecture

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    volumes: ["./backend:/app"]     # hot-reload for dev
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///data/proteccion360.db
      - ENVIRONMENT=development
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    ports: ["5173:5173"]
    volumes: ["./frontend:/app"]    # hot-reload for dev
    depends_on: [backend]
    environment:
      - VITE_API_URL=http://localhost:8000
    command: npm run dev -- --host 0.0.0.0
```

**Important:** The dev Docker setup uses volume mounts for hot-reload. The production Dockerfile should NOT mount volumes and should use multi-stage builds.

### Makefile Targets

```makefile
.PHONY: dev backend frontend build clean shell

dev:          ## Start all services (docker-compose up)
	docker compose up --build

backend:      ## Start backend only
	docker compose up --build backend

frontend:     ## Start frontend only
	docker compose up --build frontend

build:        ## Build all images
	docker compose build

shell:        ## Open backend shell
	docker compose exec backend python

clean:        ## Stop and remove containers
	docker compose down -v
```

---

## Key Decisions Needed

| # | Decision | Options | Recommendation | Impact |
|---|----------|---------|---------------|--------|
| D1 | FastMCP runtime mode | Embedded vs Sidecar | **Embedded** (MVP) | Deployment simplicity |
| D2 | Migration strategy | Alembic vs auto-create | **Auto-create** (MVP) | Speed vs schema control |
| D3 | SQLAlchemy sync vs async | Sync/aiosqlite vs asyncpg | **Async + aiosqlite** | Future PostgreSQL migration |
| D4 | Frontend bootstrapping | Vite template vs manual | **Manual** | Full control over shadcn/ui config |
| D5 | Package manager (Python) | pip + requirements.txt vs poetry vs uv | **pip + requirements.txt** | Simplest for hackathon; pin exact versions |
| D6 | Package manager (Node) | npm vs pnpm vs yarn | **npm** | Already present; simplest |
| D7 | Environment config | .env files vs pydantic-settings | **pydantic-settings** + .env | Type-safe config, built for FastAPI |
| D8 | Colsubsidio brand colors | Exact palette needed | **TBD — need brand assets** | Affects Tailwind theme |
| D9 | CORS configuration | Localhost origins for dev | Allow `http://localhost:5173` | Standard for SPA-FastAPI dev |
| D10 | shadcn/ui style | New York vs Default | **New York** | More polished default style |

---

## Dependency Lock

### Backend (`requirements.txt`)

```
# Framework
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.3
pydantic-settings==2.7.0
python-dotenv==1.0.1

# Database
sqlalchemy[asyncio]==2.0.36
aiosqlite==0.20.0

# MCP
fastmcp>=0.3.0,<1.0.0

# File Handling
python-multipart==0.0.19
aiofiles==24.1.0

# CORS
# (included with FastAPI via starlette)
```

**Versions confirmed via pypi latest stable as of 2026-07.** Pin exact versions for reproducibility.

### Frontend (`package.json` dependencies)

```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "@tanstack/react-query": "^5.62.0",
    "framer-motion": "^11.15.0",
    "lucide-react": "^0.468.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.6.0",
    "class-variance-authority": "^0.7.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "vite": "^6.0.0",
    "typescript": "^5.7.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "tailwindcss": "^3.4.17",
    "postcss": "^8.4.49",
    "autoprefixer": "^10.4.20"
  }
}
```

---

## File Manifest

### Phase 1 — Files to Create (complete list)

```
Reto30X/
├── .env.example                           # Environment template
├── .gitignore                             # Python, Node, IDE, OS files
├── .python-version                        # "3.12" for pyenv users
├── .nvmrc                                 # "20" for nvm/fnm users
├── Makefile                               # Dev shortcuts
├── README.md                              # Project overview + setup
├── docker-compose.yml                     # Multi-service orchestration
│
├── backend/
│   ├── Dockerfile                         # python:3.12-slim + deps + app
│   ├── requirements.txt                   # Pinned Python deps
│   ├── data/
│   │   └── .gitkeep                       # DB directory placeholder
│   └── app/
│       ├── __init__.py
│       ├── main.py                        # FastAPI app factory, startup events
│       ├── config.py                      # Pydantic Settings (DB URL, env, etc.)
│       ├── database.py                    # Async engine + SessionLocal
│       ├── models/
│       │   ├── __init__.py                # Re-export all models, declare Base
│       │   ├── customer.py                # Customer ORM model
│       │   ├── product.py                 # Product catalog ORM model
│       │   ├── credit.py                  # Credit application fields
│       │   ├── insurance.py               # Insurance product fields
│       │   ├── policy.py                  # Issued insurance policy
│       │   ├── claim.py                   # Insurance claim
│       │   ├── application.py             # Generic application/submission
│       │   ├── document.py                # Uploaded document + OCR data
│       │   ├── conversation.py            # Chat conversation history
│       │   ├── session.py                 # Conversation state/memory
│       │   ├── opportunity.py             # Proactive opportunity record
│       │   └── notification.py            # Notification record
│       ├── routers/
│       │   ├── __init__.py
│       │   ├── health.py                  # GET /health endpoint
│       │   └── chat.py                    # Chat endpoints (placeholder for Fase 2)
│       └── tools/
│           ├── __init__.py
│           └── mcp_server.py             # FastMCP instance + hello_world tool
│
├── frontend/
│   ├── Dockerfile                         # node:20-alpine + build + serve
│   ├── package.json                       # Dependencies
│   ├── tsconfig.json                      # TypeScript config
│   ├── tsconfig.node.json                 # Node TypeScript config
│   ├── vite.config.ts                     # Vite + React plugin, proxy config
│   ├── tailwind.config.ts                 # TailwindCSS with brand theme
│   ├── postcss.config.js                  # PostCSS + Tailwind + autoprefixer
│   ├── components.json                    # shadcn/ui config
│   ├── index.html                         # HTML entry point
│   └── src/
│       ├── main.tsx                       # React DOM entry
│       ├── App.tsx                        # Root component with Router
│       ├── index.css                      # Tailwind directives + CSS vars
│       ├── vite-env.d.ts                  # Vite type declarations
│       ├── components/
│       │   ├── ui/                        # shadcn/ui components (generated)
│       │   ├── layout/
│       │   │   ├── Header.tsx             # App header
│       │   │   └── Layout.tsx             # Main layout
│       │   └── chat/
│       │       └── ChatPanel.tsx           # Chat UI placeholder
│       └── lib/
│           └── api.ts                     # API client
│
└── openspec/
    └── changes/
        └── fundacion-plataforma/
            └── exploration.md             # THIS FILE
```

**Total: ~45 files** (including shadcn/ui generated components).

---

## Approaches Considered

### Approach A: Docker-First Foundation (Recommended)

Build everything inside Docker from the start. The `docker-compose.yml` is the primary dev workflow. Both backend and frontend have Dockerfiles with volume mounts for hot-reload.

- **Pros:** Reproducible environment from day 1, matches deployment setup, no "works on my machine" issues, immediate containerized development
- **Cons:** Slower first build, Docker overhead on low-end machines
- **Effort:** Medium

### Approach B: Native-Only Foundation

Develop directly on the host without Docker. Add Docker later.

- **Pros:** Faster iteration without container builds, simpler for single-person team
- **Cons:** Risk of environment drift, Docker setup deferred (often forgotten), doesn't match deployment
- **Effort:** Low (initially), Medium (when adding Docker later)

### Approach C: Monolithic Single Container

Place both backend and frontend in a single Docker image with a multi-process runner.

- **Pros:** Simple deployment, single container to manage
- **Cons:** Mixes concerns, cannot scale independently, confusing for future team members
- **Effort:** Low

---

## Recommendation

**Approach A — Docker-First Foundation** with these specifics:

1. **Two services** in `docker-compose.yml`: `backend` and `frontend`
2. Frontend dev server proxies `/api` requests to backend (via Vite proxy or CORS)
3. Backend uses `uvicorn --reload` with volume mounts for hot-reload
4. Frontend uses `vite dev --host` with volume mounts for HMR
5. Database file lives in `backend/data/` on a named volume or bind mount
6. `.env` file at project root is shared by both services via `env_file`
7. `Makefile` provides `make dev` → `docker compose up --build`

**Why this approach over others:**
- The deployment target (Railway/Render) uses containers — starting with Docker eliminates the "containerize later" scramble
- Hot-reload works through volume mounts so dev speed isn't sacrificed
- Single-person team benefits from reproducible environments (no surprises between machines)
- Establishes the container boundary for FastMCP early (even though we're embedding it in MVP)

---

## Risks and Edge Cases

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Python 3.12 package incompatibility** | Low | High | Pin exact versions in `requirements.txt`; test `pip install` in CI/Docker build |
| **shadcn/ui init changes API** | Medium | Medium | Run `npx shadcn@latest init` and commit `components.json`; pin shadcn version if breaking |
| **FastMCP API instability** | Medium | High | FastMCP is relatively new (<1.0). Pin to a known working version. Have a fallback plan (raw MCP protocol). |
| **SQLite concurrency in async FastAPI** | Low | Medium | SQLite has limited concurrent writes. For MVP with single user, this is fine. Document as known limitation for future PostgreSQL migration. |
| **Colsubsidio brand assets unavailable** | Medium | Low | Use neutral Tailwind theme as fallback. Brand colors can be swapped later via CSS variables. |
| **Docker disk space on dev machine** | Low | Low | Use slim/alpine images; clean up old images with `docker system prune` |
| **Hot-reload not working through Docker volumes** (Windows/macOS) | Medium | Medium | Ensure `poll` mode for `uvicorn --reload` and `vite --watch` on non-Linux hosts |
| **Alembic deferred leads to migration pain** | Low (MVP) | Medium | Accept for MVP. Add Alembic in Fase 2 or 3 when schema stabilizes. |

### Edge Cases

1. **First `docker compose up --build` failure:** Ensure the frontend Dockerfile waits for `npm install` to complete before starting the dev server. Use a `RUN npm install` in the Dockerfile (cached by Docker layer) plus volume mount for source.

2. **Multiple simultaneous users with SQLite:** SQLite handles this poorly. For the hackathon demo, this is acceptable. The architecture must document that SQLite is MVP-only and PostgreSQL (via asyncpg) is the target.

3. **shadcn/ui component.json path resolution:** shadcn/ui creates components in `components/ui/` by default. Ensure the `components.json` `aliases` field is set correctly for the project's import structure.

4. **Environment variable propagation:** Docker Compose `environment` block variables are available at runtime. Build-time variables (like VITE_API_URL) must use `VITE_` prefix and be set at build time or via dynamic injection.

5. **Database persistence across container restarts:** Use a Docker volume for `backend/data/` to avoid data loss on `docker compose down`.

---

## Ready for Proposal

**Yes.** The exploration is comprehensive enough to produce a formal proposal. The orchestrator should:

1. Confirm the key decisions (D1-D10) with the user — especially D1 (FastMCP embedded vs sidecar), D2 (auto-create vs Alembic), and D8 (Colsubsidio brand colors)
2. Proceed to `sdd-propose` for a formal change proposal
3. No blockers found — the foundation phase is well-defined with clear acceptance criteria from WI-001

### Summary for Proposal Phase

- **Project structure:** Monorepo with `backend/`, `frontend/`, `docker-compose.yml`
- **Backend:** Python 3.12, FastAPI, async SQLAlchemy + aiosqlite, FastMCP embedded
- **Frontend:** React 18, Vite 6, TypeScript 5, TailwindCSS 3.4, shadcn/ui
- **Data model:** 12 entities covering all 8 domains
- **Infrastructure:** Docker Compose with 2 services, volume-mounted hot-reload
- **Dependencies:** Pinned in `requirements.txt` and `package.json`
- **Files to create:** ~45 files
