---
type: feature
id: WI-004
title: "Form Engine — Eliminación del PDF, conversión de formularios oficiales a JSON estructurado"
knowledge_level: K2
status: draft
phase: next
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
summary: "Implementar el Form Engine que transforma formularios oficiales en JSON y completa campos automáticamente durante la conversación"
---

# WI-004: Form Engine — Eliminación del PDF

> Type: feature · Level: K2 · Phase: Fase 4

## Problem

Actualmente los afiliados deben descargar PDFs, imprimirlos, diligenciarlos, escanearlos y subirlos. Este es el punto de mayor fricción. Debemos eliminar el PDF haciendo que el agente complete internamente un formulario estructurado durante la conversación.

## Expected Result

- Analizar formularios oficiales de crédito de vivienda y seguro de vida/vehículo
- Convertir cada formulario a un contrato JSON con campos, tipos y reglas
- Form Engine runtime que recibe respuestas del agente y completa el JSON
- Detección de completitud: cuando todos los campos required están OK → submit_application()
- Capacidad de generar el PDF final a partir del JSON (opcional, para respaldo)

## Impact

Este es el **mayor diferencial del proyecto**. Transforma la experiencia de formularios en una conversación natural.

## Acceptance criteria

- [ ] Formulario de crédito de vivienda convertido a JSON
- [ ] Formulario de seguro de vida convertido a JSON
- [ ] Formulario de seguro de vehículo convertido a JSON
- [ ] Form Engine completa campos automáticamente durante la conversación
- [ ] Cuando todos los campos required están completos, permite submit
- [ ] El usuario nunca ve el formulario interno

## Design

### Form Definition (ejemplo crédito vivienda)
```json
{
  "producto": "credito_vivienda",
  "version": "1.0",
  "fields": [
    { "name": "nombre", "required": true, "type": "string", "source": "customer" },
    { "name": "documento", "required": true, "type": "string", "source": "customer" },
    { "name": "empresa", "required": true, "type": "string", "source": "customer" },
    { "name": "salario", "required": true, "type": "number", "source": "customer" },
    { "name": "tipo_contrato", "required": true, "type": "string", "source": "customer" },
    { "name": "antiguedad_laboral", "required": true, "type": "number", "source": "customer" },
    { "name": "valor_inmueble", "required": true, "type": "number", "source": "user" },
    { "name": "cuota_inicial", "required": true, "type": "number", "source": "user" },
    { "name": "plazo_meses", "required": true, "type": "number", "source": "user" }
  ]
}
```

### Engine Runtime
```python
class FormEngine:
    def __init__(self, form_definition: dict):
        self.fields = {f["name"]: f for f in form_definition["fields"]}
        self.values = {}
    
    def set_field(self, name: str, value: Any):
        if name in self.fields:
            self.values[name] = value
    
    def is_complete(self) -> bool:
        required = [f for f in self.fields.values() if f.get("required")]
        return all(f["name"] in self.values for f in required)
    
    def get_missing_fields(self) -> list:
        required = [f for f in self.fields.values() if f.get("required")]
        return [f for f in required if f["name"] not in self.values]
    
    def submit(self) -> dict:
        if not self.is_complete():
            raise ValueError("Form incomplete")
        # Llamar submit_application() con los datos
        return self.values
```

### Field Sources
- `customer`: se obtiene automáticamente del perfil del afiliado
- `user`: debe preguntarse al usuario durante la conversación

## Out of scope

- Oportunidades proactivas (Fase 5)
- Generación de PDF físico desde JSON
- Firma electrónica

## Validation

- Iniciar solicitud de crédito, completar todos los campos, verificar submit
- Iniciar cotización de seguro, completar campos, verificar policy_created
- Verificar que campos de source "customer" se auto-completan
- Verificar que el engine reporta campos faltantes correctamente

## Definition of Done

- [ ] Formularios oficiales analizados y convertidos a JSON
- [ ] Form Engine runtime implementado
- [ ] Auto-completado de campos desde perfil
- [ ] Preguntas solo por campos faltantes
- [ ] Submit automático al completar

## Learning

_What did we learn from this change? Update after completion._
