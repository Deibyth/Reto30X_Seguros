---
type: feature
id: WI-003
title: "Herramientas backend — Customer, Credit, Insurance, Document, Notification Tools vía FastMCP"
knowledge_level: K2
status: draft
phase: next
work_type: feature
initiative: "Hackathon MVP"
domains:
  - customers
  - credits
  - insurance
  - documents
  - notifications
code: []
created_at: 2026-07-16
source:
  type: manual
  inferred: false
generated_by: kaddo-create
template_version: 1
summary: "Implementar todas las tools de negocio como FastMCP tools y el pipeline OCR"
---

# WI-003: Herramientas backend

> Type: feature · Level: K2 · Phase: Fase 3

## Problem

Los agentes conversacionales no tienen acceso a datos reales. Necesitan tools para consultar clientes, simular créditos, cotizar seguros, procesar documentos y enviar notificaciones. Sin estas herramientas, el sistema solo puede simular respuestas.

## Expected Result

- Customer Tools: get_customer, search_customer, create_customer, update_customer, get_products, get_history
- Credit Tools: recommend_credit, calculate_capacity, simulate_credit, create_application, update_application, submit_application, get_application_status
- Insurance Tools: recommend_insurance, quote_insurance, create_policy, validate_coverage, create_claim, claim_status
- Document Tools: upload_document, extract_document (OCR), validate_document, save_document
- Notification Tools: send_email, send_whatsapp, send_push
- OCR pipeline con Pillow + pytesseract para extraer texto de documentos

## Impact

Transforma el sistema de "simulación conversacional" a "plataforma funcional con datos reales".

## Acceptance criteria

- [ ] Cada tool listada está implementada como FastMCP tool
- [ ] Tools se conectan a SQLAlchemy para datos reales
- [ ] OCR extrae texto de imágenes y PDFs
- [ ] Las tools retornan errores manejables por el LLM
- [ ] Notificaciones se registran en BD (simuladas para MVP)

## Design

### FastMCP Server
```python
# tools/mcp_server.py
from fastmcp import FastMCP

mcp = FastMCP("proteccion-inteligente")

@mcp.tool()
def get_customer(document: str) -> dict:
    """Obtener perfil del afiliado por documento"""
    ...

@mcp.tool()
def simulate_credit(customer_id: int, amount: float, term_months: int) -> dict:
    """Simular crédito para un afiliado"""
    ...
```

### OCR Pipeline
```python
# tools/ocr.py
from PIL import Image
import pytesseract

def extract_text(image_path: str) -> str:
    img = Image.open(image_path)
    return pytesseract.image_to_string(img, lang="spa")
```

## Out of scope

- Form Engine avanzado (Fase 4)
- Opportunity Engine (Fase 5)
- Integración real con APIs de Colsubsidio

## Validation

- Llamar a cada tool vía FastMCP y verificar respuesta
- Subir un documento de prueba y verificar extracción OCR
- Verificar que el agente puede llamar tools y recibir resultados

## Definition of Done

- [ ] Customer Tools implementadas
- [ ] Credit Tools implementadas
- [ ] Insurance Tools implementadas
- [ ] Document Tools implementadas
- [ ] Notification Tools implementadas
- [ ] OCR pipeline funcional

## Learning

_What did we learn from this change? Update after completion._
