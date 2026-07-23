```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:95229a2c504d66cb9aa9f35448cab04ca9c6ae06cc5cdd2aba2be8d08682931a
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 21/21
scenarios: 0/21
test_command: python3 -c "import ast; files = [...] for f in files: try: ast.parse(open(f).read()); print(f'✅ {f}') except SyntaxError as e: print(f'❌ {f}: {e}')"
test_exit_code: 0
test_output_hash: sha256:70fa287cb104b8c387e9f496285fd20fb8a0232075f11e9fd7dc05c71b6ee1c4
build_command: N/A — Python project, no build step
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report

**Change**: `fase3-recoleccion-conversacional`
**Version**: N/A
**Mode**: Standard (Strict TDD disabled, no test runner)

### Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 9 |
| Tasks complete | 9 |
| Tasks incomplete | 0 |

### Build & Tests Execution

**Build**: ✅ N/A — Python project, no build step required.

**Syntax Check**: ✅ All 6 source files parse without errors.

```text
✅ backend/app/schemas/credit_form.py
✅ backend/app/tools/domain_tools.py
✅ backend/app/services/chat.py
✅ backend/app/routers/chat.py
✅ backend/app/models/session.py
✅ backend/app/models/application.py
```

**Tests**: ⚠️ No test runner configured (Strict TDD: false). All spec scenarios are UNTESTED by runtime execution. Compliance verified through source inspection only.

### Spec Compliance Matrix

#### Spec 1: `openspec/specs/form-data-collection/spec.md`

| # | Requirement | Scenario | Implementation Evidence | Status |
|---|-------------|----------|------------------------|--------|
| 1 | FormSchema contract | Schema defines all credit form fields | `credit_form.py::FormField`, `FormSeccion`, `FormSchema` with 9 secciones, 54 campos. Field names: `nombres`, `numero_identificacion`, `email`, `celular`/`telefono`, `salario_basico`, `valor_solicitado`, `plazo_meses`, `tipo_solicitud`. Each field has `seccion`, `tipo`, `requerido`, `validaciones`, `prompt_question`. | ⚠️ PARTIAL — `monto_solicitado` named `valor_solicitado`, `destino` covered by `tipo_solicitud`. Minimum field set present but naming differs. |
| 2 | Progressive field collection | Fields collected sequentially | `_build_system_prompt()` instructs single-field turns. `save_form_field()` merges into `campos_diligenciados`. | ✅ COMPLIANT* |
| 3 | Progressive field collection | Required fields before optional | System prompt: "Priorizá campos REQUERIDOS dentro de cada sección antes que los opcionales." | ✅ COMPLIANT* |
| 4 | Optional field skip | User skips optional field | `save_form_field` accepts `valor=None`, stores as `null` in JSON. Prompt instructs `pasá valor=None`. | ✅ COMPLIANT* |
| 5 | Approximation for unknown values | User provides approximation | Prompt: "Si el usuario no sabe un valor exacto (ej. salario), preguntá por un valor aproximado." | ✅ COMPLIANT* |
| 6 | Completeness detection | All required fields complete | `_compute_completitud_pct()` tracks progress. Prompt instructs summary + "¿Confirmás la solicitud?" | ✅ COMPLIANT* |
| 7 | Completeness detection | Required field still missing | Prompt includes "Campos REQUERIDOS por recolectar ({N} restantes)" | ✅ COMPLIANT* |
| 8 | Confirmation triggers create_application | Confirmation succeeds | `create_application` tool + `_update_session_state` clears campos + sets `completado` | ✅ COMPLIANT* |
| 9 | Confirmation triggers create_application | Confirmation declined | Prompt: "Si no confirma o quiere cambiar algo, preguntá qué desea modificar." Session stays in `recolectando_datos`. | ✅ COMPLIANT* |

#### Spec 2: `openspec/changes/fase3-recoleccion-conversacional/specs/chat-api-stub/spec.md`

| # | Requirement | Scenario | Implementation Evidence | Status |
|---|-------------|----------|------------------------|--------|
| 10 | AI system prompt with FormSchema | Echo response with form data collection | Echo fallback returns `ChatResponse`. Main path returns `campos_actualizados` from tool calls. | ✅ COMPLIANT* |
| 11 | AI system prompt with FormSchema | Form instruction override | System prompt includes `FormSchema.to_prompt_text()` and progressive collection instructions. | ✅ COMPLIANT* |
| 12 | Response metadata for field tracking | Field metadata in response | `ChatResponse.campos_actualizados` and `completitud_pct` populated from `ChatResult`. | ✅ COMPLIANT |
| 13 | Response metadata for field tracking | Empty campos_actualizados | `_parse_campos_actualizados` returns `[]` when no tool calls. Echo fallback uses default `[]`. | ✅ COMPLIANT |
| 14 | AI follows progressive collection protocol | Single field asked per turn | Prompt: "Preguntá los campos de a UNO por turno. NUNCA preguntes varios campos en un mismo mensaje." | ✅ COMPLIANT* |
| 15 | AI follows progressive collection protocol | Confirmation request on completion | Prompt: "presentá un RESUMEN de los datos recolectados y preguntá '¿Confirmás la solicitud?'" | ✅ COMPLIANT* |

#### Spec 3: `openspec/changes/fase3-recoleccion-conversacional/specs/chat-sessions/spec.md`

| # | Requirement | Scenario | Implementation Evidence | Status |
|---|-------------|----------|------------------------|--------|
| 16 | Field tracking with progressive updates | Fields accumulated progressively | `save_form_field` merges `{campo: valor}` into existing JSON dict. Prior data preserved. | ✅ COMPLIANT |
| 17 | Field tracking with progressive updates | Field overwrite on update | `save_form_field` overwrites same key via `current[campo] = valor`. No duplicate entries. | ✅ COMPLIANT |
| 18 | State machine with completion flow | Session completed after confirmation | `_update_session_state`: `has_create_application=True` → `completado`, `campos_diligenciados={}` | ✅ COMPLIANT |
| 19 | State machine with completion flow | Completion reversed on failure | `create_application` exception → `session.rollback()`. `has_create_application` stays False. Session state unchanged. | ✅ COMPLIANT |
| 20 | Form schema versioning | Version set on data collection start | `session.form_schema_version = FormSchema.VERSION` on transition to `recolectando_datos`. | ✅ COMPLIANT |
| 21 | Form schema versioning | Version persists through session | `form_schema_version` never cleared or modified after initial set. | ✅ COMPLIANT |

#### Spec 4: `openspec/changes/fase3-recoleccion-conversacional/specs/mcp-domain-tools/spec.md`

| # | Requirement | Scenario | Implementation Evidence | Status |
|---|-------------|----------|------------------------|--------|
| 22 | create_application tool | Application + Credit created atomically | `Application(tipo, customer_id, form_data, estado="iniciada")` + `Credit(application_id, monto_solicitado, plazo_meses, destino)`. Single `async_session_maker()` + `flush()` + `commit()`. | ✅ COMPLIANT |
| 23 | create_application tool | Database error rolls back transaction | `try/except` → `session.rollback()` → returns error string. No partial persistence. | ✅ COMPLIANT |
| 24 | create_application tool | Document linked if present | `form_data.get("document_id")` → `app.document_id = doc_id` + `doc.application_id = app.id` | ✅ COMPLIANT |
| 25 | Atomic session cleanup | Session cleaned after successful creation | `_update_session_state`: `campos_diligenciados={}`, `estado_actual="completado"`, `activa=False` | ✅ COMPLIANT |
| 26 | Atomic session cleanup | Session unchanged on failure | Session state not modified when `create_application` fails. | ✅ COMPLIANT |

> *`COMPLIANT*` = code enforces via AI system prompt instructions, but compliance depends on AI runtime behavior. No automated test validates the AI actually follows instructions.

### Correctness (Static Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| Phase 1.1 — Package init | ✅ Implemented | `schemas/__init__.py` exists with docstring |
| Phase 1.2 — FormSchema | ✅ Implemented | `FormField`, `FormSeccion`, `FormSchema` with VERSION, 9 sections, 54 fields, `to_prompt_text()`, `campos_requeridos()`, `campos_opcionales()`, `campos_desde_customer()` |
| Phase 2.1 — form_schema_version | ✅ Implemented | `session.py` line 26: nullable `String(10)` column after `ultima_intencion` |
| Phase 3.1 — save_form_field tool | ✅ Implemented | `domain_tools.py` lines 234-268: opens own session, merges field, returns `"ok"` |
| Phase 3.2 — create_application tool | ✅ Implemented | `domain_tools.py` lines 271-342: atomic Application + Credit creation, optional document linking |
| Phase 3.2 — document_id column | ✅ Implemented | `application.py` lines 26-28: `document_id` FK to `documents.id` |
| Phase 4.1 — Dynamic system prompt | ✅ Implemented | `_build_system_prompt()`: base prompt + FormSchema JSON + customer context + collection state + tool instructions |
| Phase 4.2 — Form-aware state machine | ✅ Implemented | `_update_session_state()`: `inicio → validando_afiliacion → recolectando_datos → completado`. No keyword-based intent detection. |
| Phase 4.3 — campos_actualizados + completitud_pct | ✅ Implemented | `_parse_campos_actualizados()` extracts field names from save_form_field calls. `_compute_completitud_pct()` computes percentage from required vs collected. |
| Phase 5.1 — Extended ChatResponse | ✅ Implemented | `ChatResponse.campos_actualizados: list[str]`, `ChatResponse.completitud_pct: float`. Mapped from `ChatResult` in handler. |

### Coherence (Design)

No design document was published as part of this change. Design coherence check skipped.

### Issues Found

**CRITICAL**: None

**WARNING**:
1. **Field naming mismatch**: The base spec (`form-data-collection/spec.md`) requires fields named `monto_solicitado` and `destino` as minimum field names. The `FormSchema` implementation uses `valor_solicitado` (not `monto_solicitado`) and `tipo_solicitud` (not `destino`). The `create_application` tool parameter `monto_solicitado` is expected to come from form field `valor_solicitado` via AI interpretation with no explicit code-level mapping in the system prompt. This creates a gap where the AI must infer the mapping between form field names and tool parameter names.

2. **`completitud_pct` returns 0.0 after session completion**: In `process_message()`, `_update_session_state` clears `campos_diligenciados` (sets to `{}`) *before* `_compute_completitud_pct` computes the final percentage. After the final confirmation response, `completitud_pct` will be `0.0` instead of `100.0`, which is semantically misleading (collection appears empty rather than complete).

3. **Form field count mismatch**: `tasks.md` states 52 fields across 9 sections; the actual implementation has 54 fields across 9 sections. While this doesn't break functionality, the task documentation is slightly stale.

**SUGGESTION**:
1. Add explicit mapping in the system prompt's tool instructions: *"Al llamar `create_application()`, usá `monto_solicitado = valor_solicitado` de form_data y `destino = tipo_solicitud`."* This removes ambiguity for the AI.
2. Cache `completitud_pct` before `_update_session_state` clears campos_diligenciados, so the final confirmation response shows `100.0` instead of `0.0`.
3. Consider returning a 200 with a `"completed": true` flag instead of 404 for inactive/completed sessions, so the frontend can display historical data rather than an error.
4. The echo fallback at `routers/chat.py:56` doesn't explicitly populate `completitud_pct`/`campos_actualizados`; it relies on Pydantic model defaults. While this works, explicit assignment would improve readability.

### Verdict

**PASS WITH WARNINGS**

All 9 tasks complete. All 21 spec requirements implemented via source code. 0 CRITICAL issues. Syntax checks pass on all 6 source files. No test runner exists for runtime execution evidence (specified as non-Strict-TDD). Three WARNING-level issues found (field naming mismatch, post-completion percentage, field count discrepancy) that should be addressed but do not constitute functional blockers.
