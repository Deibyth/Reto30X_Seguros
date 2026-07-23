# Design: Fase 2 — Chat IA Real + MCP Domain Tools + Sesiones + Chat UI

## Technical Approach

Replace echo stub with a `ChatService` layer that orchestrates AI calls, tool execution (via `ToolBridge`), session persistence, and state tracking. Five new MCP domain tools expose ORM queries as AI-consumable functions. Frontend upgrades from placeholder to full chat UI with TanStack Query + framer-motion. References specs C03, C06, C07, C08, C09.

## Architecture Decisions

| Decision | Options | Choice | Rationale |
|----------|---------|--------|-----------|
| Tool introspection | Manual parallel list / auto from `mcp._tool_manager` | **Auto-derive** | Adding a tool via `@mcp.tool()` auto-registers — no manual sync, zero drift, follows existing pattern |
| Tool return format | Dict (MCP-native) / Formatted string | **Formatted string** | AI consumes tool results as text; avoids JSON parsing at token level; matches task spec |
| ChatService scope | New module with dependency injection | **`ChatService(session_maker, ai_client, tool_bridge)`** | Testable, decoupled from FastAPI request cycle; pattern aligns with existing AIClient design |
| Session ID transport | Request body / Header | **`X-Session-Id` header** | Pure transport metadata, not message data; existing stub already uses this pattern |
| Frontend state | Zustand / React state | **`useState` messages + `useMutation`** | Local component state only; no global store needed for single chat panel |
| AI timeout | None / 30s hard limit | **30s `asyncio.wait_for`** | Prevents hung requests blocking uvicorn worker; matches spec C08 timeout guard |

## Data Flow

```
  ChatPanel ──useMutation──→ POST /api/chat (Vite proxy)
                                  │
                              router/chat.py
                                  │
                          ChatService.process_message()
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
           get_or_create    load_history    AIClient
           _session()       (limit=20)      .chat_with_tools()
                    │             │             │
                    ▼             ▼             ▼
                Session        Conversation  SiliconFlow
                table          table           API
                                               │
                                    ┌──────────┴──────────┐
                                    ▼                     ▼
                             tool_calls?             No tools →
                             ToolBridge              Phase 1 reply
                             .execute_tool()         (final)
                                    │
                                    ▼
                             AIClient.chat()
                             [Phase 2] ──→ final reply
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
             persist user      persist AI       update session
             msg (rol=user)    reply(assistant)  estado_actual
```

## Sequence: Full Chat Turn (Tool-Calling)

```
User  ChatPanel  ChatService  AIClient  ToolBridge  DB
 │       │           │           │          │         │
 │──msg──│           │           │          │         │
 │       │──POST─────│           │          │         │
 │       │           │──get_session─────────│────────►│
 │       │           │──load_history────────│────────►│
 │       │           │──Phase1: chat_with_tools──►    │
 │       │           │           │          │         │
 │       │           │◄──tool_calls──────────          │
 │       │           │──execute_tool(name,args)──►     │
 │       │           │           │          │─query──►│
 │       │           │◄──result───────────────         │
 │       │           │──Phase2: chat(hist+result)──►   │
 │       │           │◄──final reply────               │
 │       │           │──persist(user_msg+reply)───►    │
 │       │           │──update_session_state──────►    │
 │       │◄──ChatResult────────────────────────────────│
 │       │──update messages[]                          │
 │◄──reply──────────────────────────────────────────── │
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/services/__init__.py` | Create | Package marker |
| `backend/app/services/chat.py` | Create | `ChatService` class with session, history, two-phase AI loop |
| `backend/app/services/tool_bridge.py` | Create | FastMCP → OpenAI tool converter + `execute_tool()` |
| `backend/app/tools/domain_tools.py` | Create | 5 `@mcp.tool()` functions: `get_products`, `get_customer`, `check_eligibility`, `simulate_credit`, `get_insurance` |
| `backend/app/tools/mcp_server.py` | Modify | Import domain tools; `hello_world` kept for backward compat |
| `backend/app/routers/chat.py` | Modify | Use `ChatService` instead of `AIClient.chat()` directly; return `model`, handle 404 for invalid sessions |
| `frontend/src/components/chat/ChatPanel.tsx` | Rewrite | Real UI: message list, input, typing indicator, error banner |
| `frontend/src/lib/api.ts` | Modify | Add `model` field to `ChatResponse`, optional `X-Session-Id` header management |

