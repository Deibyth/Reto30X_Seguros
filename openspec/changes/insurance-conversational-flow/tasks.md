# Tasks: Insurance Conversational Flow

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~750 (150 + 250 + 200 + 150) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (data+form) → PR 2 (engine+tools) → PR 3 (wiring) → PR 4 (tests) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Data models + InsuranceFormSchema | PR 1 | `pytest tests/test_insurance_schema.py -x -q` | `pytest tests/test_insurance_schema.py -x -q` | Revert session.py, insurance.py, delete insurance_schema.py |
| 2 | Recommendation engine + 3 MCP tools | PR 2 | `pytest tests/test_recommendation_engine.py -x -q` | `pytest tests/test_recommendation_engine.py -x -q` | Revert domain_tools.py, delete recommendation_engine.py |
| 3 | State machine + prompt + flow wiring | PR 3 | `pytest tests/test_chat.py -x -q` | Full integration: `pytest backend/tests/ -x -q` | Revert chat.py, tool_bridge.py; delete insurance_system.md |
| 4 | Integration + regression tests | PR 4 | `pytest tests/test_insurance_flow.py -x -q` | `pytest backend/tests/ -x -q` | Delete test_insurance_flow.py |

## Phase 1: Data Models + InsuranceFormSchema (~150 lines)

- [x] 1.1 Add `insurance_profile: Mapped[dict \| None]` JSON column (nullable, default=None) to `backend/app/models/session.py`
- [x] 1.2 Add `insurance_category: Mapped[str \| None]` String(50) column (nullable, default=None) to `backend/app/models/insurance.py`
- [x] 1.3 Create `backend/app/schemas/insurance_schema.py` — `FormField`/`FormSeccion` classes, `InsuranceFormSchema` with 4 sections (Datos del Tomador, Cobertura, Beneficiario, Pago), `PRODUCT_FIELD_VARIANTS` dict, `to_prompt_text()`, `campos_requeridos()`
- [x] 1.4 Write `backend/tests/test_insurance_schema.py` — 21 tests passing (16 unit + 5 async/integration)

**Verify**: `pytest tests/test_insurance_schema.py -x -q` passes; `to_prompt_text()` contains all 4 section headers; existing `pytest tests/test_credit_form.py -x -q` still green.

## Phase 2: Recommendation Engine + MCP Tools (~250 lines)

- [x] 2.1 Create `backend/app/services/recommendation_engine.py` — `PRODUCTS` catalog (7 products), `RULES` list (7 rules), `match_products(profile)`, `quote_product(product_id, profile, coverage_level)`, `COVERAGE_MULTIPLIERS`, `AGE_MULTIPLIER`, `BENEFICIARY_MULTIPLIER`
- [x] 2.2 Add `recommend_insurance(profile: dict) -> str` MCP tool to `backend/app/tools/domain_tools.py` — calls `match_products()`, formats result
- [x] 2.3 Add `quote_insurance(product_id: str, profile: dict, coverage_level: str = "estandar") -> str` MCP tool to `backend/app/tools/domain_tools.py` — calls `quote_product()`, formats result
- [x] 2.4 Add `create_policy(customer_id: str, form_data: dict, insurance_id: str) -> str` MCP tool to `backend/app/tools/domain_tools.py` — atomic `Application(tipo="seguro")` + `Policy` creation, validates `acepta_terminos`, `numero_poliza` format
- [x] 2.5 Write `backend/tests/test_recommendation_engine.py` — all 7 rules match correctly, empty profile returns `[]`, multi-match sorted, `quote_product()` multipliers (coverage, age, beneficiaries), unknown product returns error, invalid coverage returns error

**Verify**: `pytest tests/test_recommendation_engine.py -x -q` passes; familia+hijos→Vida, empty profile→`[]`, quote for edad=35 returns correct formula.

## Phase 3: State Machine + System Prompt + Flow Wiring (~200 lines)

- [x] 3.1 Add `INSURANCE_STATES` constant and `_is_insurance_state()` to `backend/app/services/chat.py`; extend `_update_session_state()` with insurance transitions (perfilando→recomendando via recommend_insurance, recomendando→cotizando via quote_insurance, cotizando→recopilando_datos_seguro via first save_form_field, cotizando→recomendando, recopilando_datos_seguro→completado_seguro via create_policy)
- [x] 3.2 Add optional `domain: str | None` filter parameter to `ToolBridge.get_openai_tools()` in `backend/app/services/tool_bridge.py` — filters tool cache by domain tag
- [x] 3.3 Create `backend/app/domain/prompts/insurance_system.md` — insurance prompt fragment (segment context, product catalog, profiling guidance, recommendation rules, "I don't know" handling)
- [x] 3.4 Create `backend/data/colsubsidio_segments.csv` — offline segment analysis (columns: segment_name, age_range, income_range, typical_family_size, common_products, pain_points)
- [x] 3.5 Inject insurance fragment in `ChatService._build_system_prompt()` — append when `_is_insurance_state()`, load from insurance_system.md or constant
- [x] 3.6 Wire domain tool filtering in `ChatService.process_message()` — pass domain filter to `get_openai_tools()` based on session state; make `_compute_completitud_pct()` domain-aware (uses InsuranceFormSchema in insurance states)

**Verify**: `pytest tests/test_chat.py -x -q` passes; insurance states route tools correctly; credit states never see insurance fragment.

## Phase 4: Tests (~150 lines)

- [x] 4.1 Write `backend/tests/test_insurance_flow.py` — integration tests: full happy path (profile→recommend→quote→collect→create_policy), quote for unknown product errors, terms declined aborts policy, empty profile returns empty list
- [x] 4.2 Extend `backend/tests/test_chat.py` — `TestBuildSystemPrompt` verifies insurance fragment injected in perfilando/recomendando states, absent in recopilando_datos state; `_update_session_state` transition tests for insurance states
- [x] 4.3 Extend `backend/tests/test_tool_bridge.py` — `get_openai_tools(domain="insurance")` returns only insurance tools, `domain="credit"` returns only credit tools, `domain=None` returns all
- [x] 4.4 Run full test suite — all 199 tests pass with zero regressions (187 existing + 12 new)

**Verify**: `pytest backend/tests/ -x -q` passes (all ~15 test files green); insurance flow integration test covers full happy path end-to-end.
