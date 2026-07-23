---
type: feature
id: WI-002
title: "Núcleo conversacional — Router, Conversation Hub, Chat UI y agentes de crédito y seguros"
knowledge_level: K2
status: draft
phase: now
work_type: feature
initiative: "Hackathon MVP"
domains:
  - shared
  - credits
  - insurance
code: []
created_at: 2026-07-16
source:
  type: manual
  inferred: false
generated_by: kaddo-create
template_version: 1
summary: "Implementar el router de intenciones, el conversation hub, la chat UI con streaming y los agentes de crédito y seguros"
---

# WI-002: Núcleo conversacional

> Type: feature · Level: K2 · Phase: Fase 2

## Problem

Tenemos la infraestructura base pero no hay lógica conversacional. El usuario no puede hablar con el sistema. Necesitamos el router que clasifica intenciones, el hub que mantiene contexto, la interfaz de chat y los agentes especializados que ejecutan los flujos de crédito y seguros.

## Expected Result

- Router de intenciones conectado a OpenAI Responses API que clasifica en: creditos, seguros, reclamos, beneficios, seguimiento, saludo
- Conversation Hub que mantiene por sesión: cliente, producto, estado, campos, documentos
- Chat UI en React con streaming SSE, burbujas de mensajes, accesos rápidos, indicador de escritura
- Credit Agent con máquina de estados completa (DISCOVERY → PROFILE → RECOMMENDATION → SIMULATION → DATA_COLLECTION → DOCUMENTS → VALIDATION → SUBMISSION → COMPLETED)
- Insurance Agent con máquina de estados (DISCOVERY → RISK → RECOMMENDATION → QUOTE → DATA_COLLECTION → PAYMENT → POLICY_CREATED)
- Form Engine básico que estructura preguntas/respuestas en JSON

## Impact

Corazón del producto. Sin esto no hay plataforma conversacional.

## Acceptance criteria

- [ ] Router clasifica "Necesito un crédito" → creditos
- [ ] Router clasifica "Quiero asegurar mi carro" → seguros
- [ ] Router NUNCA responde directamente, solo enruta
- [ ] Chat UI muestra mensajes con streaming SSE
- [ ] Credit Agent guía al usuario por los 9 estados
- [ ] Insurance Agent guía al usuario por los 7 estados
- [ ] Conversation Hub persiste estado entre mensajes
- [ ] Form Engine estructura campos en JSON y detecta completitud

## Design

### Router
```
POST /api/chat
  Body: { message: string, session_id: string }
  Response: SSE stream con respuestas del agente

Router flow:
1. Recibir mensaje
2. Recuperar o crear sesión
3. Clasificar intención vía OpenAI
4. Enrutar al agente correspondiente
5. Agente ejecuta tools según estado
6. Streamear respuesta al frontend
```

### Chat UI components
- `ChatContainer`: layout principal
- `MessageList`: burbujas de mensajes (usuario + agente)
- `MessageInput`: campo de texto + adjuntar
- `QuickActions`: botones de acceso rápido
- `TypingIndicator`: animación de escritura
- `ProductCard`: tarjeta para simulaciones/cotizaciones

## Out of scope

- OCR y procesamiento de documentos
- Opportunity Engine y flujo proactivo
- Notificaciones reales (WhatsApp/Email)
- Formularios oficiales completos

## Validation

- Enviar "Necesito un crédito" → flujo completo de simulación
- Enviar "Quiero asegurar mi carro" → flujo completo de cotización
- Verificar que el contexto se mantiene entre mensajes
- Verificar streaming en frontend

## Definition of Done

- [ ] Router de intenciones funcional
- [ ] Conversation Hub con persistencia SQLite
- [ ] Chat UI con streaming SSE
- [ ] Credit Agent funcional
- [ ] Insurance Agent funcional
- [ ] Form Engine básico implementado

## Learning

_What did we learn from this change? Update after completion._
