---
type: domain
updated_at: 2026-07-16
---

# Opportunities Domain

## Description
Motor de oportunidades proactivas. Analiza la base de afiliados usando reglas de negocio
para identificar productos relevantes y disparar campañas personalizadas.

## Tools (FastMCP)
- `find_opportunities()` — Analizar afiliados y generar oportunidades
- `create_campaign()` — Crear campaña de oportunidad
- `send_offer()` — Enviar oferta personalizada
- `schedule_followup()` — Programar seguimiento

## Architecture

```
Scheduler (diario)
    ↓
Opportunity Engine (reglas, NO IA)
    ↓
Analiza clientes contra reglas
    ↓
Genera oportunidades
    ↓
Notification Service
    ↓
WhatsApp al afiliado
    ↓
Afiliado responde → FastAPI → Agent
```

## Recommendation Rules (Reglas de Elegibilidad)

```
IF antigüedad > 5 años AND salario > 4M AND 2 hijos
THEN Crédito Vivienda

IF vehículo AND no tiene seguro
THEN Seguro Vehículo

IF trabajo estable AND salario > 3M
THEN Protección Ingresos

IF score > 80 AND sin crédito hipotecario
THEN Crédito Libre Inversión
```

## Proactive Flow (WhatsApp)

```
"Hola Andrés 👋

Según tu perfil de afiliado encontramos que actualmente podrías
acceder a un Crédito de Vivienda con condiciones preferenciales.

¿Quieres conocer una simulación?"

[ Sí ] [ Más información ]
```

El agente ya conoce el perfil. No vuelve a preguntar nombre, documento ni empresa.

## Opportunity Engine Details
- NO usa IA generativa
- Corre diariamente vía scheduler
- Genera oportunidades basadas en reglas
- Cada oportunidad → evaluación → campaign trigger
- Integración con Notification Service para WhatsApp
- Seguimiento automático de respuestas
