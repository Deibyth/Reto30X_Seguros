# Design: Backend Test Coverage

## Technical Approach

Add 25+ tests across 5 test files following existing patterns (pytest `asyncio_mode=auto`, in-memory SQLite via `conftest.py` fixtures, `monkeypatch` for `async_session_maker` overrides, `TestClient` for integration). Zero production code changes — pure test additions.

| File | Tests | Pattern | DB? |
|------|-------|---------|-----|
| `test_domain_tools.py` | +6 (categoria, categoria lookup, modalidad) | monkeypatch + domain_db_maker | Yes |
| `test_analytics.py` | +7 (6 endpoints + 503) | TestClient + pre-seeded DB fixture | Yes |
| `test_tool_bridge.py` | +5 (schemas, hidden params, execution) | Mock FastMCP directly | No |
| `test_security_middleware.py` | +5 (headers, CSP, rate-limit) | TestClient direct | No |
| `test_interest_rate.py` | +3 (create, query by cat+prod) | db_session fixture | Yes |

## Architecture Decisions

### Decision: Seeded DB fixture for AnalyticsService

| Option | Tradeoff |
|--------|----------|
| `test_client` with app startup | App creates real engine — can't control seed data |
| **Custom fixture** (chosen) | Create engine + seed Sessions, Applications, Credits, Customers, Conversations — full control |
| Mock AnalyticsService | Tests the router pass-through, not the SQL/aggregation logic |

**Rationale**: AnalyticsService runs raw SQL aggregation. A pre-seeded in-memory DB proves each endpoint returns correct structure and counts. Mocking would bypass the logic we need to validate.

### Decision: ToolBridge mocks FastMCP directly

| Option | Tradeoff |
|--------|----------|
| Real FastMCP with `mcp.list_tools()` | FastMCP reads from module-level registry — coupling to real tool registration |
| **Mock FastMCP instance** (chosen) | `MagicMock(spec=FastMCP)` with controlled `list_tools()` / `call_tool()` returns — isolated test |
| Acceptance/end-to-end | Requires running MCP server — out of scope |

**Rationale**: ToolBridge logic is schema transformation (strip hidden params + inject at execution). Mocking FastMCP at the boundary tests exactly this transformation without coupling to domain_tools registration.

### Decision: Rate-limiter tests with dedicated config

| Option | Tradeoff |
|--------|----------|
| Reuse `test_client` (default: 15 req/min) | Need to send 16+ requests — slow and flaky |
| **Create test_client with low limit** (chosen) | `Settings(chat_rate_limit_per_minute=2)` — 3 requests trigger 429 fast |
| Patch `time.time` | Fragile, needs internal RateLimiter knowledge |

