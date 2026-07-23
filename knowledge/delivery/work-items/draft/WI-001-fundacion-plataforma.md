---
type: feature
id: WI-001
title: "Fundación de la plataforma — Repositorio, backend, frontend e infraestructura base"
knowledge_level: K2
status: draft
phase: now
work_type: feature
initiative: "Hackathon MVP"
domains:
  - shared
code: []
created_at: 2026-07-16
source:
  type: manual
  inferred: false
generated_by: kaddo-create
template_version: 1
summary: "Crear la estructura base del proyecto con FastAPI, React, SQLite, FastMCP y Docker"
---

# WI-001: Fundación de la plataforma

> Type: feature · Level: K2 · Phase: Fase 1

## Problem

No existe ningún código base. Necesitamos establecer el repositorio, la estructura de directorios, las configuraciones de backend y frontend, el modelo de datos inicial, el servidor FastMCP y la infraestructura Docker para poder empezar a desarrollar sobre una base sólida.

## Expected Result

Un monorepo funcional con:
- FastAPI corriendo con health check y configuración base
- React + Vite + TypeScript + TailwindCSS + shadcn/ui con layout mínimo
- SQLite + SQLAlchemy con modelo de datos inicial (Cliente, Producto, Solicitud, Documento, Conversación, Sesión, Oportunidad, Notificación)
- FastMCP server con tool hello world
- Docker + docker-compose para dev
- Scripts de inicio y configuración

## Impact

Desbloquea todas las fases siguientes. Sin esta base no se puede desarrollar nada más.

## Acceptance criteria

- [ ] `make dev` o `docker-compose up` levanta backend y frontend
- [ ] FastAPI responde en `/health` con 200 OK
- [ ] React app se ve en el navegador con el header "Protección Inteligente 360°"
- [ ] Modelo de datos con migraciones SQLAlchemy funcionales
- [ ] FastMCP server responde a una tool de prueba
- [ ] Estructura de directorios clara: `backend/`, `frontend/`, `tools/`

## Design

### Backend structure
```
backend/
  app/
    __init__.py
    main.py
    config.py
    database.py
    models/
      __init__.py
      customer.py
      product.py
      credit.py
      insurance.py
      policy.py
      claim.py
      application.py
      document.py
      conversation.py
      session.py
      opportunity.py
      notification.py
    routers/
      __init__.py
      health.py
      chat.py
    tools/
      __init__.py
      mcp_server.py
  requirements.txt
  Dockerfile
```

### Frontend structure
```
frontend/
  src/
    App.tsx
    main.tsx
    components/
      chat/
      layout/
    lib/
      api.ts
  package.json
  vite.config.ts
  tailwind.config.ts
  Dockerfile
```

### Docker
```
docker-compose.yml
  - backend: puerto 8000
  - frontend: puerto 5173
```

## Out of scope

- Lógica de negocio de créditos/seguros
- Router de intenciones
- OCR
- Form Engine
- Opportunity Engine

## Validation

- `docker-compose up --build` funciona sin errores
- `curl localhost:8000/health` retorna OK
- Frontend accesible en `localhost:5173`

## Definition of Done

- [ ] Backend FastAPI con health check y configuración
- [ ] Frontend React con layout mínimo
- [ ] Base de datos SQLite con SQLAlchemy + modelos iniciales
- [ ] FastMCP server base funcional
- [ ] Docker + docker-compose funcional
- [ ] README con instrucciones de inicio

## Learning

_What did we learn from this change? Update after completion._
