# Insurance Conversational Flow Specification

> **Capability:** New — `insurance-conversational-flow`
> **Change:** `insurance-conversational-flow`
> **Date:** 2026-07-22

## Purpose

Define the insurance-specific state machine, system prompt fragment, and `create_policy()` tool that together enable a member to go from "I need insurance" to being insured, all within a single conversational session with Anna. Reuses the existing ChatService two-phase loop architecture.

## Requirements

### Requirement: Insurance state machine

The system SHALL define five insurance-specific states for `session.estado_actual`. The valid state machine SHALL be:

```
inicio ──> perfilando ──> recomendando ──> cotizando ──> recopilando_datos_seguro ──> completado_seguro
                     ↘─────────────↗ (user says "no me interesa")
```

| State | Description | Next States |
|-------|-------------|-------------|
| `perfilando` | Anna asks natural questions about family, home, mobility, pets, travel to build `insurance_profile` | `recomendando` (profile sufficient) |
| `recomendando` | `recommend_insurance()` called; Anna presents options with segment context | `cotizando`, back to `perfilando` (user unsure) |
| `cotizando` | `quote_insurance()` called for selected product; user asks about coverage, price, adjusts | `recopilando_datos_seguro` (buys), `perfilando` (wants different product) |
| `recopilando_datos_seguro` | `InsuranceFormSchema` fields collected progressively | `completado_seguro` (confirmed) |
| `completado_seguro` | Policy issued; Anna confirms and offers next steps (return to `inicio`) | `inicio` |

#### Scenario: Full happy path
- GIVEN a session starting at `estado_actual="inicio"`
- WHEN the user says "necesito un seguro"
- THEN the system transitions `inicio` → `perfilando`
- AND after sufficient profiling, transitions `perfilando` → `recomendando`
- AND after product selection, transitions `recomendando` → `cotizando`
- AND after buy intent, transitions `cotizando` → `recopilando_datos_seguro`
- AND after data collection + confirmation, transitions → `completado_seguro`

#### Scenario: User declines recommendation
- GIVEN a session at `estado_actual="recomendando"`
- WHEN the user says "no me interesa ninguno"
- THEN the system MAY transition back to `perfilando` to refine the profile
- OR transition to `inicio` if the user explicitly leaves

#### Scenario: User wants a different product
- GIVEN a session at `estado_actual="cotizando"`
- WHEN the user says "quiero ver otro producto"
- THEN the system SHALL transition `cotizando` → `recomendando`
- AND Anna SHALL present other recommendations

### Requirement: System prompt fragment

The `_build_system_prompt` method SHALL append an insurance-specific fragment when the session enters insurance states. The fragment SHALL include:

1. **Segment context**: Brief demographic descriptions from the offline CSV analysis (e.g., "Many families in this segment choose Vida + Hogar combo")
2. **Product catalog**: Current Colsubsidio products by family (Personal, Hogar, Movilidad, Mascotas, Crédito)
3. **Recommendation guidelines**: "Recommend 1-3 products max. Never invent products. Call `recommend_insurance()` before suggesting."
4. **Profiling guidance**: "Ask natural questions. Do NOT ask 'what insurance do you want'. Ask about their life: family, home, pets, mobility, travel."
5. **Price anchoring**: "Share approximate price ranges conversationally. Call `quote_insurance()` for accurate quotes."

#### Scenario: Insurance fragment injected on profiling state
- GIVEN a session transitioning to `estado_actual="perfilando"`
- WHEN `_build_system_prompt()` is called
- THEN the prompt SHALL contain an insurance section with product families and profiling guidance

#### Scenario: Fragment absent in credit-only states
- GIVEN a session at `estado_actual="recopilando_datos"` (credit)
- WHEN `_build_system_prompt()` is called
- THEN the prompt SHALL NOT contain the insurance section

### Requirement: `create_policy()` tool

The tool SHALL atomically create an `Application` (tipo="seguro") and a `Policy` record from the collected `campos_diligenciados`. Signature: `create_policy(customer_id: str, form_data: dict, insurance_id: str) -> dict`.

Return SHALL include: `application_id`, `policy_id`, `numero_poliza` (auto-generated), `estado` ("activo"), `fecha_inicio`.

The tool SHALL validate:
- `form_data.acepta_terminos` MUST be `true`
- All required `InsuranceFormSchema` fields MUST be present
- `insurance_id` MUST reference an existing Insurance record

#### Scenario: Policy created successfully
- GIVEN a customer, validated form_data, and a valid insurance_id
- WHEN `create_policy(customer_id, form_data, insurance_id)` is called
- THEN an `Application(tipo="seguro")` row is created
- AND a `Policy` row is created linked to it
- AND `numero_poliza` follows format `POL-{UUID8}`
- AND `session.estado_actual` becomes `"completado_seguro"`

#### Scenario: Terms not accepted
- GIVEN `form_data.acepta_terminos` is `false` or missing
- WHEN `create_policy()` is called
- THEN the tool SHALL return `{"error": "terms_not_accepted"}`
- AND no Application or Policy rows are created

#### Scenario: Invalid insurance_id
- GIVEN an `insurance_id` that does not exist in the database
- WHEN `create_policy()` is called
- THEN the tool SHALL return `{"error": "invalid_insurance_id"}`
- AND no rows are created

### Requirement: Credit flow isolation

Insurance states, tools, and schemas SHALL NOT interfere with the existing credit flow. A session in credit states (`recopilando_datos`, `evaluando`, `ofreciendo_producto`) SHALL remain unaware of insurance logic. A session in insurance states SHALL remain unaware of credit logic beyond the shared `inicio` state.

#### Scenario: Credit session ignores insurance
- GIVEN a session at `estado_actual="recopilando_datos"` (credit)
- WHEN the user asks "y qué seguros tenés?"
- THEN the AI MAY acknowledge the question briefly
- BUT SHALL NOT shift to insurance profiling
- AND `estado_actual` SHALL remain in credit flow

#### Scenario: Insurance session ignores credit
- GIVEN a session at `estado_actual="perfilando"`
- WHEN the user asks "y un crédito?"
- THEN the AI MAY acknowledge briefly
- BUT SHALL remain in `perfilando`
- AND insurance tools remain active

## Dependencies

- `insurance-form-schema` — InsuranceFormSchema for data collection
- `insurance-recommendation` — recommend_insurance, quote_insurance tools
- `ai-tool-loop` — ToolBridge execution of insurance tools
- `chat-sessions` — session.estado_actual, session.insurance_profile
- `data-models` — Application, Policy, Customer, Insurance models
- `form-data-collection` — Progressive collection pattern reused
