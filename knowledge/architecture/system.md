---
type: architecture
updated_at: 2026-07-16
---

# System Architecture

## High-Level Layered Architecture

```
                        React
                           |
                     Chat UI (SSE Streaming)
                           |
────────────────────────────────────────────────────
                    FastAPI
              API Gateway + Streaming
────────────────────────────────────────────────────
            Conversation Hub
        Contexto + Memoria + Router
────────────────────────────────────────────────────
     ┌──────────┬──────────┬──────────┬──────────┐
     │ Créditos │ Seguros  │ Reclamos │Beneficios│
     └──────────┴──────────┴──────────┴──────────┘
────────────────────────────────────────────────────
                   FastMCP
              Catálogo de Tools
────────────────────────────────────────────────────
  Customer  Credit  Insurance   OCR  Notification
  Opportunity  Application  Document
────────────────────────────────────────────────────
     SQLite    Uploads    OCR    Business Rules
```

## Component Details

### Chat UI (React)
- Única interfaz conversacional
- Soporte para tarjetas de productos, simulaciones, carga de docs
- Streaming SSE para respuestas en tiempo real
- Accesos rápidos: "Solicitar crédito", "Proteger mis ingresos", etc.

### API Gateway (FastAPI)
- Endpoints REST + SSE streaming
- Manejo de archivos multipart
- WebSockets (opcional, si el tiempo lo permite)

### Conversation Hub
- Router de intenciones (nunca responde, solo clasifica)
- Mantenimiento de contexto conversacional
- Memoria por sesión: cliente, producto, estado, campos, documentos

### Specialized Agents
Cada agente tiene su máquina de estados y acceso a tools específicas:
- **Credit Agent**: DISCOVERY → PROFILE → RECOMMENDATION → SIMULATION → DATA_COLLECTION → DOCUMENTS → VALIDATION → SUBMISSION → COMPLETED
- **Insurance Agent**: DISCOVERY → RISK → RECOMMENDATION → QUOTE → DATA_COLLECTION → PAYMENT → POLICY_CREATED
- **Claim Agent**: CLAIM → VALIDATE_POLICY → REQUEST_DOCUMENTS → OCR → BUSINESS_RULES → CREATE_CLAIM → TRACKING

### FastMCP Server
Catálogo de tools expuestas como MCP:
- Customer Tools
- Credit Tools
- Insurance Tools
- Document Tools
- Notification Tools
- Opportunity Tools

### Form Engine
Transforma PDFs oficiales en definiciones JSON estructuradas:
```json
{
  "producto": "credito_vivienda",
  "fields": [
    { "name": "nombre", "required": true, "type": "string" },
    { "name": "empresa", "required": true },
    { "name": "salario", "required": true }
  ]
}
```
El agente completa el JSON durante la conversación. Cuando todos los campos obligatorios están completos, ejecuta submit_application().

### Opportunity Engine
- NO usa IA generativa
- Usa reglas de elegibilidad
- Analiza toda la base de afiliados
- Genera oportunidades → Notification Service → WhatsApp → Cliente responde → Agente

### Base de Datos (MVP)
Entidades: Cliente, Producto, Crédito, Seguro, Póliza, Reclamo, Solicitud, Documento, Conversación, Sesión, Oportunidad, Notificación

## Data Flow: Solicitud de Crédito

```
Usuario: "Necesito un crédito"

→ Router clasifica intención "creditos"
→ Conversation Hub crea sesión
→ Credit Agent inicia estado DISCOVERY
→ Agent pregunta perfil mediante tools
→ Form Engine se completa con cada respuesta
→ Cuando todos los campos OK → submit_application()
→ Usuario recibe número de caso
```

## Data Flow: Oportunidad Proactiva

```
Scheduler (diario)
→ Opportunity Engine analiza clientes
→ Genera oportunidades
→ Notification Service envía WhatsApp
→ Cliente responde "Sí"
→ FastAPI recibe respuesta
→ Agent recupera perfil
→ Continúa flujo normal
```

## Visual Design Principles

- Una sola experiencia conversacional
- Predominio del blanco y superficies limpias
- Color institucional Colsubsidio como primario
- Grises neutros para jerarquía visual
- Bordes suaves (12–16px) y sombras ligeras
- Iconografía simple y consistente
- Tipografía moderna y altamente legible
