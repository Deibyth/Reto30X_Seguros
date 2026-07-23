# Tests Specification

## Purpose

Cover 8 untested areas: category calc, credit simulation rate lookup, analytics endpoints, ToolBridge transforms, security middleware, InterestRate CRUD, customer lookup with category, application creation with payment modality.

## Requirements

### T-CALC: _calcular_categoria

Pure function MUST return correct category for each input.

| Scenario | Input | Expected |
|----------|-------|----------|
| No salary | `None` | `"A"` |
| Zero salary | `0` | `"A"` |
| At 2 SMMLV | `2*SMMLV_2026` | `"A"` |
| At 4 SMMLV | `4*SMMLV_2026` | `"B"` |
| Above 4 SMMLV | `4*SMMLV_2026+1` | `"C"` |
| Positive low | `1` | `"A"` |
| Above 2 SMMLV | `2*SMMLV_2026+1` | `"B"` |

### T-SIM: simulate_credit rate lookup

MUST look up InterestRate by `(categoria, product_id, modalidad_pago)` when `product_id` is given, else use 18.0%.

| Scenario | Product ID | Rate exists | Expected |
|----------|-----------|-------------|----------|
| Rate found | valid UUID | Yes | `(tasa_min+tasa_max)/2` |
| Product exists, no rate | valid UUID | No | Fallback by product type name |
| Product not found | invalid UUID | — | 18.0 |
| No product_id | `None` | — | 18.0 |

### T-ANALYTICS: Analytics endpoints

Each endpoint MUST return correct structure with populated DB.

| Endpoint | Key assertions |
|----------|---------------|
| `get_pipeline_summary` | `total_sessions`, `conversion_rate`, `abandon_at_section` |
| `get_daily_trends(30)` | `list[dict]` with `date`, `applications`, `completions` |
| `get_customer_profile` | `salary_distribution`, `contract_types`, `avg_tenure_months` |
| `get_credit_stats` | `avg_amount`, `amount_ranges`, `destino_distribution` |
| `get_ai_efficiency` | `avg_messages_per_completed_session`, `sessions_with_tool_errors` |
| `get_full_summary` | All 5 sub-keys (`pipeline`, `trends`, `customers`, `credits`, `efficiency`) |

### T-TOOLBRIDGE: ToolBridge transforms

MUST hide `session_id` from schema and inject it at execution.

| Scenario | Assertion |
|----------|-----------|
| `session_id` hidden | `get_openai_tools()` for `save_form_field` excludes `session_id` from `properties` and `required` |
| `session_id` injected | `execute_tool("save_form_field", {...})` adds `session_id` before MCP call |
| Other tools unaffected | `get_openai_tools()` for `get_products` preserves all params |
| Unknown tool | `execute_tool("nonexistent")` raises `ValueError` |

### T-SECURITY: SecurityMiddleware

MUST add security headers to every response and rate-limit after threshold.

| Scenario | Assertion |
|----------|-----------|
| CSP header | Response has `Content-Security-Policy` |
| X-Content-Type-Options | `nosniff` |
| X-Frame-Options | `DENY` |
| Rate limited | After `max_requests+1` → 429 + `Retry-After` |
| `/health` whitelisted | Never rate-limited |
| HSTS in production | `Strict-Transport-Security` only when `env=production` |

### T-RATE: InterestRate queries

MUST support create, lookup by triple, and enforce unique constraint.

| Scenario | Assertion |
|----------|-----------|
| Create rate | Row persisted with all fields |
| Lookup by triple | `(categoria, product_id, modalidad_pago)` returns matching row |
| Unique violation | Duplicate `(cat, prod, modal, vigencia)` raises integrity error |
| Active filter | Row with `activo=False` excluded from queries |

### T-CUSTOMER: get_customer with categoria

MUST include `categoria_afiliacion` from DB column or computed value.

| Scenario | DB has | Outcome |
|----------|--------|---------|
| `categoria_afiliacion` set | `"B"` | Output shows `"B"` |
| No categoria, has salary | `None` | Computed from salary (≤2 SMMLV → `"A"`) |
| No categoria, no salary | `None` | Defaults to `"A"` |

### T-APPLICATION: create_application with modalidad

MUST persist `modalidad_pago` from `form_data` into the `Credit` row.

| Scenario | form_data has | Credit.modalidad_pago |
|----------|--------------|----------------------|
| Provided | `{"modalidad_pago": "libranza"}` | `"libranza"` |
| Absent | `{"nombres": "Juan"}` | `None` |

## What Was Built

33 new tests across 5 files. Zero regressions — all 89 tests pass.

| File | New Tests | Area |
|------|-----------|------|
| `test_domain_tools.py` | 12 | `_calcular_categoria` (5), `simulate_credit` rate lookup (4), `get_customer` with categoria (1), `create_application` with modalidad (2) |
| `test_analytics.py` | 7 | AnalyticsService: pipeline, trends, customer profile, credit stats, AI efficiency, full summary, 503 handling |
| `test_tool_bridge.py` | 5 | Schema transforms, `session_id` hidden/injected, unknown tool error |
| `test_security.py` | 5 | SecurityMiddleware: CSP, headers, HSTS, rate-limit 429, `/health` whitelist |
| `test_interest_rate.py` | 4 | InterestRate: create, lookup by triple, nonexistent returns None, unique constraint |

**Coverage areas:** `domain_tools` (categoría, crédito, customer), `InterestRate`, `ToolBridge`, `AnalyticsService`, `SecurityMiddleware`.

**Results:** Baseline was 57 tests (chat, routers, credit_form). Added 33 → **89 total**. All pass, 0 regressions.
