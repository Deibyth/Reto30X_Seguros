# Proposal: Fase 3 — Documentos OCR (Carga y Parseo de PDF de Crédito)

## Intent

Eliminar la digitación manual del formulario de crédito persona natural. El usuario sube el PDF digital, el sistema extrae texto con pdfplumber, AI parsea campos estructurados, pre-llena la conversación en el chat, y el usuario confirma/corrige antes de crear la Application.

## Scope

### In Scope
1. Endpoint `POST /api/upload/document` — recibe multipart/form-data con PDF
2. `PDFService` — extracción (pdfplumber) + parseo AI (Qwen2-7B via SiliconFlow)
3. Persistencia del PDF original como `Document` en `data/uploads/`
4. Inyección de campos parseados en `session.campos_diligenciados` para pre-llenar el chat
5. Nueva tool MCP `create_application()` — crea Application + Credit + vincula Document
6. Botón/subida de PDF en `ChatPanel.tsx`
7. `ApiClient.uploadDocument()` en frontend

### Out of Scope
- OCR de PDFs escaneados (solo digital con texto seleccionable)
- Formulario UI dedicado de confirmación (todo va por chat)
- Parseo de otros tipos de documento (seguros, codeudores)
- Validación de integridad del PDF (firma, sellos)

## Capabilities

### New Capabilities
- `ocr-document-upload`: PDF upload via multipart, text extraction with pdfplumber, AI-parsed structured fields, Document persistence with file_path and extracted_text, pre-fill into session context

### Modified Capabilities
- `chat-api-stub`: system prompt injected with `session.campos_diligenciados` as pre-filled context; frontend `ApiClient` adds `uploadDocument(file)` method
- `chat-sessions`: `campos_diligenciados` now supports pre-population from PDF parse (beyond keyword extraction from text)
- `mcp-domain-tools`: new tool `create_application(tipo, customer_id, form_data, monto, plazo, destino)` added

## Approach

1. **`POST /api/upload/document`**: recibe `file` (PDF) + `session_id`. Guarda en `data/uploads/` via `aiofiles`. Crea `Document(customer_id?, tipo_documento="formulario_credito", file_path=..., ocr_processed=False)`.
2. **`PDFService.extract_text()`**: pdfplumber abre el PDF, extrae texto de todas las páginas, limpia saltos de línea excesivos.
3. **`PDFService.parse_with_ai()`**: llama a Qwen2-7B con prompt estructurado + el texto extraído. Prompt pide JSON con mapeo a Customer/Credit/Application.form_data.
4. **Guarda resultado**: `Document.extracted_text = texto_crudo`, `Document.ocr_processed = True`, `session.campos_diligenciados = campos_parseados`.
5. **ChatService**: en el system prompt del AI, inyecta `"El usuario ya ha proporcionado estos datos vía PDF: {campos_diligenciados}. Pedí confirmación antes de crear."`.
6. **`create_application()` tool**: cuando usuario confirma, crea Application + Credit + asocia Document.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/routers/upload.py` | New | POST /upload/document handler |
| `backend/app/services/pdf_service.py` | New | PDFService with extract + parse |
| `backend/app/tools/domain_tools.py` | Modified | Add create_application() tool |
| `backend/app/services/chat.py` | Modified | Inject campos_diligenciados into system prompt |
| `backend/app/main.py` | Modified | Register upload router |
| `backend/requirements.txt` | Modified | Add pdfplumber |
| `frontend/src/components/chat/ChatPanel.tsx` | Modified | File upload button + preview |
| `frontend/src/lib/api.ts` | Modified | Add uploadDocument() method |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Texto entremezclado de tablas multi-columna del PDF | High | Evaluar extracción real; si falla, ajustar parseo con pre-procesamiento |
| Qwen2-7B no parsea todos los campos correctamente | Med | Prompt estructurado con few-shot; validación manual post-parseo |
| Campos sin columna ORM dedicada (>10) | Low | Van a `Application.form_data` (JSON) — diseño ya previsto |

## Rollback Plan

1. Revertir `backend/app/main.py` — quitar `app.include_router(upload.router)`
2. Revertir `backend/app/services/chat.py` — quitar inyección de campos_diligenciados
3. Revertir `backend/app/tools/domain_tools.py` — quitar `create_application()`
4. Eliminar archivos nuevos: `upload.py`, `pdf_service.py`
5. Revertir `frontend/` cambios (ChatPanel, api.ts)
6. Revertir `requirements.txt` (quitar pdfplumber)
7. Los `Document` creados y PDFs en `data/uploads/` son datos huérfanos — se pueden limpiar con script ad-hoc

## Dependencies

- `pdfplumber>=0.11.4` (nueva dependencia Python)
- `python-multipart` ya instalado; `aiofiles` ya instalado

## Success Criteria

- [ ] `POST /api/upload/document` acepta PDF, extrae texto, parsea campos, devuelve 200 con campos parseados
- [ ] Los campos parseados aparecen en `session.campos_diligenciados` y el AI los usa como pre-llenado en el chat
- [ ] `create_application()` tool crea Application + Credit + vincula Document correctamente
- [ ] Frontend permite subir PDF desde el chat y recibe respuesta con datos parseados
