# Proposal: Mejora Chat — Categorías de Afiliación y Tasas Diferenciales

## Intent

Anna no puede responder qué tasa aplica a cada cliente porque `simulate_credit` usa 18% fijo y no existe el concepto de categoría A/B/C de Colsubsidio. Esto rompe la credibilidad de la demo y bloquea consultas reales como "¿qué tasa me corresponde?".

## Scope

### In Scope
1. Columna `categoria_afiliacion` (enum A/B/C) en Customer
2. Modelo `InterestRate` con tasas por categoría y tipo de producto
3. Cálculo automático de categoría según salario (SMMLV 2026)
4. `simulate_credit` usa tasa según categoría + producto
5. `get_customer` retorna `categoria_afiliacion`
6. System prompt de Anna con tabla de categorías y tasas
7. Seed data actualizado con categorías y registros de tasa
8. Activar columna `modalidad_pago` en Credit (ya existe en tabla) — popular al crear crédito

### Out of Scope
Tasas reales exactas de Colsubsidio, lógica de precios de seguros (no aplican categorías), integración con backend real de Colsubsidio, notificaciones multicanal.

## Capabilities

### New
- `interest-rates`: Tabla de tasas de interés por categoría A/B/C y tipo de producto, con vigencia.

### Modified
- `data-models`: +columna `categoria_afiliacion` (String(1)) en Customer; +modelo InterestRate.
- `mcp-domain-tools`: `simulate_credit` acepta `customer_id` y usa tasa diferencial; `get_customer` incluye `categoria_afiliacion`.
- `form-data-collection`: `categoria_afiliacion` como campo opcional select (A/B/C) en FormSchema.
- `chat-api-stub`: System prompt inyectado con tabla de categorías y tasas referenciales.

## Approach

1. **InterestRate model**: id, categoria (A/B/C), product_id (FK→Product), tasa_min, tasa_max, vigencia_desde, activo.
2. **SMMLV 2026: $1.750.905** (fuente: decreto gov.co). **`_calcular_categoria(salario)`**: salario ≤ 2 SMMLV ($3.501.810) → A, ≤ 4 SMMLV ($7.003.620) → B, > 4 SMMLV → C. Si salario es 0 o None → A.
3. **`_get_tasa(categoria, product_id)`**: query tasa vigente más reciente por categoría+producto. Fallback 18% si no hay registro.
4. **`simulate_credit(monto, plazo, customer_id)`**: busca customer → calcula categoría → obtiene tasa → calcula cuota con fórmula estándar.
5. **`get_customer`**: append `categoria_afiliacion` (calculada desde salario si no está fijada manualmente).
6. **System prompt**: en `_build_system_prompt`, agregar sección "CATEGORÍAS Y TASAS" con tabla markdown de rangos SMMLV y tasas referenciales por producto.
7. **`create_application`**: al crear el crédito, preguntar modalidad de pago ("libranza" o "pago directo") y guardar en `Credit.modalidad_pago`.
8. **Seed**: Juan Pérez ($3.5M, < 2 SMMLV) → A, Pedro Jiménez ($0) → A. Crear registros InterestRate para productos de crédito con tasas demo.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `models/customer.py` | Modified | +columna categoria_afiliacion |
| `models/interest_rate.py` | New | Modelo InterestRate |
| `tools/domain_tools.py` | Modified | simulate_credit + categoría; get_customer |
| `services/chat.py` | Modified | System prompt con categorías y tasas |
| `schemas/credit_form.py` | Modified | +campo categoria_afiliacion |
| `seed.py` | Modified | Categorías seed + tasas demo |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Tasas demo no coinciden con Colsubsidio real | Low | Prompt aclara "valores referenciales para esta demo" |
| Cliente sin salario → categoría default | Low | Salario 0/None → A (regla Colsubsidio: menor ingreso = mayor subsidio) |

## Rollback Plan

1. Revert Customer model (drop column), delete InterestRate model and table
2. Revert `domain_tools.py` a `simulate_credit` anterior y `get_customer` anterior
3. Revert `chat.py` system prompt (quitar sección CATEGORÍAS Y TASAS)
4. Revert `credit_form.py` (quitar campo)
5. Revert `seed.py`

## Dependencies

Depende de `data-models`, `mcp-domain-tools`, `form-data-collection`, `chat-sessions` (todas existentes de fases anteriores).

## Success Criteria

- [ ] Anna explica las categorías A/B/C y sus diferencias, y determina la del cliente
- [ ] `simulate_credit` devuelve tasas distintas según categoría y producto
- [ ] `get_customer` incluye `categoria_afiliacion`
- [ ] La categoría se persiste en Customer y se reusa entre sesiones
- [ ] Seed actualizado con datos coherentes (Juan Pérez → A, Pedro Jiménez → A)
