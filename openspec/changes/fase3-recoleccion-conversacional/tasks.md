# Tasks: Fase 3 — Recolección Conversacional de Datos de Crédito

## Review Workload Forecast

| Guard | Value |
|-------|-------|
| Decision needed before apply | **No** — single PR, changes are well-scoped |
| Chained PRs recommended | **No** — ~250-300 lines total, no architectural split point |
| 400-line budget risk | **Low** — authored lines estimated ~275 max |
| Risk level | **Low-Medium** — FormSchema is new code (~54 fields), ChatService is modified |
| Single PR expected | **Yes** — all tasks share a single delivery path |

Forecast rationale: FormSchema (~80 lines) is standalone. Tools (~70 lines) and session column (~3 lines) are additive. ChatService changes (~60 lines) touch the most critical existing code. Router extended (~10 lines). No frontend. No DB migration tooling needed (SQLite additive column).

---

## Phases

### Phase 1: FormSchema — Foundation

**1.1 — Create package init**
`backend/app/schemas/__init__.py`
- Empty package init.
- No existing `schemas/` directory exists — create it.

[x] — Done

**1.2 — Create FormSchema**
`backend/app/schemas/credit_form.py`
- Define `FormField` dataclass: `nombre`, `tipo` (Literal["string","number","date","email","select"]), `requerido: bool`, `prompt_question: str`, `seccion: str`, `validaciones: dict | None`, `desde_customer: str | None`
- Define `FormSeccion` dataclass: `nombre: str`, `campos: list[FormField]`
- Define `FormSchema` class:
  - Class constant `VERSION = "1.0"`
  - `secciones: list[FormSeccion]` — at minimum: `Datos Personales` (nombre, documento, email, telefono), `Información Financiera` (salario), `Solicitud` (monto_solicitado, plazo, destino)
  - `to_prompt_text()` — serializes JSON with `ensure_ascii=False`, indented, for AI prompt injection
  - `campos_requeridos()` — returns only `requerido=True` fields
  - `campos_opcionales()` — returns only `requerido=False` fields
  - `campos_desde_customer()` — maps field names to Customer columns (e.g. `{"nombre": "nombre_completo", "salario": "salario", "email": "email"}`)
- All field `tipo` values must use `string`, not `str`, to match the Literal type.

[x] — Done (9 secciones, 54 campos total, todos los campos del formulario original)

### Phase 2: Session Model — Schema Evolution

**2.1 — Add form_schema_version column**
`backend/app/models/session.py`
- Add `form_schema_version: Mapped[str | None] = mapped_column(String(10), nullable=True)` after `fecha_nacimiento` or `ultima_intencion`.
- No existing migration framework — additive column, SQLite ignores nullable additions. The column must be nullable to support existing sessions.

[x] — Done (added after `ultima_intencion`)

### Phase 3: Domain Tools — New MCP Tools

**3.1 — Add save_form_field tool**
`backend/app/tools/domain_tools.py`
- `@mcp.tool() async def save_form_field(session_id: str, campo: str, valor: str | float | None) -> str`
- Opens own `async_session_maker()` session, loads `Session` by ID, merges `{campo: valor}` into `session.campos_diligenciados`, commits.
- Returns `"ok"` on success or error string.
- If `session_id` not found, returns error message, not exception.
- If `valor` is `None`, saves explicitly as `None` (user skipped optional field).

[x] — Done

**3.2 — Add create_application tool**
`backend/app/tools/domain_tools.py`
- `@mcp.tool() async def create_application(tipo: str, customer_id: str, form_data: dict, monto_solicitado: float, plazo_meses: int, destino: str) -> str`
- Opens own `async_session_maker()`, creates `Application(tipo=tipo, customer_id=customer_id, form_data=form_data, estado="iniciada")` + `Credit(application_id=app.id, monto_solicitado=monto_solicitado, plazo_meses=plazo_meses, destino=destino, tasa_interes=<default from config or None>)` in a single atomic transaction (same session, flush before creating Credit to get app.id).
- If `form_data.get("document_id")` is present, set `Application.document_id` and link `Document.application_id`.
- Returns application ID string on success, error string on failure.
- Import `Application` from `app.models.application`.
- Import `Credit` from `app.models.credit`.
- Import `Document` from `app.models.document`.

[x] — Done
[+] — Added `document_id` column to `Application` model (needed for document linking)

