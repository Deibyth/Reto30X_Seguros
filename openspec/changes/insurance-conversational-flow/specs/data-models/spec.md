# Delta for Data Models

> **Change:** `insurance-conversational-flow`
> **Date:** 2026-07-22

## ADDED Requirements

### Requirement: Session — `insurance_profile` JSON field

The `Session` model SHALL gain a column `insurance_profile` of type `JSON`, nullable, defaulting to `null`.

| Column | Type | Constraints |
|--------|------|-------------|
| insurance_profile | JSON | `nullable=True`, `default=None` |

This field SHALL store demographic attributes extracted conversationally during the `perfilando` state. Structure SHALL be a flat JSON object with optional keys:

| Key | Type | Example |
|-----|------|---------|
| `edad` | int | `35` |
| `estado_civil` | string | `"casado"`, `"soltero"` |
| `familia_con_hijos` | boolean | `true` |
| `tiene_mascota` | boolean | `false` |
| `tiene_vehiculo` | string | `"auto"`, `"moto"`, `null` |
| `es_propietario_vivienda` | boolean | `true` |
| `viaja_frecuentemente` | boolean | `false` |
| `tiene_deuda_activa` | boolean | `true` |
| `preocupacion` | string | `"proteger"`, `"ahorro"`, `"salud"` |

#### Scenario: Insurance profile stored
- GIVEN a Session row
- WHEN `insurance_profile` is set to `{"edad": 35, "familia_con_hijos": true}`
- THEN the JSON is stored and retrievable
- AND existing sessions have `insurance_profile = null`

### Requirement: Insurance model — `insurance_category` column

The `Insurance` model SHALL gain a column `insurance_category` of type `String(50)`, nullable, defaulting to `null`.

| Column | Type | Constraints |
|--------|------|-------------|
| insurance_category | String(50) | `nullable=True`, `default=None` |

Valid values SHALL be: `"personal"`, `"hogar"`, `"movilidad"`, `"mascotas"`, `"credito"`.

#### Scenario: Category stored for insurance product
- GIVEN an Insurance row
- WHEN `insurance_category` is set to `"hogar"`
- THEN the value is stored and retrievable
- AND the model query can filter by category

## MODIFIED Requirements

### Requirement: Session model — updated field list (F-DATA-01 subsumes)

The Session model specification SHALL include the new `insurance_profile` field. Existing fields (`id`, `customer_id`, `estado_actual`, `campos_diligenciados`, `ultima_intencion`, `activa`, timestamps) SHALL remain unchanged.
(Previously: Session had 7 columns; now 8)

### Requirement: Insurance model — updated field list

The Insurance model specification SHALL include the new `insurance_category` field. Existing fields (`id`, `nombre`, `cobertura`, `publico_objetivo`, `prima_base`, `activo`, timestamps) SHALL remain unchanged.
(Previously: Insurance had 7 columns; now 8)
