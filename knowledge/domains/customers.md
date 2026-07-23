---
type: domain
updated_at: 2026-07-16
---

# Customer Domain

## Description
Gestión del perfil, búsqueda y creación de afiliados de Colsubsidio. Corazón del sistema
ya que toda interacción comienza identificando al afiliado.

## Tools (FastMCP)
- `get_customer()` — Obtener perfil por documento
- `search_customer()` — Búsqueda por criterios
- `create_customer()` — Crear nuevo afiliado
- `update_customer()` — Actualizar datos
- `get_products()` — Productos del afiliado
- `get_history()` — Historial de interacciones

## Memory Model
Cada sesión mantiene:
- cliente (ID, datos básicos)
- producto actual
- estado del flujo
- campos diligenciados
- campos faltantes
- última intención
- documentos adjuntos
- historial completo

## Business Rules
- No preguntar datos ya conocidos (nombre, documento, empresa)
- Recuperar automáticamente perfil al iniciar conversación desde WhatsApp
- Score de afiliado para elegibilidad
