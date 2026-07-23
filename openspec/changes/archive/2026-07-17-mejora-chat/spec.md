# Spec: Mejora Chat — Categorías de Afiliación y Tasas Diferenciales

> **Change:** `mejora-chat`
> **Capabilities:** `interest-rates` (new), `data-models` (modified), `mcp-domain-tools` (modified), `form-data-collection` (modified), `chat-api-stub` (modified)
> **Date:** 2026-07-17

## Purpose

Anna (the AI assistant) currently uses a flat 18% rate for all credit simulations and cannot determine which rate applies to a given customer. This spec adds Colsubsidio's affiliation categories (A/B/C), a lookup table for differential interest rates per category and product, and the logic to compute and surface category-specific rates throughout the chat flow.

---

## Requirements

### R1: Customer model — `categoria_afiliacion` column

The `Customer` model SHALL gain a column `categoria_afiliacion` of type `String(1)`, nullable, with a CHECK constraint `IN ('A','B','C')`.

#### Business rules

- The column SHALL be auto-calculated on customer creation/update via `_calcular_categoria(salario)`.
- The column MAY be set manually (overriding auto-calculation) — manual value takes precedence.
- When `salario` is `0` or `None`, the auto-calculated category SHALL be `'A'`.

#### Scenarios

- **Happy path**: GIVEN a customer with `salario=3500000` WHEN created THEN `categoria_afiliacion` SHALL be `'A'`.
- **Manual override**: GIVEN a customer with `salario=8000000` (auto→C) WHEN `categoria_afiliacion` is set to `'B'` manually THEN `'B'` persists regardless of salary.
- **Null salary**: GIVEN a customer with `salario=None` WHEN created THEN `categoria_afiliacion` SHALL be `'A'`.
- **Invalid value rejected**: GIVEN an attempt to set `categoria_afiliacion='D'` WHEN saving THEN the DB SHALL reject the value.

### R2: InterestRate model

The system SHALL define a new ORM model `InterestRate` with these columns:

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID (PK) | `default=uuid4` |
| categoria | String(1) | `nullable=False`, `CHECK IN ('A','B','C')` |
| product_id | UUID (FK→Product) | `nullable=False`, indexed |
| tasa_min | Float | `nullable=False` |
| tasa_max | Float | `nullable=False` |
| vigencia_desde | Date | `nullable=False` |
| activo | Boolean | `default=True` |
| created_at | DateTime | `default=utcnow` |

The model SHALL be unique on `(categoria, product_id, vigencia_desde)`.

#### Scenarios

- **Rate lookup**: GIVEN a product and category WHEN querying the most recent active InterestRate THEN the matching rate is returned.
- **No rate found**: GIVEN no InterestRate exists for a category+product pair WHEN queried THEN the system SHALL return a fallback of 18%.
- **Duplicate prevented**: GIVEN an existing `(A, product-X, 2026-01-01)` WHEN inserting the same triple THEN the DB SHALL enforce uniqueness.

### R3: `_calcular_categoria(salario)` function

The system SHALL implement a pure function `_calcular_categoria(salario: int) -> str` applying SMMLV 2026 = $1.750.905:

| Condition | Result |
|-----------|--------|
| salario <= 2 SMMLV ($3.501.810) | `'A'` |
| salario <= 4 SMMLV ($7.003.620) | `'B'` |
| salario > 4 SMMLV ($7.003.620) | `'C'` |
| salario is 0, None, or missing | `'A'` |

#### Scenarios

- **Category A**: GIVEN `salario=3500000` WHEN called THEN returns `'A'`.
- **Category B threshold**: GIVEN `salario=3501811` WHEN called THEN returns `'B'`.
- **Category B upper**: GIVEN `salario=7003620` WHEN called THEN returns `'B'`.
- **Category C**: GIVEN `salario=7003621` WHEN called THEN returns `'C'`.
- **No salary**: GIVEN `salario=0` WHEN called THEN returns `'A'`.

### R4: InterestRate seed data

The seed script SHALL create InterestRate records for every credit product × every category (A/B/C) using the reference rates below.

**Tasas (% EA) por categoría y tipo de producto:**

