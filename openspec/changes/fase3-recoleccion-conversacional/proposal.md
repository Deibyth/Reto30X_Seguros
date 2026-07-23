# Proposal: Fase 3 — Recolección Conversacional de Datos de Crédito

## Intent

Eliminar la digitación manual del formulario de crédito persona natural. El usuario **no** sube ningún PDF — el sistema usa un `FormSchema` interno como guía, y el AI recolecta los campos uno a uno conversacionalmente por el chat, llenando `session.campos_diligenciados` progresivamente. Cuando todos los requeridos están completos, el AI pregunta confirmación y ejecuta `create_application()`.

## Scope

### In Scope
1. **FormSchema**: definición estructurada de todos los campos del formulario de crédito (secciones, campos, tipos, required/optional, validaciones, orden de pregunta)
2. **ChatService modificado**: system prompt del AI incluye FormSchema + instrucciones de recolección progresiva + tracking de completitud
3. **Tracking de estado**: `session.campos_diligenciados` se actualiza con cada turno; el AI sabe qué falta y qué está completo
4. **Tool `create_application()`**: AI detecta que todos los REQUERIDOS están completos, pregunta confirmación, y al aceptar crea Application + Credit

### Out of Scope
- Subida de PDFs, OCR, o cualquier extracción de documentos
- Frontend changes (el chat actual ya funciona para este flujo)
- Formulario UI dedicado de captura
- Notificaciones push o recordatorios de campos faltantes
- Validación backend de completitud (el AI es responsable)

## Capabilities

### New Capabilities
- `form-data-collection`: FormSchema en JSON con secciones/campos/tipos/validaciones/orden; lógica de recolección progresiva por el AI; tracking de completitud de campos requeridos

### Modified Capabilities
- `chat-api-stub`: system prompt inyectado con FormSchema completo + instrucciones de recolección conversacional; respuesta incluye `campos_actualizados` en metadata para trazabilidad
- `chat-sessions`: `session.campos_diligenciados` se actualiza progresivamente turno a turno; el AI evalúa completitud contra el FormSchema
- `mcp-domain-tools`: nueva tool `create_application(tipo, customer_id, form_data, monto, plazo, destino)` agregada

## Approach

1. **FormSchema** (`backend/app/schemas/credit_form.py`): lista de secciones, cada sección con lista de campos. Cada campo tiene: `nombre`, `tipo` (string|number|date|email|select), `requerido`, `validaciones` (min/max/pattern/enum), `prompt_question` (cómo preguntarlo), `seccion`. El schema es el contrato que el AI usa para guiar la conversación.

2. **System Prompt**: en `backend/app/services/chat.py`, el system prompt del AI incluye el FormSchema serializado e instrucciones: "Preguntá los campos de a uno, en orden lógico por sección. No preguntes opcionales hasta después de los requeridos. Cuando todos los REQUERIDOS estén completos, resumí y preguntá '¿Confirmás la solicitud?'."

3. **Tool Bridge**: `create_application()` recibe el form_data completo, crea `Application` + `Credit` en una transacción, limpia `session.campos_diligenciados` y marca `estado_actual = "completado"`.

4. **Completitud**: es responsabilidad del AI comparar campos recolectados contra el FormSchema. No hay guard backend de "todos los campos presentes" — el AI decide cuándo está listo.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/schemas/credit_form.py` | New | FormSchema con todos los campos del formulario de crédito |
| `backend/app/services/chat.py` | Modified | System prompt con FormSchema + instrucciones de recolección |
| `backend/app/tools/domain_tools.py` | Modified | Agregar `create_application()` — recibe form_data, crea Application + Credit |
| `backend/app/services/tool_bridge.py` | Modified | (si necesario) soporte para tool sin ORM directo |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| AI saltea campos requeridos | Med | System prompt con checklist; Qwen2-7B fine-tuned para seguir esquemas |
| AI alucina valores no preguntados | Low | Tool recibe solo lo que el AI declara; log de campos para auditoría |
| FormSchema cambia post-MVP | Low | Schema versionado en JSON; cambiar schema = cambiar prompt |
| Usuario da info incompleta (ej. "no sé mi salario") | Med | AI debe preguntar "¿Podés aproximarlo?" o pasar al siguiente campo |

## Rollback Plan

1. Revertir `backend/app/services/chat.py` — restaurar system prompt sin FormSchema
2. Revertir `backend/app/tools/domain_tools.py` — eliminar `create_application()`
3. Eliminar `backend/app/schemas/credit_form.py`
4. Sessions con datos parciales quedan huérfanas — se limpian via admin endpoint o expiran naturalmente

## Dependencies

- Ninguna externa nueva
- Depende de `chat-sessions` + `mcp-domain-tools` (Fase 2) para session.campos_diligenciados y tools base

## Success Criteria

- [ ] FormSchema definido cubre todos los campos del formulario de crédito persona natural
- [ ] AI pregunta campos de a uno en orden lógico por sección
- [ ] `session.campos_diligenciados` se actualiza progresivamente con cada respuesta
- [ ] AI detecta completitud de requeridos y pregunta "¿Confirmás la solicitud?"
- [ ] `create_application()` tool crea Application + Credit correctamente y limpia la session
