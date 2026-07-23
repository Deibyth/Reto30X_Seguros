# Design: Fundación de la Plataforma (Fase 1)

## Technical Approach

Docker-first monorepo with two services (backend FastAPI + React frontend). App factory (`create_app`) with FastAPI lifespan context manager orchestrates startup: config load → DB engine init → metadata.create_all() → router registration → CORS → FastMCP init. All 5 capabilities land as new files under `backend/`, `frontend/`, and root.

## Architecture Decisions

| Decision | Options | Choice | Rationale |
|----------|---------|--------|-----------|
| App pattern | Class-based / Factory fn with lifespan | **`create_app()` factory** | Test-injectable settings, single startup path, matches spec F-HEALTH-05 |
| DB init | On first request / Lifespan startup | **Lifespan startup** | Guarantees DB ready before first request; FastAPI idiomatic |
| FastMCP runtime | Sidecar / Embedded | **Embedded (in-process)** | Simplifies MVP; shared DB session; future sidecar extraction via extracted module |
| Schema migration | Alembic / `create_all()` | **`create_all()` on startup** | MVP speed; schema volatile; Alembic added post-MVP |
| ORM style | Legacy `declarative_base()` / 2.0 `Mapped` | **SQLAlchemy 2.0 `Mapped`** | Type-safe, modern, async-native |
| CORS config | FastAPI middleware / Per-route | **CORSMiddleware on app** | Single config point, covers all routes |

## Data Flow

```
Browser ──HTTP──→ Vite Dev Server (:5173)
                    │
                  proxy /api/*
                    │
                    ▼
            FastAPI App (:8000)
             ├── GET /health ──→ DB ping check
             ├── POST /chat ──→ echo response (no DB)
             └── FastMCP (in-process)
                   └── hello_world tool
```

## Sequence: Application Startup

```
uvicorn main:app
    │
    ▼
create_app(settings=None)
    │
    ├── 1. Load Settings (env / .env fallback)
    ├── 2. Create FastAPI instance
    ├── 3. Record start_time for uptime
    │
    ├── [lifespan startup]
    │   ├── 4. Init async_engine (aiosqlite)
    │   ├── 5. Base.metadata.create_all()
    │   ├── 6. Import & init FastMCP instance
    │   └── 7. Log "Application started"
    │
    ├── 8. Register middleware: CORS
    ├── 9. Include routers: health, chat
    │
    └── return app
```

## Component Interaction

```
┌─────────────────────────────────────────────────┐
│                  FastAPI App                      │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ health   │  │ chat     │  │ FastMCP (tools) │  │
│  │ router   │  │ router   │  │ mcp_server.py   │  │
│  └────┬─────┘  └────┬─────┘  └────────────────┘  │
│       │             │                              │
│       ▼             ▼                              │
│  ┌──────────────────────────────────┐              │
│  │       database.py                │              │
│  │  async_engine → async_session    │              │
│  │  get_db() dependency             │              │
│  └──────────────┬───────────────────┘              │
│                 │                                   │
└─────────────────┼───────────────────────────────────┘
                  │
                  ▼
        ┌─────────────────┐
        │  aiosqlite       │
        │  proteccion360.db│
        └─────────────────┘
```

## File Changes (all new — greenfield)