| Producto | A | B | C |
|----------|---|---|---|
| Crédito Libre Inversión (libranza) | 12 | 15 | 18 |
| Crédito Libre Inversión (pago directo) | 15 | 18 | 22 |
| Compra de Cartera (libranza) | 12 | 15 | 18 |
| Compra de Cartera (pago directo) | 15 | 18 | 22 |
| Crédito para Mujeres | 12 | 15 | 18 |
| Crédito Educativo | 10 | 13 | 16 |
| Crédito Hipotecario | 10.7 | 10.7 | 10.7 |
| Cupo de Crédito | 18 | 22 | 26 |
| Microcrédito | 20 | 24 | 28 |

Rates for products not listed SHALL use 18% as default across all categories.

#### Scenario

- GIVEN the seed runs WHEN completed THEN `InterestRate` has at least 27 rows (9 products × 3 categories).
- GIVEN seed data WHEN queried THEN `tasa_min == tasa_max` for all entries (single rate per category+product).

### R5: `simulate_credit` — signature and rate lookup

The `simulate_credit` tool signature SHALL change from `(monto, plazo)` to `(monto, plazo, customer_id: str | None = None)`.

Behavior:
1. If `customer_id` is provided, look up the customer's `categoria_afiliacion`.
2. Query `InterestRate` for the matching category and the customer's requested product type (`tipo_solicitud` from session form_data).
3. Use `tasa_min` as the effective annual rate for calculation.
4. If no matching InterestRate is found, fallback to 18%.
5. If `customer_id` is not provided, use fallback 18%.
6. Monthly payment SHALL use the **French amortization formula**: `cuota = P * [r(1+r)^n] / [(1+r)^n - 1]`, where `r = tasa_anual/12`.

#### Scenarios

- **With customer_id found**: GIVEN `customer_id` for Juan Pérez (cat. A), `monto=5000000`, `plazo=24`, tipo="Libre Inversión" WHEN called THEN `cuota_mensual` reflects 12% annual rate.
- **Without customer_id**: GIVEN no `customer_id` WHEN called THEN tasa is 18%.
- **Unknown product**: GIVEN a product with no InterestRate record WHEN called THEN tasa fallback is 18%.
- **Invalid monto/plazo**: GIVEN `monto <= 0` or `plazo <= 0` WHEN called THEN returns error.

### R6: `get_customer` — include `categoria_afiliacion`

The `get_customer` tool SHALL include `categoria_afiliacion` in its output string. If `categoria_afiliacion` is null (e.g., legacy data before migration), it SHALL be computed on-the-fly from `salario` using `_calcular_categoria`.

#### Scenarios

- **With categoria**: GIVEN a customer with `categoria_afiliacion='A'` WHEN called THEN the output contains `"Categoría: A"`.
- **Null categoria**: GIVEN a customer where `categoria_afiliacion IS NULL` WHEN called THEN `_calcular_categoria` runs and the output shows the computed category.

### R7: `create_application` — `modalidad_pago`

The `create_application` SHALL:
1. Read `modalidad_pago` from `form_data` (values: `"libranza"` or `"pago_directo"`).
2. Populate `Credit.modalidad_pago` with that value.
3. The AI SHALL ask the customer "¿preferís libranza (descuento por nómina) o pago directo?" before calling `create_application`.

#### Scenarios

- **With modalidad**: GIVEN `form_data` contains `modalidad_pago="libranza"` WHEN `create_application` runs THEN `Credit.modalidad_pago == "libranza"`.
- **Without modalidad**: GIVEN `form_data` lacks `modalidad_pago` WHEN called THEN `Credit.modalidad_pago` is `None`.
- **Conversational prompt**: GIVEN all required fields are collected WHEN the AI asks for the last field THEN it SHALL ask for modalidad de pago before offering confirmation.

### R8: System prompt — categories and rates

The `_build_system_prompt` method SHALL append a `CATEGORÍAS Y TASAS` section containing:
- SMMLV 2026 value and salary ranges per category.
- A markdown table of reference interest rates per product and category.
- Clarification that rates are "valores referenciales para esta demo" and final rates depend on credit evaluation.

#### Scenario

