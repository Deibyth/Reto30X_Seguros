---
type: current-state
updated_at: 2026-07-16
---

# Protección Inteligente 360° — Knowledge

> What is true about this product right now.

## Purpose

Plataforma inteligente de atención, protección y oportunidades para afiliados de Colsubsidio.
Reemplaza la navegación por formularios con una conversación única donde un agente inteligente
multidominio recomienda, asesora, gestiona solicitudes, procesa documentos y genera oportunidades
comerciales de forma proactiva.

**Lema:** La conversación reemplaza al formulario. La inteligencia reemplaza la navegación.

## Core Problem

Actualmente un afiliado debe navegar el portal, encontrar un producto, descargar un PDF,
diligenciarlo, escanearlo, volverlo a subir y esperar respuesta. Nuestra propuesta elimina
completamente esa fricción mediante un único asistente conversacional.

## Value Proposition

No es un chatbot. Es un **Agente Inteligente Multidominio** capaz de:
- Recomendar productos y servicios
- Asesorar y vender
- Gestionar solicitudes completas
- Recibir documentos y procesar OCR
- Realizar reclamaciones
- Generar oportunidades comerciales
- Hacer seguimiento proactivo

## Pilars

1. **Conversación única** — Un solo chat, sin módulos independientes ni formularios separados.
2. **Agentes especializados** — Router distribuye a agentes internos (créditos, seguros, reclamos, beneficios).
3. **Tools como backend** — El LLM nunca calcula ni consulta BD directamente; siempre usa herramientas (FastMCP).
4. **Formulario invisible** — Existe internamente como definición estructurada (Form Engine), el usuario nunca lo ve.
5. **Plataforma proactiva** — No solo responde, también inicia conversaciones (Opportunity Engine).

## Use Cases

### Reactivos (usuario inicia)
- Solicitar crédito
- Asegurar un vehículo
- Reportar pérdida de empleo
- Consultar estado de solicitud

### Proactivos (plataforma inicia)
- Oferta de crédito personalizada
- Recordatorio de renovación de póliza
- Notificación de cambio de estado en solicitud

## Architecture Overview

Frontend: React + Vite + TypeScript + TailwindCSS + shadcn/ui
Backend: FastAPI + Pydantic + SQLAlchemy + SQLite + FastMCP
IA: OpenAI Responses API + FastMCP
OCR: Pillow + pytesseract
Deploy: Docker + Railway / Render

### Key Components
- **Chat UI** — Interfaz conversacional única en React con streaming SSE
- **API Gateway** — FastAPI con streaming y WebSockets
- **Conversation Hub** — Contexto, memoria y router de intenciones
- **Specialized Agents** — Créditos, Seguros, Reclamos, Beneficios
- **FastMCP Server** — Catálogo de tools (customer, credit, insurance, document, notification, opportunity)
- **Form Engine** — Definición estructurada de formularios oficiales en JSON
- **Opportunity Engine** — Motor de reglas que analiza afiliados y genera campañas proactivas
- **State Machines** — Máquinas de estado por dominio (crédito, seguro, reclamo)

## Key Domains

- **customers** — Perfil, búsqueda, creación, historial del afiliado
- **credits** — Simulación, solicitud, radicación, estado de créditos
- **insurance** — Recomendación, cotización, pólizas, coberturas
- **claims** — OCR, validación, seguimiento de reclamaciones
- **documents** — Carga, extracción, validación de documentos
- **notifications** — Email, WhatsApp, push notifications
- **opportunities** — Motor de reglas, campañas, ofertas proactivas
- **shared** — Tipos comunes, utilidades compartidas

## Active Constraints

- MVP debe funcionar para la hackathon con equipo de 1 persona
- SQLite como base de datos (sin PostgreSQL en MVP)
- OCR local con Tesseract (sin servicios cloud)
- Formularios oficiales de Colsubsidio deben convertirse a JSON estructurado
- La experiencia debe ser 100% conversacional sin formularios visibles
- Opportunity Engine usa reglas, no IA generativa
- El router NUNCA responde, solo clasifica y enruta

## Tooling Conventions

- **Python environment**: `python -m venv` (stdlib, sin poetry/pipenv/conda)
- **Python server**: `uvicorn`
- **Frontend package manager**: `pnpm` (nunca npm ni yarn)
- **Python dependencies**: `pip` + `requirements.txt`