| File | Description |
|------|-------------|
| `backend/Dockerfile` | python:3.12-slim, layers for pip cache, mkdir data |
| `backend/requirements.txt` | Pinned deps: fastapi, uvicorn, pydantic-settings, sqlalchemy[asyncio], aiosqlite, fastmcp |
| `backend/app/__init__.py` | Package marker |
| `backend/app/main.py` | `create_app()` factory, lifespan context manager |
| `backend/app/config.py` | `Settings(BaseSettings)` with all env vars |
| `backend/app/database.py` | `async_engine`, `AsyncSession` factory, `get_db` async generator |
| `backend/app/models/__init__.py` | `Base` declarative base, re-export all models |
| `backend/app/models/customer.py` | 12 columns: id UUID PK, documento_identidad unique, salario, etc. |
| `backend/app/models/product.py` | 8 columns: nombre, tipo discriminator, monto_maximo |
| `backend/app/models/credit.py` | 7 columns: FK→application, monto_solicitado, plazo_meses |
| `backend/app/models/insurance.py` | 7 columns: nombre, cobertura, prima_base |
| `backend/app/models/policy.py` | 10 columns: FK→customer, FK→insurance, numero_poliza, fechas |
| `backend/app/models/claim.py` | 8 columns: FK→customer, FK→policy, monto_reclamado |
| `backend/app/models/application.py` | 8 columns: FK→customer, FK→product, form_data JSON |
| `backend/app/models/document.py` | 9 columns: FKs→application/claim/customer, file_path, ocr_processed |
| `backend/app/models/conversation.py` | 6 columns: FK→session, rol, mensaje, metadata_json |
| `backend/app/models/session.py` | 8 columns: FK→customer, estado_actual, campos_diligenciados JSON |
| `backend/app/models/opportunity.py` | 8 columns: FK→customer, FK→product, score |
| `backend/app/models/notification.py` | 8 columns: FK→customer, tipo discriminator wpp/email |
| `backend/app/routers/__init__.py` | Package marker |
| `backend/app/routers/health.py` | `GET /health` → status, version, uptime, db status |
| `backend/app/routers/chat.py` | `POST /chat` → `ChatRequest`/`ChatResponse`, echo mock |
| `backend/app/tools/__init__.py` | Package marker |
| `backend/app/tools/mcp_server.py` | `FastMCP("Proteccion360")` + `hello_world` tool |
| `backend/data/.gitkeep` | Preserve data/ dir in git |
| `frontend/Dockerfile` | node:20-alpine, npm ci layers |
| `frontend/package.json` | React 18, Vite 6, TS 5, TailwindCSS 3.4, shadcn/ui deps |
| `frontend/vite.config.ts` | React plugin, proxy `/api` → `localhost:8000` |
| `frontend/src/lib/api.ts` | `ApiClient` class with `sendMessage`, `checkHealth` |
| `frontend/src/components/layout/Header.tsx` | App header with branding |
| `frontend/src/components/layout/Layout.tsx` | Main layout wrapper |
| `frontend/src/components/chat/ChatPanel.tsx` | Chat UI placeholder |
| Root: `docker-compose.yml`, `Makefile`, `.env.example`, `.gitignore`, `README.md` | Infrastructure + dev workflow |

## Interfaces / Contracts

### Health Router (`app/routers/health.py`)
```python
@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    # Returns {"status": "ok", "version", "uptime_seconds", "database", "environment"}
```

### Chat Router (`app/routers/chat.py`)
```python
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)

class ChatResponse(BaseModel):
    reply: str
    timestamp: datetime
    session_id: str | None = None

@router.post("/chat")
async def chat_handler(request: ChatRequest, session_id: str | None = Header(None)) -> ChatResponse
```

### Database Dependency (`app/database.py`)
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(async_engine) as session:
        yield session
```

## Error Handling Strategy

| Layer | Strategy | Behaviour |
|-------|----------|-----------|
| DB connection failure | Lifespan exception | App fails to start; logs explain missing DB |
| DB unreachable at health check | Try `execute(SELECT 1)` | Returns 503 with `database: "disconnected"` |
| Invalid chat payload | Pydantic validation (FastAPI) | Auto 422 with detail array |
| Unhandled route | FastAPI default | 404 Not Found |
| Server error | FastAPI default exception handler | 500 Internal Server Error |
| Missing .env file | pydantic-settings falls back to defaults | App starts with default config, warns if DEBUG |

## Configuration Management

All config via `pydantic-settings` `Settings` class. Priority: explicit env var > `.env` file > class default. Singleton instance created in `create_app()` (or injected for tests). Values: `DATABASE_URL`, `ENVIRONMENT`, `APP_NAME`, `APP_VERSION`, `CORS_ORIGINS`, `DEBUG`. `.env.example` documents every var.

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | Settings loading | `create_app(settings=test_settings)`, assert config used |
| Unit | Health response | TestClient GET /health → assert status, version, uptime shape |
| Unit | Chat echo | TestClient POST /chat → assert reply == "Echo: {message}" |
| Unit | Model creation | Create model instances in-memory, assert UUID/column types |
| Integration | DB startup | Init engine, `create_all()`, verify table count |
| Integration | get_db lifecycle | FastAPI dependency override, assert session open/close |

Foundation phase: functional smoke tests only. No CI pipeline (out of scope). Tests run via `python -m pytest` inside container.

## Threat Matrix

**N/A** — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary in this change.

## Migration / Rollout

No migration required. Greenfield creation of all files. Rollback: `git clean -fd` for files; `docker compose down -v` for Docker state.

## Open Questions

- [x] None — all decisions resolved in exploration phase.
