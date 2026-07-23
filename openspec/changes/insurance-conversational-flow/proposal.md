# Proposal: Insurance Conversational Flow

## Intent

Insurance requires a commercial advisor today — no advisor, no sale. Credit already works conversationally via Anna. Extend the same architecture (ChatService, ToolBridge, FormSchema, state machine) to create a complete conversational insurance purchase flow, taking a member from "I don't know what I need" to "I'm now insured" without human intervention.

## Scope

### In Scope
- Insurance-specific FormSchema (policy data fields)
- Recommendation rules engine (demographic profiling → product match)
- `recommend_insurance()`, `quote_insurance()`, `create_policy()` MCP tools
- Insurance-specific session states (profiling → recommending → quoting → collecting_data → completado)
- Conversational profiling: Anna engages naturally, profile emerges from dialogue
- CSV population analysis used offline for segment empathy only (not at inference time)
- Policy data collected at closing (no document/cédula lookup during profiling)

### Out of Scope
- Real payment gateway integration (stubbed quote/issue flow)
- Real insurer API integration (internal policy issuance only)
- Document upload for insurance claims
- Multi-insurer comparison shopping
- ML-based recommendation (rule-based given sparse consumption data)

## Capabilities

### New Capabilities
- `insurance-form-schema`: InsuranceFormSchema definition — policy holder data, coverage selections, beneficiary info, payment method
- `insurance-recommendation`: Rule-based engine mapping demographic profile (family composition, age range, income level) to Colsubsidio insurance products. Tools: `recommend_insurance()`, `quote_insurance()`
- `insurance-conversational-flow`: State machine driving profiling → recommendation → quoting → data collection → policy creation flow. Includes `create_policy()` tool

### Modified Capabilities
- `ai-tool-loop`: Add insurance tools to ToolBridge registrations
- `form-data-collection`: Generalize FormSchema loader to support credit AND insurance schemas
- `data-models`: Add `insurance_profile` JSON field to Session; add `insurance_category` field to Insurance model
- `chat-sessions`: Add insurance states to session state machine (`perfilando`, `recomendando`, `cotizando`, `recopilando_datos_seguro`, `completado_seguro`)

## Approach

Extend the existing two-phase AI loop with insurance-specific components:

1. **Conversational profiling**: Anna's system prompt includes demographic segment knowledge (from offline CSV analysis). She asks natural questions about family, home, pets, mobility — NOT "what insurance do you want". Profile is saved to `session.insurance_profile` JSON.
2. **Recommendation**: When profile is sufficient, Anna calls `recommend_insurance(profile)` — the rule engine matches profile to products. She presents options naturally with segment context ("many families like yours choose...").
3. **Quoting & adjusting**: User asks about coverage, price. Anna calls `quote_insurance(product_id, profile)` for personalized quote. User can adjust coverage, compare options.
4. **Data collection + policy creation**: On user intent to buy, Anna loads InsuranceFormSchema and collects policy fields progressively (same pattern as credit). On confirmation, `create_policy()` creates Application + Policy atomically.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/services/recommendation_engine.py` | New | Rule-based insurance recommendation |
| `backend/app/services/insurance_schema.py` | New | InsuranceFormSchema definition |
| `backend/app/services/tool_bridge.py` | Modified | Register insurance tools |
| `backend/app/services/chat_service.py` | Modified | Insurance-aware state routing |
| `backend/app/models/insurance.py` | Modified | Add `insurance_category` column |
| `backend/app/models/session.py` | Modified | Add `insurance_profile` JSON field |
| `backend/app/domain/tools/insurance_tools.py` | New | recommend, quote, create_policy tools |
| `backend/app/domain/prompts/insurance_system.md` | New | Insurance-specific system prompt fragment |
| `backend/data/colsubsidio_segments.csv` | New | Offline CSV segment analysis |
| `backend/tests/test_insurance_flow.py` | New | Integration tests for insurance flow |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| CSV real names (PII) exposed in code | Low | CSV used offline only; never loaded at runtime. Store segment aggregates, not raw rows |
| No ID for policy binding | Med | Generate internal UUID on first contact; policy bound to session customer record |
| Sparse consumption data makes profiling weak | Med | Rule-based + conversational empathy; refine rules as more data comes in |
| Insurance products more nuanced than credit | Med | Limit to 4 product families initially; expand coverage later |
| LLM recommends wrong product | Low-Med | Recommendation is tool-call-gated (LLM cannot invent products); rules engine is deterministic |

## Rollback Plan

Revert the `chat_service.py` routing to ignore insurance states — credit flow continues uninterrupted. Remove insurance tools from ToolBridge registration. Insurance-specific models and tools remain in code (inert) for future reactivation. No data migration needed since insurance sessions will not exist in production before GA.

## Dependencies

- Existing `ChatService`, `ToolBridge`, `FormSchema`, session state machine — all credit-land infrastructure reused
- Colsubsidio insurance product catalog (from website) for recommendation rules
- CSV population dataset (offline analysis only)

## Success Criteria

- [ ] Anna can profile a member conversationally and recommend the correct Colsubsidio insurance product
- [ ] Member can adjust coverage, get a quote, and ask questions before committing
- [ ] Policy data collected progressively and `create_policy()` issues a valid Policy record
- [ ] Full happy path works end-to-end in a single chat session
- [ ] Existing credit flow is not broken (all existing tests pass)
