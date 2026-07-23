# Design: Fase 3 — Recolección Conversacional

## Technical Approach

Replace keyword-based session tracking with a **FormSchema-driven AI conversation** for credit data collection. The AI uses a structured schema (injected into its system prompt) to guide the conversation field by field. A new tool `save_form_field` records each collected datum into `session.campos_diligenciados`. The AI validates completeness against the schema and, when all required fields are filled, calls `create_application` to persist Application + Credit atomically.

Session state states: `inicio → validando_afiliacion → recolectando_datos → completado`.

## Architecture Decisions

### Decision: FormSchema format — Python dataclass + JSON serialization

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Pydantic model | Already in stack, validation baked in | ✅ **Chosen** — no new deps, consistent with FastAPI/Pydantic patterns |
| Raw dict | Less structure, no validation | ❌ Rejected — needs `by_seccion()`, `requeridos()`, etc. |
| YAML file | External config, harder to version with code | ❌ Rejected — schema IS code, changes with app logic |

FormSchema lives in `backend/app/schemas/credit_form.py`. Exposes `to_prompt_text()` for system prompt injection and `fields_from_customer()` to identify which fields are pre-filled from Customer data.

### Decision: AI reports progress via tool calls, not text parsing

| Option | Tradeoff | Decision |
|--------|----------|----------|
| AI includes `[CAMPO: x=y]` in reply text | Fragile, model-dependent format | ❌ Rejected |
| AI calls `save_form_field` tool | Structured, reliable, auditable | ✅ **Chosen** — MCP tool, same pattern as existing tools |
| Backend parses all AI text | Not future-proof, misses nuanced responses | ❌ Rejected |

New MCP tool `save_form_field(session_id, campo, valor)` persists each field as collected. The AI calls it after the user provides a value. `ChatService` tracks `campos_actualizados` from tool invocations and returns them in the response metadata.

### Decision: Dynamic system prompt built per-request in ChatService

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Static SYSTEM_PROMPT in client.py | Cannot include session state or schema | ❌ Rejected |
| Build prompt in ChatService.process_message() | Has full context (session, schema, state) | ✅ **Chosen** — passes to `chat_with_tools(system_prompt=...)` |
| Template with placeholders replaced | Less flexible for conditional sections | ❌ Rejected |

`ChatService.process_message()` builds the system prompt string that includes: base instructions + FormSchema (`to_prompt_text()`) + customer context (name, pre-filled fields) + current collection state + instructions for tool usage. The `AIClient` already accepts `system_prompt` override in both `chat_with_tools()` and `chat_raw()`.

## Data Flow

```
User                    ChatService                    AI (Qwen2)              Database
 │                          │                             │                      │
 │  "Quiero un crédito"     │                             │                      │
 │ ───────────────────────► │                             │                      │
 │                          │  build dynamic system       │                      │
 │                          │  prompt with FormSchema     │                      │
 │                          │  + instrucciones            │                      │
 │                          │                             │                      │
 │                          │  Phase 1: chat_with_tools   │                      │
 │                          │ ─────────────────────────► │                      │
 │                          │ ◄───────────────────────── │ tool: get_customer() │
 │                          │                             │                      │
 │                          │  execute get_customer()     │                      │
 │                          │ ─────────────────────────────────────────────►    │
 │                          │ ◄─────────────────────────────────────────────    │
 │                          │                             │                      │
 │                          │  Phase 2: chat_raw w/       │                      │
 │                          │  tool result                │                      │
 │                          │ ─────────────────────────► │                      │
 │                          │ ◄───────────────────────── │ "¿Cuál es tu doc?"   │
 │                          │                             │                      │
 │  "1234567890"            │                             │                      │
 │ ◄─────────────────────── │                             │                      │
 │ ───────────────────────► │                             │                      │
 │                          │  Phase 1: chat_with_tools   │                      │
 │                          │ ─────────────────────────► │                      │
 │                          │ ◄───────────────────────── │ tool: get_customer() │
 │                          │                             │                      │
 │                          │  execute get_customer("123")│                      │
 │                          │ ─────────────────────────────────────────────►    │
 │                          │ ◄─────────────────────────────────────────────    │
 │                          │  → customer found!                                │
 │                          │  → session.customer_id = "cust-uuid"              │
 │                          │                             │                      │
 │                          │  Phase 2: chat_raw w/       │                      │
 │                          │  customer data              │                      │
 │                          │ ─────────────────────────► │                      │
 │                          │ ◄───────────────────────── │ "¡Hola Juan!"        │
 │                          │                             │  "¿Cuál es tu        │
 │                          │                             │   dirección?"        │
 │                          │                             │                      │
 │  [field by field...]     │                             │                      │
 │                          │  AI calls save_form_field()  │                      │
 │                          │  for each collected datum   │                      │
 │                          │ ─────────────────────────────────────────────►    │
 │                          │                             │                      │
 │  (all required fields    │                             │                      │
 │   collected)             │                             │                      │
 │                          │  AI asks "¿Confirmás?"      │                      │
 │ ◄─────────────────────── │                             │                      │
 │  "Confirmo"              │                             │                      │
 │ ───────────────────────► │                             │                      │
 │                          │  AI calls create_application()  │                  │
 │                          │ ─────────────────────────────────────────────►    │
 │                          │ ◄─────────────────────────────────────────────    │
 │                          │  → Application + Credit created                   │
 │                          │  → session cleanup                                │
 │                          │                             │                      │
 │  "¡Solicitud creada!"   │                             │                      │
 │ ◄─────────────────────── │                             │                      │
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/schemas/__init__.py` | Create | Package init |
| `backend/app/schemas/credit_form.py` | Create | `FormSchema` class: sections, fields, validations, `to_prompt_text()`, `fields_from_customer()` |
| `backend/app/models/session.py` | Modify | Add `form_schema_version: Mapped[str]` column |
| `backend/app/services/chat.py` | Modify | Replace `_update_session_state()` with form-aware logic; build dynamic system prompt; parse `campos_actualizados` from tool calls; compute `completitud_pct` |
| `backend/app/tools/domain_tools.py` | Modify | Add `save_form_field(session_id, campo, valor)` and `create_application(tipo, customer_id, form_data, monto_solicitado, plazo_meses, destino)` |
| `backend/app/routers/chat.py` | Modify | Extend `ChatResponse` with `campos_actualizados: list[str]` and `completitud_pct: float` |

