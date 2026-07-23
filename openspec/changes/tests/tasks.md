# Tasks: Backend Test Coverage

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~350 (all additions, zero deletions) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | All 8 test areas | PR 1 | `pytest backend/tests/ -v` | `pytest backend/tests/ -x --co` | `git checkout -- backend/tests/` — zero production change |

## Phase 1: Tests unitarios puros (sin DB)

- [x] **T1** — Tests para `_calcular_categoria`: 5 casos (None→A, 0→A, ≤2 SMMLV→A, ≤4 SMMLV→B, >4 SMMLV→C). File: `backend/tests/test_domain_tools.py`. Dep: ninguna. Prioridad: alta.
- [x] **T7** — Tests unitarios para `ToolBridge`: 5 casos (schema oculta `session_id`, otros tools no afectados, `execute_tool` inyecta `session_id`, unknown tool raise `ValueError`, `get_openai_tools` retorna lista). File: `backend/tests/test_tool_bridge.py` (nuevo). Mock FastMCP. Dep: ninguna. Prioridad: alta.

## Phase 2: Tests con DB (fixtures existentes)

- [x] **T2** — Tests para `InterestRate` queries: 4 tests (create row, lookup by triple+activo, nonexistent combi retorna None, unique constraint). File: `backend/tests/test_interest_rate.py` (nuevo). Fixture: `db_session`. Dep: ninguna. Prioridad: alta.
- [x] **T4** — Test para `get_customer` con `categoria_afiliacion`: seed Customer con categoria explícita, verificar output incluye categoría. File: `backend/tests/test_domain_tools.py`. Fixture: `domain_db_maker`. Dep: ninguna. Prioridad: media.
- [x] **T5** — Tests para `create_application` con `modalidad_pago`: 2 tests (con y sin modalidad en form_data). File: `backend/tests/test_domain_tools.py`. Fixture: `domain_db_maker`. Dep: ninguna. Prioridad: media.
- [x] **T3** — Tests para `simulate_credit` con product_id: 4 tests (basic, invalid amount, invalid plazo, rate lookup from DB). File: `backend/tests/test_domain_tools.py`. Fixture: `domain_db_maker` + seed InterestRate. Dep: suave hacia T2 (patrón de seed). Prioridad: media.

## Phase 3: Tests de integración

- [x] **T6** — Tests de integración para `AnalyticsService`: 7 tests (pipeline summary, daily trends, customer profile, credit stats, AI efficiency, full summary, 503 unavailable). File: `backend/tests/test_analytics.py` (nuevo). Pre-seeded DB fixture + TestClient directo. Dep: ninguna. Prioridad: alta.
- [x] **T8** — Tests de integración para `SecurityMiddleware`: 5 tests (CSP header, X-Content-Type-Options, X-Frame-Options, rate-limit 429 con Retry-After, `/health` whitelisted). File: `backend/tests/test_security.py` (nuevo). TestClient con `chat_rate_limit_per_minute=2`. Dep: ninguna. Prioridad: alta.
