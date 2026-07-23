---
type: feature
id: WI-006
title: "Demo final — Flujo completo integrado, pruebas y despliegue"
knowledge_level: K2
status: draft
phase: later
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
summary: "Integrar todos los componentes, probar el flujo completo y preparar la demo final"
---

# WI-006: Demo final

> Type: feature · Level: K2 · Phase: Fase 6

## Problem

Todos los componentes existen pero están desconectados o sin pulir. Necesitamos integrar el flujo completo de principio a fin, probar que todo funciona, pulir la UI/UX y documentar la demo para la presentación de la hackathon.

## Expected Result

- Flujo completo demostrable:
  1. Usuario recibe WhatsApp con oferta personalizada
  2. Inicia conversación desde el mensaje
  3. Agente recupera perfil del afiliado automáticamente
  4. Genera simulación personalizada
  5. Solicita solo información faltante
  6. Completa internamente el formulario oficial (Form Engine)
  7. Permite adjuntar documentos (OCR)
  8. Radica la solicitud y muestra número de caso
  9. Usuario consulta estado desde el mismo chat
- UI pulida con identidad Colsubsidio
- Despliegue en Railway/Render
- Documentación de la demo y el proyecto

## Impact

Es la presentación final. Debe demostrar el valor completo de la plataforma en un solo flujo.

## Acceptance criteria

- [ ] Flujo completo de oportunidad proactiva a radicación funciona de principio a fin
- [ ] UI/UX con identidad Colsubsidio (colores, logo, tipografía)
- [ ] Despliegue funcional en Railway/Render
- [ ] README con instrucciones y demo script
- [ ] Documentación técnica del proyecto
- [ ] Sin errores críticos en el flujo principal

## Design

### Demo Script
```
1. Opportunity Engine detecta oportunidad para "Andrés"
2. Envía WhatsApp: "Hola Andrés, según tu perfil..."
3. Andrés responde "Sí"
4. Chat UI se abre con contexto cargado
5. Agente: "Perfecto, ya conozco tu información. Solo necesito confirmar dos datos"
6. Andrés proporciona valor_inmueble y cuota_inicial
7. Agente genera simulación con tabla de amortización
8. Andrés acepta
9. Agente solicita documento de identidad (OCR)
10. Andrés adjunta foto de la cédula
11. OCR extrae datos y valida
12. Form Engine completa automáticamente campos del perfil
13. Submit radica la solicitud
14. Agente muestra número de caso: CS-2026-0042
15. Andrés pregunta: "¿Cómo va mi solicitud?"
16. Agente consulta estado: "En estudio, documento en validación"
```

## Out of scope

- Integración real con WhatsApp Business API
- Producción con datos reales de Colsubsidio
- Autenticación y seguridad avanzada
- Pruebas de carga

## Validation

- Ejecutar script de demo completo sin errores
- Verificar cada paso del flujo
- Probar desde dispositivo móvil (responsive)
- Verificar despliegue accesible desde internet

## Definition of Done

- [ ] Flujo completo integrado y funcional
- [ ] UI/UX con identidad Colsubsidio
- [ ] Despliegue en Railway/Render
- [ ] Documentación de demo
- [ ] README del proyecto completo
- [ ] Sin bugs críticos

## Learning

_What did we learn from this change? Update after completion._
