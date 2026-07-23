# Archive Report: Fase 2 — Chat IA + MCP Domain Tools

**Status**: COMPLETED
**Date**: 2026-07-16
**Change**: `fase2-chat-ia-mcp`

## Executive Summary

Fase 2 completada. Chat con IA real usando SiliconFlow (Qwen2-7B-Instruct), 5 MCP tools del dominio con acceso a ORM, sistema de sesiones con persistencia de historial, y frontend de chat completo con TanStack Query + framer-motion.

## Capabilities Delivered

| ID | Capability | Status | New/Modified Files |
|---|---|---|---|
| C03 | Chat API (updated) | ✅ | `routers/chat.py` |
| C04 | FastMCP Server (updated) | ✅ | `tools/mcp_server.py` |
| C06 | Chat Sessions | ✅ | `services/chat.py` |
| C07 | MCP Domain Tools | ✅ | `tools/domain_tools.py` |
| C08 | AI Tool Loop | ✅ | `services/tool_bridge.py` |
| C09 | Chat UI | ✅ | `ChatPanel.tsx`, `api.ts` |

## Archivos Creados/Modificados

### Nuevos (5)
- `backend/app/services/__init__.py`
- `backend/app/services/chat.py` — ChatService (sesiones, historial, loop de tools)
- `backend/app/services/tool_bridge.py` — FastMCP → OpenAI tool bridge
- `backend/app/tools/domain_tools.py` — 5 herramientas ORM del dominio

### Modificados (4)
- `backend/app/tools/mcp_server.py` — domain_tools importado
- `backend/app/routers/chat.py` — usa ChatService real
- `backend/app/main.py` — inicializa ToolBridge + ChatService en lifespan
- `frontend/src/components/chat/ChatPanel.tsx` — UI completa de chat
- `frontend/src/lib/api.ts` — tipos actualizados con model field

## Flujo de Conversación

```
POST /chat
  → ChatService.get_or_create_session(session_id)
  → ChatService.load_history() (últimos 20 mensajes)
  → Phase 1: AI call con tools (30s timeout)
    → Si tool_calls → ejecuta via ToolBridge → Phase 2 con resultados
    → Si no tool_calls → reply directo
  → Persiste user_msg + ai_reply en conversations
  → Actualiza session state (estado_actual, ultima_intencion, campos_diligenciados)
  → Devuelve ChatResponse(session_id, reply, model, timestamp)
```

## MCP Domain Tools

| Tool | Descripción | ORM |
|---|---|---|
| `get_products(tipo)` | Lista productos (crédito/seguro) | Product + Insurance |
| `get_customer(documento)` | Busca cliente por documento | Customer |
| `check_eligibility(customer_id)` | Evalúa elegibilidad crediticia | Customer |
| `simulate_credit(monto, plazo)` | Simula crédito (18% Tasa Anual) | Pure math |
| `get_insurance(insurance_id)` | Detalle de seguro | Insurance |

## State Machine (Session)

```
inicio → recopilando_datos → evaluando → ofreciendo_producto → completado
```

Intención detectada por keywords (NLP diferido a Fase 3).

## Verification

| Check | Result |
|---|---|
| Python syntax (all .py) | ✅ |
| Frontend Vite build | ✅ 1984 modules, 273KB JS, 12KB CSS |
| Spec compliance | ✅ 24/27 requirements, 33/40 scenarios |
| Blockers | 0 |
| Warnings | 3 (state machine sin NLP real — aceptado para MVP) |

## Deferred

- NLP intent classification real (en lugar de keywords)
- Tool calling loop multi-turn (soporte para que la IA llame múltiples tools secuencialmente)
- Sistema de notificaciones en tiempo real (WebSocket)
- File upload para documentos
- Tests automatizados (pytest + Vitest)

## Next Steps

1. Población de datos reales de Colsubsidio en la DB
2. Fase 3: Sistema de notificaciones y alertas
3. Fase 4: Admin dashboard para Colsubsidio
