---
type: domain
updated_at: 2026-07-16
---

# Claims Domain

## Description
Gestión de reclamaciones y siniestros con soporte OCR para documentos.

## Tools (FastMCP)
- `upload_document()` — Recibir documento del afiliado
- `extract_document()` — Extraer texto vía OCR
- `validate_document()` — Validar documento contra reglas de negocio
- `save_document()` — Almacenar documento

## State Machine

```
CLAIM
    ↓
VALIDATE_POLICY
    ↓
REQUEST_DOCUMENTS
    ↓
OCR
    ↓
BUSINESS_RULES
    ↓
CREATE_CLAIM
    ↓
TRACKING
```

## OCR Pipeline
1. Recibir documento (imagen o PDF) mediante `upload_document()`
2. Procesar con Pillow + pytesseract
3. Extraer campos relevantes
4. Validar contra reglas de negocio
5. Asociar a la reclamación

## Document Types
- Cédula de identidad
- Certificado laboral
- Factura
- Formulario de siniestro
- Soporte de pago