**Rationale**: Low limit makes rate-limit deterministic (3 requests → 429 on #3). No time mocking needed.

### Decision: Add to `test_domain_tools.py` vs new file for categoria/domain additions

| Option | Tradeoff |
|--------|----------|
| **Same file** (chosen) | Follows existing pattern — all domain_tools tests together |
| New file | More files, same monkeypatch fixture reuse |

**Rationale**: `_calcular_categoria`, `get_customer` categoria, `create_application` modalidad, and `simulate_credit` product_id are all domain_tools — they belong in the same test file.

## Data Flow

```
test_analytics.py:
  Pre-seed fixture (engine + session_maker + seed data)
    ├── Sessions(3): activa=1, completado=1, abandonado=1
    ├── Customers(3): salarios variados, contratos variados
    ├── Applications(3): estados variados
    ├── Credits(3): montos, plazos, destinos variados
    └── Conversations(10): linked to sessions
        │
  TestClient → /analytics/summary → AnalyticsService(session_maker)
        │                              └── raw SQL + pandas → dict
  Assert structure and key values

test_tool_bridge.py:
  Mock FastMCP
    ├── mock.list_tools → [Tool(name="save_form_field", parameters={...session_id...}),
    │                       Tool(name="get_products", parameters={...})]
    │
  ToolBridge(mock_mcp) → get_openai_tools()
    └── Assert session_id stripped from save_form_field schema
    └── Assert session_id NOT in get_products schema
    └── execute_tool("save_form_field", {...}) auto-injects session_id

test_security_middleware.py:
  TestClient(low_rate_limit) → GET /health (whitelisted, passes)
  TestClient(low_rate_limit) → POST /chat × 3 → 429 on third
  TestClient → GET /health → assert headers present
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/tests/test_domain_tools.py` | Modify | +6 tests: categoria bounds, categoria lookup, modalidad_pago |
| `backend/tests/test_analytics.py` | Create | 7 tests: 6 AnalyticsService endpoints + 503 unavailable |
| `backend/tests/test_tool_bridge.py` | Create | 5 tests: schema transformation, hidden params, execution |
| `backend/tests/test_security_middleware.py` | Create | 5 tests: headers, CSP, HSTS, rate-limit, health whitelist |
| `backend/tests/test_interest_rate.py` | Create | 3 tests: create, query by categoria+product, query by cat alone |

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Unit (pure) | `_calcular_categoria` (5 cases) | Direct function call, no DB |
| Unit (state) | `ToolBridge` (5 cases) | Mock FastMCP, assert schema transforms |
| Integration | `InterestRate` CRUD (3 cases) | `db_session` fixture, SQLAlchemy queries |
| Integration | `AnalyticsService` (7 cases) | Pre-seeded DB fixture, TestClient |
| Integration | `SecurityMiddleware` (5 cases) | TestClient with dedicated low-limit config |
| Integration | domain_tools additions (3 cases) | `domain_db_maker` + monkeypatch pattern |

### Specific Test Cases

**`_calcular_categoria`** (pure — 5 tests):
- `None` → `"A"`
- `0` → `"A"`
- `1_000_000` (≤2 SMMLV = 3_501_810) → `"A"`
- `4_000_000` (≤4 SMMLV = 7_003_620) → `"B"`
- `10_000_000` (>4 SMMLV) → `"C"`

**`simulate_credit` with product_id** (1 test):
- `domain_db_maker` + seed InterestRate(row A, credito-prod, libranza, 15-18%)
- Call `simulate_credit(5_000_000, 12, categoria="A", modalidad="libranza", product_id="credito-prod")`
- Assert `"15.0%"` or `"16.5%"` in output (midpoint)

**`get_customer` with `categoria_afiliacion`** (1 test):
- Add customer with explicit `categoria_afiliacion="B"` to domain_db_maker (or use existing)
- Call `get_customer(documento_identidad=...)`
- Assert `"Categoría de afiliación: B"` in output

**`create_application` with `modalidad_pago`** (1 test):
- Call `create_application` with `form_data` containing `modalidad_pago="libranza"`
- Query Credit row by the returned app ID
- Assert `credit.modalidad_pago == "libranza"`

**ToolBridge** (5 tests):
- `get_openai_tools` returns list
- `get_openai_tools` strips `session_id` from save_form_field params
- `get_openai_tools` does NOT strip session_id from other tools (not in HIDDEN_PARAMS)
- `execute_tool` injects `session_id` for save_form_field when `current_session_id` is set
- `execute_tool` raises `ValueError` for unknown tool name

**SecurityMiddleware** (5 tests):
- All responses have `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy` headers
- All responses have `Content-Security-Policy` (CSP_DEV in testing)
- `Server` header is removed from responses
- Rate limit: 3rd request to `/chat` returns 429 (with `Retry-After: 60`)
- `/health` is whitelisted — never rate-limited even after many requests

**InterestRate** (3 tests):
- Create an InterestRate row, assert it has UUID id
- Query by `categoria + product_id + modalidad_pago + activo`, get the active rate
- Query by nonexistent combination returns `None`

**AnalyticsService** (7 tests):
- `GET /analytics/summary` returns 503 when service unavailable (echo_client)
- `GET /analytics/pipeline` returns correct counts (total_sessions, active, completed, applications)
- `GET /analytics/trends` returns list of daily records
- `GET /analytics/customers` returns salary distribution, contract types, averages
- `GET /analytics/credits` returns avg_amount, destinos, amount_ranges
- `GET /analytics/efficiency` returns avg_messages, total_conversations, field counts
- `GET /analytics/summary` returns compound dict with all 5 sub-sections

### Data Seed Pattern for Analytics

```python
@pytest_asyncio.fixture
async def analytics_db():
    """Engine + session_maker seeded with analytics demo data."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as session:
        # 3 sessions: active, completed, abandoned
        session.add_all([...])
        # 3 customers: high salary, low salary, no salary
        session.add_all([...])
        # 3 applications: iniciada, completada, rechazada
        session.add_all([...])
        # 3 credits: different amounts, destinos
        session.add_all([...])
        # 10 conversations across sessions
        session.add_all([...])
        await session.commit()

    # Attach analytics_service to a TestClient
    svc = AnalyticsService(maker)
    settings = Settings(database_url="sqlite+aiosqlite://", ...)
    app = create_app(settings=settings)
    app.state.analytics_service = svc
    # Override the lifespan-created engine by attaching our engine
    # Or simply use TestClient(app) which won't trigger full lifespan

    with TestClient(app) as client:
        yield client

    await engine.dispose()
```

**Alternative**: Don't wire through `create_app`. Test `AnalyticsService` directly:

```python
@pytest.mark.asyncio
async def test_pipeline_summary(analytics_db_maker):
    svc = AnalyticsService(analytics_db_maker)
    result = await svc.get_pipeline_summary()
    assert result["total_sessions"] == 3
```

This avoids app lifecycle complexity. Both approaches documented — prefer direct service testing for unit-level assertion and TestClient for integration-level assertion.

## Threat Matrix

**N/A** — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. Pure test additions with zero production code changes.

## Migration / Rollout

No migration required. Tests run independently alongside existing suite. Rollback is `git checkout` on the new/modified test files — zero risk.

## Open Questions

- **None** — all decisions scoped, patterns well-established in existing tests.
