# Insurance Recommendation Specification

> **Capability:** New — `insurance-recommendation`
> **Change:** `insurance-conversational-flow`
> **Date:** 2026-07-22

## Purpose

Define the rule-based insurance recommendation engine that maps a member's demographic profile (derived conversationally) to Colsubsidio insurance products. The engine is deterministic — no ML — and provides product matching `recommend_insurance()` and pricing `quote_insurance()` as MCP tools.

## Requirements

### Requirement: Recommendation rule engine

The system SHALL implement a pure function `_match_products(profile: dict) -> list[dict]` that applies deterministic rules against `session.insurance_profile`. Each rule SHALL map a profile attribute to one or more insurance products:

| Rule ID | Condition | Product |
|---------|-----------|---------|
| R1 | `profile.familia_con_hijos == true AND preocupacion == "proteger"` | Seguro de Vida |
| R2 | `profile.edad in ["18-25","26-35"] AND profile.estado_civil == "soltero"` | Accidentes Personales |
| R3 | `profile.viaja_frecuentemente == true` | Asistencia Médica Viajes |
| R4 | `profile.tiene_mascota == true` | Seguro Mascotas |
| R5 | `profile.tiene_deuda_activa == true` | Vida Deudor |
| R6 | `profile.es_propietario_vivienda == true` | Seguro Hogar |
| R7 | `profile.tiene_vehiculo == true` | Seguro Movilidad |

#### Scenario: Family with children matched to Vida
- GIVEN `insurance_profile` = `{"familia_con_hijos": true, "preocupacion": "proteger"}`
- WHEN `recommend_insurance(profile)` is called
- THEN the result includes "Seguro de Vida" as the top recommendation

#### Scenario: Multiple rules match
- GIVEN `insurance_profile` = `{"tiene_vehiculo": true, "tiene_mascota": true, "es_propietario_vivienda": true}`
- WHEN `recommend_insurance(profile)` is called
- THEN the result SHALL include Movilidad, Mascotas, AND Hogar

### Requirement: `recommend_insurance()` tool

The tool SHALL accept a `profile` JSON argument with known demographic attributes and return an ordered list of recommended products, each with: `product_id`, `nombre`, `descripcion`, `match_reason`, and `confidence` (low/medium/high based on rule specificity).

Signature: `recommend_insurance(profile: dict) -> list[dict]`

#### Scenario: Profile with one clear match
- GIVEN `profile` = `{"viaja_frecuentemente": true, "edad": "30", "estado_civil": "soltero"}`
- WHEN `recommend_insurance(profile)` is called
- THEN Asistencia Médica Viajes SHALL be in the result with `confidence: "high"`
- AND Accidentes Personales SHALL be in the result with `confidence: "medium"` (R2 partial match)

#### Scenario: Empty profile
- GIVEN `profile` = `{}`
- WHEN `recommend_insurance(profile)` is called
- THEN the result SHALL be an empty list — no rules matched

### Requirement: `quote_insurance()` tool

The tool SHALL compute a personalized quote based on the product and profile attributes. Signature: `quote_insurance(product_id: str, profile: dict) -> dict`.

Return SHALL include: `product_id`, `nombre`, `prima_mensual`, `prima_anual`, `cobertura_resumen`, `deducible`, `vigencia`.

Prima calculation SHALL be rule-based:
- Product base price × profile risk factor
- Risk factors SHALL be hardcoded constants (edad_factor, cobertura_factor)
- No external pricing API calls

#### Scenario: Quote for Vida product
- GIVEN `product_id="vida"` and `profile={"edad": 35, "suma_asegurada": 50000000}`
- WHEN `quote_insurance(product_id, profile)` is called
- THEN the result contains `prima_mensual` and `prima_anual`
- AND `prima_anual` = `prima_mensual * 12`

#### Scenario: Unknown product returns error
- GIVEN `product_id="nonexistent"`
- WHEN `quote_insurance(product_id, {})` is called
- THEN the result SHALL contain `{"error": "unknown_product"}`

### Requirement: Profile emergence from conversation

The `insurance_profile` JSON SHALL NOT be collected via a form — it SHALL emerge from natural conversation. Anna SHALL ask contextual questions about family, home, mobility, pets, and travel. The ChatService SHALL update `session.insurance_profile` incrementally as the AI extracts demographic attributes from the user's responses.

#### Scenario: Profile built conversationally
- GIVEN a session at `estado_actual="perfilando"`
- WHEN the user says "tengo dos hijos y vivo en Bogotá"
- THEN `session.insurance_profile` SHALL be updated with `{"familia_con_hijos": true}`
- AND the AI continues asking about other aspects (vivienda, mascotas, etc.)

#### Scenario: Profile sufficient triggers recommendation
- GIVEN `session.insurance_profile` has at least one confirmed attribute
- WHEN Anna determines no more profiling questions are needed
- THEN the system SHALL transition to `"recomendando"`
- AND Anna SHALL call `recommend_insurance(profile)` to present options

### Requirement: CSV data — offline only

The `backend/data/colsubsidio_segments.csv` file SHALL contain demographic segment analysis for Anna's system prompt context. It SHALL NOT be loaded at runtime. It SHALL contain aggregate segment data only — never raw member rows or PII.

#### Scenario: CSV structure
- GIVEN `colsubsidio_segments.csv`
- WHEN inspected
- THEN it SHALL contain columns: `segment_name`, `age_range`, `income_range`, `typical_family_size`, `common_products`, `pain_points`
- AND SHALL NOT contain `documento`, `nombre`, `telefono`, or any individually identifiable data

## Dependencies

- `data-models` — `session.insurance_profile` JSON field
- `insurance-conversational-flow` — state machine states (perfilando, recomendando, cotizando)
- `fastmcp-server` — tool registration for recommend_insurance, quote_insurance
- CSV file at `backend/data/colsubsidio_segments.csv` — offline analysis only
