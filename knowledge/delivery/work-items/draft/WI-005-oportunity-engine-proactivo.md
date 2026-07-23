---
type: feature
id: WI-005
title: "Opportunity Engine — Motor de reglas proactivo con scheduler, elegibilidad y campañas WhatsApp"
knowledge_level: K2
status: draft
phase: later
work_type: feature
initiative: "Hackathon MVP"
domains:
  - opportunities
  - notifications
  - customers
code: []
created_at: 2026-07-16
source:
  type: manual
  inferred: false
generated_by: kaddo-create
template_version: 1
summary: "Implementar el motor de oportunidades proactivas basado en reglas que analiza afiliados y genera campañas personalizadas"
---

# WI-005: Opportunity Engine — IA Proactiva

> Type: feature · Level: K2 · Phase: Fase 5

## Problem

La plataforma solo responde a solicitudes. Para maximizar el valor, debe identificar proactivamente oportunidades de negocio en la base de afiliados y contactarlos con ofertas personalizadas. Esto no debe usar IA generativa — debe ser un motor de reglas determinístico.

## Expected Result

- Opportunity Engine que analiza la base de afiliados usando reglas de elegibilidad
- Scheduler diario que ejecuta el análisis
- Generación de oportunidades con producto, motivo y prioridad
- Integración con Notification Service para enviar ofertas por WhatsApp
- Flujo completo: WhatsApp → afiliado responde → agente recupera perfil → continúa
- Seguimiento automático de respuestas

## Impact

Transforma la plataforma de reactiva a proactiva. Diferencial clave frente a chatbots tradicionales.

## Acceptance criteria

- [ ] Reglas de elegibilidad implementadas (Crédito Vivienda, Seguro Vehículo, Protección Ingresos)
- [ ] Scheduler diario ejecuta análisis sobre la BD
- [ ] Oportunidades se generan y almacenan
- [ ] Simulación de envío WhatsApp con oferta personalizada
- [ ] Afiliado responde "Sí" → agente recupera contexto y continúa flujo
- [ ] Agente NO pregunta datos que ya conoce del perfil

## Design

### Rule Engine
```python
RULES = [
    {
        "name": "credito_vivienda",
        "condition": lambda c: (
            c.antiguedad > 5 and
            c.salario > 4_000_000 and
            c.hijos >= 2 and
            not c.tiene_credito_vivienda
        ),
        "product": "Credito Vivienda",
        "priority": "high"
    },
    {
        "name": "seguro_vehiculo",
        "condition": lambda c: (
            c.tiene_vehiculo and
            not c.tiene_seguro_vehiculo
        ),
        "product": "Seguro Vehiculo",
        "priority": "medium"
    },
    {
        "name": "proteccion_ingresos",
        "condition": lambda c: (
            c.tipo_contrato == "indefinido" and
            c.salario > 3_000_000 and
            not c.tiene_proteccion_ingresos
        ),
        "product": "Proteccion Ingresos",
        "priority": "medium"
    }
]
```

### Proactive Flow
```
Scheduler (cron: 0 8 * * *)
    ↓
OpportunityEngine.analyze_all(customers)
    ↓
For each customer:
    Evaluate all rules
    If match → create Opportunity
    ↓
Opportunity stored in DB (status: pending)
    ↓
NotificationService.send_whatsapp(customer, opportunity)
    ↓
Customer replies "Sí"
    ↓
FastAPI endpoint /api/whatsapp-webhook
    ↓
Recover session + profile
    ↓
Route to corresponding Agent
    ↓
Agent: "Perfecto. Ya conozco tu información. Solo necesito dos datos..."
```

### WhatsApp Message Template
```
Hola {nombre} 👋

Según tu perfil de afiliado encontramos que actualmente podrías
acceder a un {producto} con condiciones preferenciales.

¿Quieres conocer una simulación?

[ Sí ] [ Más información ]
```

## Out of scope

- Integración real con API de WhatsApp Business
- Campañas segmentadas avanzadas
- Dashboard de oportunidades
- OCR y documentos (Fase 3-4)

## Validation

- Ejecutar Opportunity Engine contra datos de prueba
- Verificar generación correcta de oportunidades según reglas
- Simular flujo completo: oportunidad → WhatsApp → respuesta → agente
- Verificar que el agente no pregunta datos conocidos

## Definition of Done

- [ ] Reglas de elegibilidad implementadas
- [ ] Scheduler diario funcional
- [ ] Oportunidades generadas y almacenadas
- [ ] Simulación de envío WhatsApp
- [ ] Flujo de respuesta del afiliado completo
- [ ] Agente recupera perfil sin preguntar datos conocidos

## Learning

_What did we learn from this change? Update after completion._
