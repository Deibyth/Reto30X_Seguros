# Proposal: Backend Test Coverage — Mejora Chat & Critical Areas

## Intent

Cerrar brechas de cobertura identificadas en la exploration: código nuevo de mejora-chat (Phase 4) y servicios críticos enteros sin tests. Actualmente 57 tests backend, 0 en AnalyticsService, ToolBridge, SecurityMiddleware, InterestRate queries.

## Scope

### In Scope

1. Tests unitarios para `_calcular_categoria` (None, 0, ≤2 SMMLV, ≤4 SMMLV, >4 SMMLV)
2. Tests unitarios para `simulate_credit` con categoría + product_id (lookup en InterestRate, fallbacks)
3. Tests de integración para `AnalyticsService` (6 endpoints con DB poblada)
4. Tests unitarios para `ToolBridge` (get_openai_tools, execute_tool con hidden params)
5. Tests de integración para `SecurityMiddleware` (headers, rate limit, CSP, HSTS)
6. Tests para `InterestRate` queries (crear, buscar por categoría+producto)
7. Tests para `get_customer` con `categoria_afiliacion`
8. Tests para `create_application` con `modalidad_pago`

### Out of Scope

- Frontend tests (vitest no instalado)
- Tests de integración real con LLM (mockeado como ahora)
- Tests end-to-end

## Capabilities

No cambian capacidades existentes — test suite pura sin cambios de spec. No se agregan ni modifican capabilities.

### New Capabilities

None — pure test addition, no spec-level change.

### Modified Capabilities

None.

## Approach

Seguir el patrón existente: `asyncio_mode=auto`, in-memory SQLite vía `conftest.py` fixtures, `monkeypatch` para `async_session_maker`. Tests de integración con `TestClient` + DB poblada vía fixtures. Tests unitarios puros sin DB.

| Área | Patrón | DB? |
|------|--------|-----|
| `_calcular_categoria` | Test directo, función pura | No |
| `simulate_credit` + categoría | monkeypatch session_maker + seed InterestRate | Sí |
| `AnalyticsService` | Instanciar con session_maker, poblar DB | Sí |
| `ToolBridge` | Mock FastMCP, verificar schemas y ejecución | No |
| `SecurityMiddleware` | TestClient con app, verificar headers/429 | No |
| `InterestRate` | CRUD directo con db_session | Sí |
| `get_customer` + categoria | domain_db_maker + verificar output | Sí |
| `create_application` + modalidad | domain_db_maker + verificar Credit row | Sí |

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/tests/test_domain_tools.py` | Modified | +tests: _calcular_categoria, simulate_credit rate lookup, get_customer categoria, create_application modalidad |
| `backend/tests/test_analytics.py` | New | AnalyticsService integration tests (6 endpoints) |
| `backend/tests/test_tool_bridge.py` | New | ToolBridge unit tests |
| `backend/tests/test_security_middleware.py` | New | SecurityMiddleware integration tests |
| `backend/tests/test_interest_rate.py` | New | InterestRate model CRUD tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| InterestRate seed requerido para tests | Low | Crear fixture que inserta rows de tasa en setUp |
| AnalyticsService depende de pandas + SQL raw | Low | Tests con DB poblada verifican cada endpoint |
| Rate limiter en test_client puede flakear | Low | Usar RateLimiter propio con window grande o mockear time |

## Rollback Plan

Revertir los archivos de test nuevos (`test_analytics.py`, `test_tool_bridge.py`, `test_security_middleware.py`, `test_interest_rate.py`) y revertir cambios en `test_domain_tools.py`. Ningún código de producción se modifica, rollback es zero-risk.

## Dependencies

Ninguna — tests corren sobre código existente.

## Success Criteria

- [ ] Mínimo 20 tests nuevos (blanco: 24)
- [ ] Todos los tests existentes siguen pasando
- [ ] `_calcular_categoria` cubre: None, 0, 2 SMMLV, 4 SMMLV, >4 SMMLV
- [ ] `simulate_credit` usa tasa desde InterestRate cuando se pasa product_id
- [ ] `AnalyticsService` retorna estructura correcta para cada endpoint con DB poblada
- [ ] `ToolBridge` oculta session_id del schema y lo inyecta al ejecutar
- [ ] `SecurityMiddleware` agrega headers de seguridad y rate-limita a 429
- [ ] `get_customer` incluye `categoria_afiliacion` en output
- [ ] `create_application` persiste `modalidad_pago` en Credit