## Interfaces / Contracts

```python
# backend/app/schemas/credit_form.py

@dataclass
class FormField:
    nombre: str
    tipo: Literal["string", "number", "date", "email", "select"]
    requerido: bool
    prompt_question: str
    seccion: str
    validaciones: dict | None = None      # {"min": 0, "max": 1e9, "pattern": "...", "enum": [...]}
    desde_customer: str | None = None     # Customer field name if pre-filled, e.g. "salario"

@dataclass
class FormSeccion:
    nombre: str
    campos: list[FormField]

class FormSchema:
    VERSION = "1.0"
    secciones: list[FormSeccion]

    def to_prompt_text(self) -> str: ...
    def campos_requeridos(self) -> list[FormField]: ...
    def campos_opcionales(self) -> list[FormField]: ...
    def campos_desde_customer(self) -> dict[str, str]: ...  # {"nombre": "nombre_completo", ...}
```

**Tool schemas** (OpenAI format, auto-generated by FastMCP):

```
save_form_field(session_id: str, campo: str, valor: str | float | None) → str
  - Persists a single field into session.campos_diligenciados (merge/upsert).
  - Returns: "ok" or error message.

create_application(tipo: str, customer_id: str, form_data: dict,
                   monto_solicitado: float, plazo_meses: int, destino: str) → str
  - Creates Application + Credit in atomic transaction.
  - Returns: application_id on success, error on failure.
```

**Extended ChatResponse**:
```json
{
  "reply": "¡Hola Juan! ¿Cuál es tu dirección de residencia?",
  "session_id": "abc-123",
  "campos_actualizados": ["direccion"],
  "completitud_pct": 45.0
}
```

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | `FormSchema` serialization, field query methods | Pure Python tests — `test_credit_form.py` |
| Unit | `save_form_field` merge logic | Test with mocked DB session |
| Integration | `create_application()` atomic transaction | Test with real SQLite, verify rollback on FK violation |
| Integration | Full flow: validate → collect → confirm | Test with `AIClient` stub that returns canned tool calls, verify session state transitions |
| E2E | `POST /chat` returns `campos_actualizados` and `completitud_pct` | Hit real endpoint with mock AI responses |

**Not applicable** — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No data migration needed. Existing sessions continue with the old `_update_session_state` keyword-based logic until they hit `recolectando_datos` state, at which point the new FormSchema-driven flow takes over.

1. Deploy schema change (`form_schema_version` column) — additive, no downtime
2. Deploy `FormSchema` + tools (`save_form_field`, `create_application`)
3. Deploy `ChatService` changes — system prompt now includes FormSchema
4. Existing sessions remain valid; new sessions get the full flow

Rollback: revert `ChatService` to use `SYSTEM_PROMPT` constant, remove new tools. `form_schema_version` column stays (nullable, unused).

## Open Questions

- [ ] What is the exact list of FormSchema fields and sections? Needs SME input for the complete credit form.
- [ ] `save_form_field` opens its own DB session — is there a race condition risk if the AI calls it twice in quick succession? Should we add a lock or use `ChatService`'s session instead?
- [ ] Should `completitud_pct` include optional fields in the denominator, or only required fields?
- [ ] Rate limiting: the AI might call `save_form_field` per field — ~20-30 calls per session. Acceptable for MVP?
