---
type: tech
updated_at: 2026-07-16
---

# Technology Stack

## Tooling Conventions

- **Python environment**: `python -m venv` (standard library, no poetry/pipenv/conda)
- **Python server**: `uvicorn` (ASGI runner)
- **Frontend package manager**: `pnpm` exclusively (never npm or yarn)
- **Python dependencies**: `pip` via `requirements.txt` (no poetry/pipenv lockfiles)

## Frontend
| Technology | Purpose |
|-----------|---------|
| React 18+ | UI Framework |
| Vite | Build tool |
| pnpm | Package manager |
| TypeScript | Type safety |
| TailwindCSS | Styling |
| shadcn/ui | Component library |
| TanStack Query | Server state management |
| React Hook Form | Admin forms (if needed) |
| Framer Motion | Animations |

## Backend
| Technology | Purpose |
|-----------|---------|
| FastAPI | API Gateway + Streaming |
| uvicorn | ASGI server |
| Pydantic v2 | Data validation |
| SQLAlchemy | ORM |
| SQLite | Database (MVP) |
| python-venv | Virtual environment |
| FastMCP | MCP Server / Tools |
| python-dotenv | Environment config |

## AI / Agents
| Technology | Purpose |
|-----------|---------|
| OpenAI Responses API | LLM backend |
| FastMCP | Tool exposure |
| LangGraph | Agent orchestration (optional, MVP sin él) |

## OCR
| Technology | Purpose |
|-----------|---------|
| Pillow | Image processing |
| pytesseract | Text extraction |

## Document Handling
| Technology | Purpose |
|-----------|---------|
| python-multipart | File uploads |
| aiofiles | Async file I/O |

## Infrastructure
| Technology | Purpose |
|-----------|---------|
| Docker | Containerization |
| Railway / Render | Hosting (MVP) |
| Azure App Service | Future hosting |

## Domain Modules
```
customers/
credits/
insurance/
claims/
documents/
notifications/
opportunities/
shared/
```

## Session Memory Model
```json
{
  "cliente": {},
  "producto": null,
  "estado": "DISCOVERY",
  "campos_diligenciados": {},
  "campos_faltantes": [],
  "ultima_intencion": null,
  "documentos": [],
  "historial": []
}
```