- GIVEN a chat session WHEN `_build_system_prompt` is called THEN the output contains a "CATEGORÍAS Y TASAS" section with a rate table.
- GIVEN the system prompt WHEN a user asks "¿qué tasa me corresponde?" THEN Anna SHALL reference the category and rate table in her response.

### R9: FormSchema — optional `categoria_afiliacion` field

The `FormSchema` SHALL add an optional field:
- `nombre`: `"categoria_afiliacion"`, `tipo`: `"select"`, `requerido`: `False`, `seccion`: `"Datos Personales"`, `validaciones`: `{"enum": ["A", "B", "C"]}`, `prompt_question`: `"¿Sabés cuál es tu categoría de afiliación en Colsubsidio?"`.

The AI SHALL only ask this field if the category could not be determined automatically (e.g., customer has no salary on record).

#### Scenario

- **Schema includes field**: GIVEN `FormSchema.to_prompt_text()` WHEN inspected THEN it includes `categoria_afiliacion (select) [opt]`.
- **Auto-determined skip**: GIVEN the customer has a salary that auto-computes to category A WHEN the AI collects data THEN the AI SHALL NOT ask for `categoria_afiliacion` (it's pre-filled).

### R10: Seed — customer categories

The seed data SHALL set:
- Juan Pérez (salario $3.500.000, < 2 SMMLV) → `categoria_afiliacion = 'A'`.
- Pedro Jiménez (salario $0) → `categoria_afiliacion = 'A'`.

#### Scenario

- GIVEN the seed runs WHEN customers are inserted THEN `categoria_afiliacion` is populated for both customers.

---

## Business Rules

| Rule | Description |
|------|-------------|
| BR1 | SMMLV 2026 = $1.750.905 (hardcoded constant). |
| BR2 | Category auto-calculation runs on customer create/update but manual value overrides. |
| BR3 | Missing InterestRate → fallback 18%. |
| BR4 | Rate lookup uses the most recent `vigencia_desde` where `activo = True`. |
| BR5 | French amortization is the single formula for monthly payment. |
| BR6 | `modalidad_pago` is asked conversationally before confirming the application. |
| BR7 | System prompt MUST clarify rates are "valores referenciales para esta demo". |

---

## Dependencies

| Dependency | Direction | Reason |
|------------|-----------|--------|
| `data-models` → `mcp-domain-tools` | InterestRate model must exist before simulate_credit queries it | R2, R5 |
| `mcp-domain-tools` → `chat-api-stub` | simulate_credit receives customer_id from chat session | R5 |
| `form-data-collection` → `mcp-domain-tools` | modalidad_pago collected during chat, used by create_application | R7 |
| `chat-api-stub` → `form-data-collection` | System prompt references FormSchema fields | R8, R9 |

---

## Capability Mapping

| Capability | Type | Artifact |
|------------|------|----------|
| `interest-rates` | New model | `backend/app/models/interest_rate.py` |
| `data-models` | Modified | `+categoria_afiliacion` in Customer, `+InterestRate` in `__init__.py` |
| `mcp-domain-tools` | Modified | `domain_tools.py` — simulate_credit, get_customer |
| `form-data-collection` | Modified | `credit_form.py` — +categoria_afiliacion field |
| `chat-api-stub` | Modified | `chat.py` — _build_system_prompt section |
| Seed | Modified | `seed.py` — categorías + InterestRate records |

---

## Acceptance Criteria

| Req | Criteria |
|-----|----------|
| R1 | Customer row has `categoria_afiliacion` set on create; CHECK constraint rejects invalid values |
| R2 | InterestRate table exists with 3×N rows; unique constraint enforced |
| R3 | `_calcular_categoria` returns correct category for all salary ranges |
| R4 | Seed creates all 27+ InterestRate records |
| R5 | `simulate_credit` returns different cuotas for different categories |
| R6 | `get_customer` output includes `Categoría: X` |
| R7 | Created Credit has `modalidad_pago` populated from form_data |
| R8 | System prompt contains CATEGORÍAS Y TASAS section with reference table |
| R9 | FormSchema includes optional `categoria_afiliacion` field |
| R10 | Seed customers have `categoria_afiliacion='A'` |
