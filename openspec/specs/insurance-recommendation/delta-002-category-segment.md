# Insurance Recommendation — Delta Spec: Category × Segment Personalization

> **Capability:** `insurance-recommendation`
> **Change:** `insurance-personalization-by-category`
> **Parent Spec:** `openspec/specs/insurance-recommendation/spec.md`
> **Date:** 2026-07-23

## Purpose

Extend the deterministic rule engine with compound rules that map `categoria_afiliacion` (A/B/C) and `segmento_grupo_familiar` (LAMBDA/RHO/EPSILON/IOTA/CHI/THETA/PI) to insurance products. Conversational rules (R1-R7) remain as fallback when category or segment data is unavailable.

## Terminology

| Term | Mapping | Source |
|------|---------|--------|
| CATEGORIA A | SIGMA (72.8% of dataset) | Customer model or `_calcular_categoria(salario)` |
| CATEGORIA B | PI (16.4%) | Customer model or `_calcular_categoria(salario)` |
| CATEGORIA C | ZETA (9.8%) | Customer model or `_calcular_categoria(salario)` |
| CATEGORIA MU / "sin categoría" | MU (1.0%) | Fallback — no A/B/C assigned |
| LAMBDA | Sin grupo familiar (57.3%) | CSV dataset only |
| RHO | Monoparental (24.3%) | CSV dataset only |
| EPSILON | Nuclear (9.4%) | CSV dataset only |
| IOTA | Pareja (5.1%) | CSV dataset only |
| CHI / THETA / PI(segmento) | Unknown | CSV dataset only |

## Requirements

### Requirement: Profile enrichment

The recommendation engine SHALL support an enriched profile that includes `categoria_afiliacion` and `segmento_grupo_familiar` alongside conversational attributes.

The `match_products()` function SHALL remain backward-compatible: profiles without `categoria_afiliacion` SHALL use only R1-R7 conversational rules.

A new function `match_products_by_segment(profile: dict, categoria: str | None, segmento: str | None) -> list[dict]` SHALL:
1. If `categoria` is `"A"`, `"B"`, or `"C"` → apply compound rules (R8-R13) that require that categoria
2. If `categoria` is `None`, `"MU"`, or any value outside A/B/C → skip compound rules entirely
3. If `segmento` is provided and non-empty → apply segment-weighted modifiers (boost or demote specific products)
4. Compound rules SHALL NOT override conversational rules — they SHALL be additive
5. Always fall through to R1-R7 at medium confidence as a safety net

#### Scenario: Profile with categoria A recommends Vida + Hogar before Viajes
- GIVEN `segment_data_categoria = "A"` and `segment_data_segmento = "LAMBDA"`
- WHEN `match_products_by_segment(profile, "A", "LAMBDA")` is called with empty conversational profile
- THEN the result SHALL include "Seguro de Vida" (product "vida") and "Seguro Hogar" (product "hogar")
- AND "Asistencia Médica Viajes" (product "viajes") SHALL NOT appear before "Seguro de Vida"
- AND all results SHALL have `confidence: "medium"` (compound rule, no conversational confirmation)

#### Scenario: Profile with categoria B recommends Accidentes + Movilidad
- GIVEN `categoria = "B"` and `segmento = "RHO"`
- WHEN `match_products_by_segment(profile, "B", "RHO")` is called with empty conversational profile
- THEN the result SHALL include "Accidentes Personales" (product "accidentes") and "Seguro Movilidad" (product "movilidad")
- AND "Seguro de Vida" SHALL NOT appear unless R1-R7 also match

#### Scenario: Profile with categoria C recommends premium tiers
- GIVEN `categoria = "C"` and `segmento = "EPSILON"`
- WHEN `match_products_by_segment(profile, "C", "EPSILON")` is called
- THEN the result SHALL include all 6 products
- AND "Seguro de Vida" and "Seguro Hogar" SHALL have `confidence: "high"`
- AND "Accidentes Personales" SHALL have `confidence: "medium"`

#### Scenario: MU returns R1-R7 only
- GIVEN `categoria = "MU"` or `categoria = None`
- WHEN `match_products_by_segment(profile, "MU", None)` is called
- THEN no compound rules SHALL apply
- AND only R1-R7 conversational rules SHALL determine the result

#### Scenario: Conversational + category rules combine
- GIVEN `categoria = "A"`, conversationally confirmed `viaja_frecuentemente = True`
- WHEN `match_products_by_segment(profile, "A", None)` is called
- THEN "Asistencia Médica Viajes" SHALL be in results with `confidence: "high"` (R3 matched)
- AND compound rules SHALL add category-matching products at `confidence: "medium"`

### Requirement: Compound rules table (R8-R13)

The engine SHALL define new rules in a `SEGMENT_RULES: list[tuple[str, str, str]]` structure:

