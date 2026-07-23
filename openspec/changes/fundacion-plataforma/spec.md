# Spec: Fundación de la Plataforma (Fase 1)

> **Change:** `fundacion-plataforma`
> **Change ID:** WI-001
> **Date:** 2026-07-16

## Description

Greenfield foundation for Protección Inteligente 360° — a monorepo with FastAPI backend, React frontend, FastMCP embedded server, and Docker Compose orchestration. All capabilities are new; no existing specs are modified.

## Capability Specs

| ID | Capability | Spec | Description |
|----|-----------|------|-------------|
| C01 | `health-check` | [spec](../specs/health-check/spec.md) | FastAPI health endpoint, Pydantic settings, startup lifecycle |
| C02 | `data-models` | [spec](../specs/data-models/spec.md) | 12 SQLAlchemy async ORM entities covering all 8 domains |
| C03 | `chat-api-stub` | [spec](../specs/chat-api-stub/spec.md) | POST /chat echo mock endpoint + API client stub |
| C04 | `fastmcp-server` | [spec](../specs/fastmcp-server/spec.md) | FastMCP server base with hello_world tool, embedded in FastAPI |
| C05 | `docker-infrastructure` | [spec](../specs/docker-infrastructure/spec.md) | Multi-service Docker Compose, Dockerfiles, dev workflow |

## Modified Specs

None — all capabilities are new.

## Traceability Matrix

| Requirement | C01 | C02 | C03 | C04 | C05 |
|-------------|:---:|:---:|:---:|:---:|:---:|
| Backend FastAPI on :8000 | ✓ | | | | ✓ |
| GET /health returns status | ✓ | | | | |
| Health includes version + uptime | ✓ | | | | |
| Pydantic-settings configuration | ✓ | | | | |
| 12 ORM entities across 8 domains | | ✓ | | | |
| SQLAlchemy 2.0 Mapped style | | ✓ | | | |
| Async + aiosqlite engine | | ✓ | | | |
| Auto-create tables on startup | | ✓ | | ✓ | |
| POST /chat echo stub | | | ✓ | | |
| API client in frontend | | | ✓ | | |
| FastMCP in-process server | | | | ✓ | |
| hello_world tool function | | | | ✓ | |
| Docker Compose 2 services | | | | | ✓ |
| Volume-mounted hot-reload | | | | | ✓ |
| Makefile dev shortcuts | | | | | ✓ |
| .env.example + .gitignore | | | | | ✓ |

## Dependency Graph

```
docker-infrastructure (C05)
  ├── health-check (C01)     — backend service depends on config + health
  ├── data-models (C02)      — models imported by startup
  ├── chat-api-stub (C03)    — router mounted in app factory
  └── fastmcp-server (C04)   — MCP tools initialized on startup
```

All capability-level specs are leaf nodes — they have no intra-change dependencies beyond the shared monorepo layout defined in the proposal.

## Success Criteria

- [ ] `make dev` starts both services without errors
- [ ] `curl localhost:8000/health` returns 200 with `{"status": "ok"}`
- [ ] React app renders at localhost:5173 with "Protección Inteligente 360°" header
- [ ] FastMCP hello_world tool responds to invocations
- [ ] All 12 SQLAlchemy models created in SQLite on startup
- [ ] Frontend layout renders Header + Layout + ChatPanel placeholder
