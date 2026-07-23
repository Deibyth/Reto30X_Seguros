# Archive Report: mejora-chat

> **Estado:** Completado (intentional-with-warnings)
> **Fecha de archivo:** 2026-07-17
> **Modo:** openspec
> **Archivado en:** `openspec/changes/archive/2026-07-17-mejora-chat/`

---

## 1. Cambio

**mejora-chat** — Categorías de Afiliación y Tasas Diferenciales

## 2. Estado

**Completado** — Verificación: PASSED (10/10 requisitos, 0 CRITICAL, 0 WARNING)

> **Advertencia de archivo:** Las tareas de testing (Phase 4: 4.1–4.6) no fueron implementadas. El archive es intencional con esta advertencia, autorizado explícitamente por el orquestador. Las tareas Phase 2 tenían checkboxes obsoletos (`[ ]`) y fueron reconciliadas en el archive contra el verify-report que confirma su implementación completa.

## 3. Resumen

Se implementó el sistema de **categorías de afiliación A/B/C** de Colsubsidio con **tasas diferenciales por categoría y producto**:

- **Modelo `InterestRate`** — tasas por `(categoria, product_id, modalidad_pago, vigencia_desde)` con UniqueConstraint.
- **Columna `categoria_afiliacion`** en `Customer` — String(1), CHECK A/B/C, nullable, auto-calculada desde salario con `_calcular_categoria()`.
- **`_calcular_categoria(salario)`** — función pura basada en SMMLV 2026 ($1.750.905): ≤2 SMMLV → A, ≤4 SMMLV → B, >4 SMMLV → C.
- **`simulate_credit`** — nuevo signature `(monto, plazo, customer_id, categoria, modalidad)`; consulta `InterestRate` por categoría+producto+modalidad; French amortization; fallback por tipo de producto (18% default, 10.7% hipotecario, 12% educativo, 22% cupo, 24% microcrédito).
- **`get_customer`** — incluye `Categoría de afiliación: {categoria}` en output, computada on-the-fly si es null.
- **`create_application`** — lee `modalidad_pago` de `form_data` ("libranza"/"pago_directo") y lo persiste en `Credit.modalidad_pago`.
- **System prompt de Anna** — sección `CATEGORÍAS DE AFILIACIÓN Y TASAS` con tabla markdown de tasas, rangos SMMLV, disclaimer "valores referenciales para esta demo", e instrucción para preguntar modalidad de pago.
- **FormSchema** — campos opcionales `categoria_afiliacion` (select A/B/C) y `modalidad_pago` (select libranza/pago_directo).
- **Seed data** — 27 registros InterestRate (9 productos × 3 categorías); Juan Pérez (sal $3.5M → A), Pedro Jiménez (sal $0 → A).

## 4. Archivos creados

| Archivo | Descripción |
|---------|-------------|
| `backend/app/models/interest_rate.py` | Modelo ORM InterestRate con UniqueConstraint y FK a Product |

## 5. Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `backend/app/models/customer.py` | +columna `categoria_afiliacion` con CHECK A/B/C |
| `backend/app/models/__init__.py` | +import InterestRate, +`"InterestRate"` en `__all__` |
| `backend/app/tools/domain_tools.py` | +`_calcular_categoria`; `simulate_credit` con tasa diferencial; `get_customer` output; `create_application` con modalidad_pago |
| `backend/app/schemas/credit_form.py` | +campos `categoria_afiliacion` y `modalidad_pago` (select, opt) |
| `backend/app/services/chat.py` | +sección CATEGORÍAS DE AFILIACIÓN Y TASAS en system prompt |
| `backend/app/seed.py` | +categorías en seed customers; +27 registros InterestRate |
| `tests/test_credit_form.py` | Tests actualizados para nuevos campos (56 tests pasan) |

## 6. Métricas

**Tasas diferenciales probadas** — Libre Inversión (libranza):

| Categoría | Tasa % EA |
|-----------|-----------|
| A | 12.0% |
| B | 15.0% |
| C | 18.0% |

**Tasa fija anterior (sin cambio):** 18% para todos los clientes.

**Matriz completa de tasas (27 registros seed):**

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

**Fallbacks por producto:** 18% default consumo, 10.7% hipotecario, 12% educativo, 22% cupo, 24% microcrédito.

**Cobertura de tests:** 56 tests existentes pasan. Sin tests nuevos para la funcionalidad agregada (Phase 4 no implementada).

## 7. Tareas reconciliadas en archive

Las siguientes tareas tenían checkboxes obsoletos en `tasks.md` y fueron marcadas como completadas durante el archive, basado en evidencia del `verify-report.md`:

| Tarea | Evidencia |
|-------|-----------|
| 2.1 — simulate_credit con tasa diferencial | ✅ verify-report R5: DB query implementada, tasas A=12%, B=15%, C=18% verificadas |
| 2.2 — get_customer output | ✅ verify-report R6: output contiene `Categoría de afiliación: {categoria}` |
| 2.3 — create_application modalidad_pago | ✅ verify-report R7: `Credit.modalidad_pago` set desde form_data |
| 2.4 — FormSchema campos | ✅ verify-report R9: ambos campos presentes, en secciones correctas |

**No reconciliadas** (genuinamente no implementadas):
| Tarea | Estado |
|-------|--------|
| 4.1 — Unit test `_calcular_categoria` | 🔲 No implementado |
| 4.2 — Integration test InterestRate + simulate_credit | 🔲 No implementado |
| 4.3 — Test fallbacks simulate_credit | 🔲 No implementado |
| 4.4 — Test get_customer output | 🔲 No implementado |
| 4.5 — Test create_application modalidad_pago | 🔲 No implementado |
| 4.6 — Test InterestRate unique constraint | 🔲 No implementado |

## 8. Artefactos archivados

| Artefacto | Path archivado |
|-----------|----------------|
| Proposal | `openspec/changes/archive/2026-07-17-mejora-chat/proposal.md` |
| Spec | `openspec/changes/archive/2026-07-17-mejora-chat/spec.md` |
| Design | `openspec/changes/archive/2026-07-17-mejora-chat/design.md` |
| Tasks | `openspec/changes/archive/2026-07-17-mejora-chat/tasks.md` |
| Verify Report | `openspec/changes/archive/2026-07-17-mejora-chat/verify-report.md` |
| Archive Report | `openspec/changes/archive/2026-07-17-mejora-chat/archive-report.md` |

## 9. Próximos pasos recomendados

| Prioridad | Acción |
|-----------|--------|
| Alta | Implementar Phase 4 tests: unit test `_calcular_categoria` (5 thresholds), integration tests para InterestRate query, simulate_credit con categoría, get_customer output, create_application modalidad_pago, y unique constraint |
| Media | Dashboard de tasas por categoría visible para el usuario/admin |
| Media | Extraer constante `SMMLV_2026` a un módulo compartido (actualmente duplicada en `domain_tools.py` y `seed.py`) |
| Baja | Validación visual del flujo completo: chat → categoría → simulate_credit → create_application con modalidad_pago |
| Baja | Evaluar migración a Alembic para cambios de schema futuros |
