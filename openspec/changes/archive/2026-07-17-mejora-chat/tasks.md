# Tasks: Mejora Chat — Categorías y Tasas Diferenciales

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~410 |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Model + logic + seed + prompt + tests | PR 1 | `pytest tests/ -v -k "categoria or interest_rate or simulate_credit or create_application"` | `python -m app.seed --clear && uvicorn app.main:app` | drop interest_rates table + revert Customer col + revert domain_tools + revert seed + revert chat.py + revert credit_form.py |

## Phase 1: Foundation

- [x] 1.1 Create `backend/app/models/interest_rate.py` — InterestRate ORM: id (UUID pk), categoria (String(1), CHECK A/B/C), product_id (FK→Product, indexed), tasa_min, tasa_max, modalidad_pago (nullable String(50)), vigencia_desde (Date), activo (default=True), created_at, updated_at. UniqueConstraint(categoria, product_id, modalidad_pago, vigencia_desde)
- [x] 1.2 Modify `backend/app/models/customer.py` — add `categoria_afiliacion: Mapped[str | None] = mapped_column(String(1), CheckConstraint("categoria_afiliacion IN ('A','B','C')"), nullable=True)`
- [x] 1.3 Modify `backend/app/models/__init__.py` — import InterestRate, add `"InterestRate"` to `__all__`
- [x] 1.4 Add `_calcular_categoria(salario: int | None) -> str` in `backend/app/tools/domain_tools.py` — SMMLV_2026 = 1_750_905; 0/None→A, ≤2x→A, ≤4x→B, >4x→C

## Phase 2: Core Logic

- [x] 2.1 Update `simulate_credit(monto, plazo, customer_id=None, categoria=None, modalidad="libranza")` — query InterestRate by categoria+product_id+modalidad (activo, ORDER BY vigencia_desde DESC, LIMIT 1); fallback 18% (consumo), 10.7% (hipotecario), 12% (educativo); French amortization
- [x] 2.2 Update `get_customer` output — append `**Categoría:** {categoria}` line; compute via `_calcular_categoria` if null
- [x] 2.3 Update `create_application` — read `form_data.get("modalidad_pago")`, set `credit.modalidad_pago = valor`
- [x] 2.4 Modify `backend/app/schemas/credit_form.py` — add `categoria_afiliacion` (select, opt, enum A/B/C, prompt "¿Sabés tu categoría?") and `modalidad_pago` (select, opt, enum libranza/pago_directo, prompt "¿Libranza o pago directo?")

## Phase 3: Integration

- [x] 3.1 Modify `backend/app/services/chat.py` `_build_system_prompt()` — append CATEGORÍAS Y TASAS section: SMMLV ranges, rate markdown table, "valores referenciales" disclaimer, instruction to ask modalidad_pago before create_application
- [x] 3.2 Update `backend/app/seed.py` — set `categoria_afiliacion` on Juan Pérez (A) and Pedro Jiménez (A); insert 27 InterestRate rows per design rate table (7 product groups × 3 categorías, Libre Inversión and Compra de Cartera split by libranza/pago_directo)

## Phase 4: Testing

- [ ] 4.1 Unit test `_calcular_categoria`: 0→A, 3.5M→A, 3_501_811→B, 7_003_620→B, 7_003_621→C
- [ ] 4.2 Integration test: seed InterestRate, call `simulate_credit` with customer_id, verify category-specific rate in output
- [ ] 4.3 Test `simulate_credit` fallbacks: no customer_id → 18%, unknown product → 18%
- [ ] 4.4 Test `get_customer` returns `Categoría: A` for pre-set and for null+salary
- [ ] 4.5 Test `create_application` sets `Credit.modalidad_pago` from form_data (libranza, pago_directo, missing → None)
- [ ] 4.6 Test InterestRate unique constraint violation and rate query by categoria+product
