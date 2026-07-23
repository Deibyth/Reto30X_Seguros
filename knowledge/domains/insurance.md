---
type: domain
updated_at: 2026-07-16
---

# Insurance Domain

## Real Products (Colsubsidio)

| Producto | Descripción | Cobertura | Público |
|----------|-------------|-----------|---------|
| Accidentes Personales | Cobertura completa accidentes individuales/familiares | Cobertura completa | Personas y familias |
| Exequial | Gastos funerarios completos | Gastos funerarios | Familias |
| Póliza de Salud | Atención médica preferencial flexible | Red de salud Colsubsidio | Personas y familias |
| Seguro de Vida | Respaldo económico para beneficiarios | Cobertura amplia fallecimiento | Personas y familias |
| Vida y Ahorro | Protección + acumulación de capital | Fallecimiento accidental + ahorro | Personas y familias |
| Accidente + Exequial | Combinado accidentes + funerarios | Cobertura completa combinada | Personas y familias |
| Asistencia Médica Viajes | Emergencias médicas en viajes | 24/7, internacional | Viajeros |
| Asistencias Médicas Familiares | Medicina especializada + domicilio | 24/7, Bogotá | Familias |
| Asistencias Múltiples | Salud, hogar, auto, mascotas | Multi-asistencia 24/7 | Familias |
| Seguro Mascotas | Veterinaria + protección daños | Perros y gatos | Dueños de mascotas |
| Vida Deudor | Cancelación de deuda por fallecimiento | Fallecimiento/incapacidad | Deudores |
| Asistencia Moto | Daños accidente, robo, lesiones terceros | Motocicletas | Dueños de motos |

## Recommendation Rules (Motor de Reglas)

```
IF vehículo AND no tiene seguro auto → Seguro Vehículo / Asistencia Moto
IF trabajo estable AND salario > 3M → Protección Ingresos / Vida
IF tiene hijos AND sin protección → Seguro Vida / Vida y Ahorro
IF viaja frecuentemente → Asistencia Médica Viajes
IF tiene mascota AND sin seguro → Seguro Mascotas
IF tiene deuda activa → Vida Deudor
```

## Tools (FastMCP)
- `recommend_insurance()` — Recomendar seguro según perfil y riesgos
- `quote_insurance()` — Cotizar prima
- `create_policy()` — Crear póliza
- `validate_coverage()` — Validar cobertura existente
- `create_claim()` — Iniciar reclamación
- `claim_status()` — Consultar estado de reclamación

## State Machine

```
DISCOVERY
    ↓
RISK
    ↓
RECOMMENDATION
    ↓
QUOTE
    ↓
DATA_COLLECTION
    ↓
PAYMENT
    ↓
POLICY_CREATED
```

## Key Forms por Producto
- Seguro Accidentes Personales: datos personales, cobertura deseada, beneficiarios
- Seguro Exequial: datos personales, plan funerario, beneficiarios
- Póliza de Salud: datos personales, cobertura médica, red preferida
- Seguro de Vida: datos personales, beneficiarios, monto asegurado
- Vida y Ahorro: datos personales, beneficiarios, monto ahorro/protección
- Asistencia Viajes: datos personales, destino, duración, cobertura