### Phase 4: ChatService — Dynamic Prompt & Form-Aware Logic

**4.1 — Build dynamic system prompt**
`backend/app/services/chat.py`
- In `process_message()`, build a dynamic system prompt string that includes:
  1. Base persona instructions (reuse logic from `SYSTEM_PROMPT` in `client.py`)
  2. Complete `FormSchema.to_prompt_text()` — the serialized schema
  3. Current customer context if `session.customer_id` is set: "El cliente ya identificado es: {customer name}, con estos datos pre-completados: {fields from customer}"
  4. Current collection state: "Campos ya recolectados: {list}. Por recolectar (requeridos): {list}."
  5. Tool instructions: "Usá `save_form_field(session_id, campo, valor)` para cada campo que el usuario responda. No preguntes múltiples campos en un turno. Cuando todos los REQUERIDOS estén completos, presentá un resumen y preguntá '¿Confirmás la solicitud?'."
- Pass `system_prompt` to `chat_with_tools()` call in Phase 1.
- In Phase 2, replace the hardcoded `SYSTEM_PROMPT` with the dynamic prompt as the first message.

[x] — Done

**4.2 — Replace _update_session_state with form-aware state machine**
`backend/app/services/chat.py`
- Replace the keyword-based `_update_session_state()` with a new state machine:
  - `inicio` → AI calls `get_customer()` → `validando_afiliacion`
  - `validando_afiliacion` → customer confirmed + first form field asked → `recolectando_datos`
  - `recolectando_datos` → AI calls `create_application()` with confirmation → completion handling
  - `completado` → terminal state
- Remove the old intent detection keyword matching.
- After a successful `create_application()` tool execution, clear `session.campos_diligenciados = {}` and set `session.estado_actual = "completado"` in the same DB session as the tool call (or a subsequent atomic update).
- When session enters `recolectando_datos`, set `session.form_schema_version = FormSchema.VERSION`.

[x] — Done

**4.3 — Parse campos_actualizados and compute completitud_pct**
`backend/app/services/chat.py`
- After Phase 2 AI reply, detect if `save_form_field` was called in Phase 1 tool calls:
  - If tool name is `save_form_field`, extract `campo` from arguments → add to `campos_actualizados` list.
  - If no tool calls, `campos_actualizados = []`.
- Compute `completitud_pct` = `(len(collected_required) / len(all_required_fields)) * 100` where collected required fields are those with non-None values in `session.campos_diligenciados` matching `FormSchema.campos_requeridos()`.
- Extend `ChatResult` dataclass with `campos_actualizados: list[str]` and `completitud_pct: float` (default `0.0` and `[]`).

[x] — Done

### Phase 5: Chat Router — Extended Response

**5.1 — Add campos_actualizados and completitud_pct to ChatResponse**
`backend/app/routers/chat.py`
- Add `campos_actualizados: list[str] = Field(default_factory=list)` to `ChatResponse`.
- Add `completitud_pct: float = Field(default=0.0)` to `ChatResponse`.
- In the chat handler, map `result.campos_actualizados` and `result.completitud_pct` to the response.
- Return empty list/`0.0` for echo fallback path.

[x] — Done

---

## Implementation Order

1. **Phase 1** (1.1 → 1.2) — Foundation, no deps
2. **Phase 2** (2.1) — Model change, independent
3. **Phase 3** (3.1 → 3.2) — Tools, depend on models existing
4. **Phase 4** (4.1 → 4.2 → 4.3) — Service logic, depends on Phases 1-3
5. **Phase 5** (5.1) — Router, depends on Phase 4 (ChatResult fields)

Phases 1, 2, and 3 can be implemented in parallel. Phase 4 depends on all three. Phase 5 depends on Phase 4.

## Files Changed (Summary)

| File | Action | Task |
|------|--------|------|
| `backend/app/schemas/__init__.py` | **Create** | 1.1 |
| `backend/app/schemas/credit_form.py` | **Create** | 1.2 |
| `backend/app/models/session.py` | **Modify** | 2.1 |
| `backend/app/tools/domain_tools.py` | **Modify** | 3.1, 3.2 |
| `backend/app/services/chat.py` | **Modify** | 4.1, 4.2, 4.3 |
| `backend/app/routers/chat.py` | **Modify** | 5.1 |
| `backend/app/models/application.py` | **Modify** | 3.2 (add document_id column) |
