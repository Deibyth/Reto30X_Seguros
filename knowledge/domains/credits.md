---
type: domain
updated_at: 2026-07-16
---

# Credit Domain

## Real Products (Colsubsidio)

| Producto | Descripción | Monto Máximo | Modalidad |
|----------|-------------|-------------|-----------|
| Libre Inversión | Viajes, vivienda, gastos médicos | $150,000,000 COP | Solicitud digital |
| Vivienda Hipotecario | Compra de vivienda nueva o usada | Según capacidad | UVR o Pesos |
| Complementario Hipotecario | Acabados, remodelación, trámites | Según capacidad | Flexible |
| Compra de Cartera | Unificación de deudas | Según deuda actual | Menor tasa |
| Crédito Mujeres | Proyectos personales, protección oncológica | Montos adaptables | Incluye protección oncológica |

## Tools (FastMCP)
- `recommend_credit()` — Recomendar producto crediticio según perfil
- `calculate_capacity()` — Calcular capacidad de endeudamiento
- `simulate_credit()` — Generar simulación personalizada
- `create_application()` — Crear solicitud
- `update_application()` — Actualizar solicitud
- `submit_application()` — Radicar solicitud
- `get_application_status()` — Consultar estado

## State Machine

```
DISCOVERY
    ↓
PROFILE
    ↓
RECOMMENDATION
    ↓
SIMULATION
    ↓
DATA_COLLECTION
    ↓
DOCUMENTS
    ↓
VALIDATION
    ↓
SUBMISSION
    ↓
COMPLETED
```

## Form Engine Fields por Producto

### Libre Inversión
- nombre (string, required, source: customer)
- documento (string, required, source: customer)
- empresa (string, required, source: customer)
- salario (number, required, source: customer)
- tipo_contrato (string, required, source: customer)
- antigüedad_laboral (number, required, source: customer)
- monto_solicitado (number, required, source: user)
- plazo_meses (number, required, source: user)
- destino (string, required, source: user)
- correo (string, required, source: customer)

### Vivienda Hipotecario
- nombre (string, required, source: customer)
- documento (string, required, source: customer)
- salario (number, required, source: customer)
- tipo_contrato (string, required, source: customer)
- antigüedad_laboral (number, required, source: customer)
- valor_inmueble (number, required, source: user)
- cuota_inicial (number, required, source: user)
- plazo_meses (number, required, source: user)
- modalidad (string, required, source: user) [UVR/Pesos]

### Crédito Mujeres (campos adicionales)
- Todos los de Libre Inversión
- Protección oncológica incluida (automático)

## Business Rules
- El agente nunca pregunta datos ya conocidos del perfil
- Libre Inversión: solicitud completamente digital
- Vivienda: requiere Vivienda NET portal para gestión
- Submit solo cuando todos los campos required están completos
- Crédito Mujeres: solo disponible para afiliadas mujeres
- Compra de Cartera: requiere validación de deuda actual