## Interfaces / Contracts

### `ChatService`
```python
# app/services/chat.py
@dataclass
class ChatResult:
    session_id: str
    reply: str
    model: str
    timestamp: datetime

class ChatService:
    def __init__(self, session_maker: async_sessionmaker,
                 ai_client: AIClient, tool_bridge: ToolBridge) -> None

    async def get_or_create_session(
        self, session_id: str | None, customer_id: str | None = None
    ) -> Session

    async def load_history(self, session_id: str, limit: int = 20) -> list[ChatMessage]

    async def process_message(self, session: Session,
                              user_message: str) -> ChatResult
```

### `ToolBridge`
```python
# app/services/tool_bridge.py
class ToolBridge:
    def __init__(self, mcp: FastMCP) -> None  # consumes FastMCP instance
    def get_openai_tools(self) -> list[dict]   # reads mcp._tool_manager
    async def execute_tool(self, name: str, args: dict) -> str
```

### Updated `ChatResponse`
```python
class ChatResponse(BaseModel):
    reply: str
    timestamp: datetime
    session_id: str
    model: str
```

### Updated `ChatResponse` (TypeScript)
```typescript
interface ChatResponse {
  reply: string
  timestamp: string
  session_id: string
  model: string
}
```

## Domain Tools Detail

Each tool opens its own `async with async_session_maker() as session:`, queries ORM, returns a **formatted string** (not raw JSON). All five in `app/tools/domain_tools.py`.

- `get_products(tipo=None)` — joins `Product` + `Insurance` by `tipo` filter; returns `"Producto: {nombre} — {descripcion}"` per row
- `get_customer(documento_identidad)` — queries `Customer` by `documento_identidad`; returns `"Cliente: {nombre_completo}, salario: {salario}"` or `"Cliente no encontrado"`
- `check_eligibility(customer_id)` — loads customer, checks `salario >= 1_000_000`, `tipo_contrato in ("indefinido","fijo")`, `antiguedad_meses >= 6`; returns `"Elegible: sí/no. Razones: ..."`
- `simulate_credit(monto, plazo)` — pure math: `cuota = monto * (tasa/12) / (1 - (1+tasa/12)^(-plazo))` with fixed `TASA_ANUAL = 0.18`; returns `"Cuota mensual: $X. Interés total: $Y. Total: $Z."`
- `get_insurance(insurance_id)` — queries `Insurance` by `id`; returns `"Seguro: {nombre}. Cobertura: {cobertura}. Prima base: ${prima_base}"`

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | `ToolBridge.get_openai_tools()` | Assert 5 tools returned, each has `name, description, parameters` matching domain tools |
| Unit | `ToolBridge.execute_tool()` | Mock domain tool fn, assert call delegation; test unknown name raises ValueError |
| Unit | `simulate_credit` math | Assert known inputs produce expected monthly payment using fixed rate |
| Integration | `ChatService` with mocked AI | Assert session created if none provided, history loaded, user+assistant persisted |
| Integration | Full POST /chat | TestClient post with `X-Session-Id`, assert response shape |
| Frontend | `ChatPanel` render | Assert input, send button, typing indicator, error banner render at correct times |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. The `POST /chat` route is an existing HTTP endpoint with no dynamic command execution or shell integration.

## Migration / Rollout

No data migration. Existing echo sessions are ephemeral (no persistence). Backward-compatible: `session_id` becomes required (new behavior), but existing clients without it will auto-create a new session. Rollback: revert `chat.py`, `ChatPanel.tsx`, `api.ts` to Fase 1 baseline; keep new files as dead code.

## Open Questions

- [ ] Eligibility rules: what exact thresholds for `salario`, `antiguedad_meses`, and `tipo_contrato`? Placeholder values used — validate with business.
- [ ] Fixed interest rate: `18%` annual assumed for `simulate_credit` — confirm or make configurable.
- [ ] Should `hello_world` remain registered alongside domain tools, or remove it?