| Rule ID | Categoria | Segmento | Product(s) | Rationale |
|---------|-----------|----------|------------|-----------|
| R8 | A | LAMBDA | vida, hogar | Singles/low-income — basic protection (Vida is #1 for SIGMA in drogueria) |
| R9 | A | RHO | vida, accidentes | Monoparental — life + personal accident protection |
| R10 | A | EPSILON | vida, hogar | Nuclear family — home + life |
| R11 | B | any | accidentes, movilidad | Mid-income — mobility + personal accident (PI's top products) |
| R12 | C | any | vida, hogar, movilidad, accidentes, viajes, mascotas | High-income — all products (ZETA sees all categories) |
| R13 | any | IOTA | vida, hogar | Couples — home + life regardless of income |

Segment weighting modifiers:
- Segment does NOT exclude any product — it only boosts/prioritizes
- When segmento is unknown (CHI/THETA/PI) or None → no segment modifier
- The modifier SHALL reorder results: boosted products appear before non-boosted at same confidence level

#### Scenario: R8 — Categoria A + LAMBDA
- GIVEN `categoria = "A"`, `segmento = "LAMBDA"`
- WHEN compound rules are evaluated
- THEN R8 SHALL add "vida" and "hogar" to matched products

#### Scenario: R9 — Categoria A + RHO
- GIVEN `categoria = "A"`, `segmento = "RHO"`
- WHEN compound rules are evaluated
- THEN R9 SHALL add "vida" and "accidentes" to matched products

#### Scenario: R10 — Categoria A + EPSILON
- GIVEN `categoria = "A"`, `segmento = "EPSILON"`
- WHEN compound rules are evaluated
- THEN R10 SHALL add "vida" and "hogar" to matched products

#### Scenario: R11 — Categoria B
- GIVEN `categoria = "B"`
- WHEN compound rules are evaluated regardless of segmento
- THEN R11 SHALL add "accidentes" and "movilidad" to matched products

#### Scenario: R12 — Categoria C
- GIVEN `categoria = "C"` with any segmento
- WHEN compound rules are evaluated
- THEN R12 SHALL add "vida", "hogar", "movilidad", "accidentes", "viajes", "mascotas" to matched products
- AND "vida" + "hogar" SHALL have `confidence: "high"`
- AND all others SHALL have `confidence: "medium"`

#### Scenario: R13 — Any category + IOTA
- GIVEN `segmento = "IOTA"` with any categoria
- WHEN compound rules are evaluated
- THEN R13 SHALL add "vida" and "hogar" to matched products

#### Scenario: Compound rule products use full product catalog
- GIVEN any compound rule matches
- WHEN products are resolved from rule IDs
- THEN each product_id SHALL resolve to the same `PRODUCTS` dict entry used by R1-R7
- AND the output dict SHALL include all same fields: `product_id`, `nombre`, `descripcion`, `categoria`, `prima_base`, `match_reason`, `confidence`

### Requirement: Confidence by rule type

| Rule Source | Confidence | match_reason |
|-------------|------------|-------------|
| R1-R7 (conversational match) | high | Existing reasons unchanged |
| Compound rule (categoria only, no segment) | medium | "Producto popular en tu categoría de afiliación ({categoria})" |
| Compound rule (categoria + segment) | medium | "Común en afiliados {categoria} con perfil {segmento_label}" |
| Compound (confirmado conversacionalmente) | high | Combination: original reason + "y está alineado con tu categoría" |
| R1-R7 (fallback, no categoria) | medium | Existing reason + "(perfil general)" |

#### Scenario: Compound rule match_reason contains category info
- GIVEN `categoria = "A"`, rule R8 matches
- WHEN the result is inspected
- THEN `match_reason` SHALL contain "categoría A" or "afiliación A"
- AND the `confidence` SHALL be "medium"

### Requirement: Anonymous user flow

When Anna has no documento and asks salary range, the system SHALL:
1. Receive the salary value from conversation → stored in `insurance_profile.salario`
2. Call `_calcular_categoria(salario)` (imported from `domain_tools.py`) to compute categoria
3. Store the computed categoria in `insurance_profile.categoria_afiliacion`
4. No segmento available for anonymous users (CSV-only)
5. Continue with compound rules using only categoria

#### Scenario: Salary triggers category inference
- GIVEN a session at `estado_actual = "perfilando"` with no documento
- WHEN Anna asks the salary range and the user responds "ganó 2 millones"
- THEN the system SHALL extract the salary into `insurance_profile.salario`
- AND `insurance_profile.categoria_afiliacion` SHALL be set to `"A"` (2M ≤ 2 SMMLV)
- AND subsequent `recommend_insurance()` calls SHALL use categoria A rules

#### Scenario: Salary not provided
- GIVEN a session with no documento and no salary in profile
- WHEN `match_products_by_segment()` is called
- THEN categoria is None → SHALL fall through to R1-R7 only

### Requirement: Backward compatibility

All existing scenarios from `spec.md` SHALL pass unchanged:
- Empty profile → empty list
- R1-R7 rules match with same conditions
- `quote_product()` unchanged
- Profiles without `categoria_afiliacion` key → R1-R7 only
- `match_products(profile)` (the original function) SHALL remain unmodified

#### Scenario: Existing R1-R7 tests pass
- GIVEN the existing `test_recommendation_engine.py`
- WHEN all tests are run
- THEN TestProductsCatalog, TestRules, TestMatchProducts, TestMatchProductsEdgeCases, TestCoverageMultipliers, TestQuoteProduct SHALL all pass without changes

## Dependencies

- `backend/app/services/recommendation_engine.py` — modified: add `SEGMENT_RULES`, `match_products_by_segment()`
- `backend/app/services/segment_data.py` — new: SegmentDataService singleton
- `backend/app/tools/domain_tools.py` — `_calcular_categoria()` used by anonymous flow
- `data-models` — `session.insurance_profile` already stores JSON
- `insurance-conversational-flow` — profiling instructions updated for salary question
- `chat-sessions` — profile pre-seed from documento lookup

## Files Affected

| File | Change |
|------|--------|
| `backend/app/services/recommendation_engine.py` | +SEGMENT_RULES constant, +match_products_by_segment(), +confidence/reason helpers |
| `backend/tests/test_recommendation.py` | +TestCompoundRules, +TestProfileEnrichment, +TestAnonymousFlow, +TestBackwardCompat |
