# Design: Insurance Conversational Flow

## Technical Approach

Extend the existing two-phase AI tool loop (ChatService + ToolBridge + FormSchema) with insurance-specific components running in parallel to the credit flow. Insurance adds 5 new session states, 3 new MCP tools, a rule-based recommendation engine, an InsuranceFormSchema, and a dynamic system prompt fragment — all reusing the same ChatService architecture. Credit flow remains untouched; session state determines which domain is active.

**Specs mapped**: `insurance-form-schema`, `insurance-recommendation`, `insurance-conversational-flow`, plus delta specs for `ai-tool-loop`, `form-data-collection`, `data-models`, `chat-sessions`.

---

## Architecture Decisions

### Decision: Recommendation engine — pure functions module, not a class

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Pydantic service class | OOP overhead for stateless logic | ❌ Rejected |
| **Pure functions in module** | Testable, no deps, follows credit_form.py pattern | ✅ **Chosen** |
| SQL-based rules | Requires schema changes, less transparent | ❌ Rejected |

The engine lives in `backend/app/services/recommendation_engine.py` as exported functions `match_products(profile)`, `quote_product(product_id, profile, coverage_level)`, and a `PRODUCTS` catalog dict. No DB reads at inference time — product data is hardcoded from the Colsubsidio catalog.

### Decision: InsuranceFormSchema — separate file, same pattern as credit

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Merge into FormSchema | Conditional sections make credit schema fragile | ❌ Rejected |
| **Separate `insurance_schema.py`** | Clean isolation, follows existing pattern | ✅ **Chosen** |
| YAML/JSON external file | Schema IS code, versioning with app logic | ❌ Rejected |

Matches the `FormField`/`FormSeccion` classes from `credit_form.py` but uses its own field list with product-specific field variants (conditional beneficiary fields for Vida, different `suma_asegurada` ranges per product).

### Decision: Tool injection filtered by domain (credit vs insurance)

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Always send all tools | Wastes tokens, confuses model | ❌ Rejected |
| **Filter by session state domain** | Clean separation, optimized context | ✅ **Chosen** |
| Separate MCP instances | Unnecessary complexity | ❌ Rejected |

`ToolBridge.get_openai_tools()` gains an optional `domain` filter. `ChatService._build_system_prompt()` determines domain from `session.estado_actual` and passes the filter. Insurance states (`perfilando`, `recomendando`, `cotizando`, `recopilando_datos_seguro`) expose insurance tools only; credit states expose credit tools only; `inicio` exposes both.

### Decision: Profile sufficiency — minimum 1 attribute triggers recommendation

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Require N attributes | May never trigger for quiet users | ❌ Rejected |
| **1 confirmed attribute** + AI judgment | Lets Anna decide naturally | ✅ **Chosen** |
| Always recommend at 3+ | Over-collection, friction | ❌ Rejected |

No hardcoded threshold in the backend. The AI decides when profiling is sufficient — the system prompt instructs: "Once you have at least one clear attribute (family, home, pet, vehicle, travel, debt) and the user seems engaged, call `recommend_insurance()` to present options." The AI can also say "I have enough info to give you some recommendations" and transition state.

---

## Data Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                          ChatService                                  │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────────────┐   │
│  │_build_system │──>│ Phase 1 AI   │──>│ Phase 2 AI (with tool    │   │
│  │_prompt()     │   │ call (tools) │   │ results appended)        │   │
│  └──────┬──────┘   └──────┬───────┘   └────────────┬─────────────┘   │
│         │                 │                         │                  │
│         │           ┌─────▼──────────┐              │                  │
│         │           │ ToolBridge      │              │                  │
│         │           │ .execute_tool() │              │                  │
│         │           └─────┬──────────┘              │                  │
│         │                 │                          │                  │
│         │    ┌────────────┼──────────────┐          │                  │
│         │    │            │              │          │                  │
│         │    ▼            ▼              ▼          │                  │
│         │  Credit      Insurance     Insurance     │                  │
│         │  Tools       Recom.        Schema        │                  │
│         │  (existing)  Engine        Tools         │                  │
│         │              (new)         (new)         │                  │
│         │                                           │                  │
│         │    session.insurance_profile (JSON)        │                  │
│         │    session.estado_actual (insurance/credit)│                  │
│         ▼                                           ▼                  │
│    prompt = base + insurance                    prompt = base + credit │
│    fragment (perfilando →                     fragment (recopilando   │
│    completado_seguro)                          _datos → completado)   │
└──────────────────────────────────────────────────────────────────────┘
```

### Domain routing logic:

```
session.estado_actual
  ├── "inicio" → AI detects intent → credit or insurance?
  │     ├── intent: solicitar_seguro → estado_actual = "perfilando"
  │     └── intent: solicitar_credito → estado_actual = "recopilando_datos"
  │
  ├── credit states: recopilando_datos, evaluando, ofreciendo_producto, completado
  │     └── Credit tools + Credit FormSchema
  │
  └── insurance states: perfilando, recomendando, cotizando, recopilando_datos_seguro, completado_seguro
        └── Insurance tools + InsuranceFormSchema
```

---

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/services/recommendation_engine.py` | Create | Pure functions: `match_products()`, `quote_product()`, product catalog |
| `backend/app/services/insurance_schema.py` | Create | `InsuranceFormSchema` — policy fields, product-specific variants, `to_prompt_text()` |
| `backend/app/domain/prompts/insurance_system.md` | Create | Insurance system prompt fragment for Anna (segment context, catalog, guidelines) |
| `backend/app/tools/domain_tools.py` | Modify | Add `recommend_insurance()`, `quote_insurance()`, `create_policy()` MCP tools |
| `backend/app/services/chat.py` | Modify | Insurance-aware `_build_system_prompt()`, `_update_session_state()` with insurance states, domain tool filtering |
| `backend/app/services/tool_bridge.py` | Modify | Add `domain` filter support to `get_openai_tools()` |
| `backend/app/models/insurance.py` | Modify | Add `insurance_category` column (String, nullable) |
| `backend/app/models/session.py` | Modify | Add `insurance_profile` JSON column |
| `backend/data/colsubsidio_segments.csv` | Create | Offline segment analysis (aggregates only — never loaded at runtime) |
| `backend/tests/test_insurance_flow.py` | Create | Integration tests for full insurance flow |
| `backend/tests/test_recommendation_engine.py` | Create | Unit tests for rule engine and quote calculation |
| `backend/tests/test_insurance_schema.py` | Create | Unit tests for InsuranceFormSchema |

---

## 1. Architecture Overview

### Component relationships

```
         ┌─────────────────────────────────────────────────────────────┐
         │                      FastMCP Server                           │
         │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
         │  │ credit tools │  │ insurance    │  │ insurance_form   │   │
         │  │ (existing)   │  │_recom tools  │  │ tools (new)      │   │
         │  │ get_products │  │ recommend    │  │ save_form_field  │   │
         │  │ get_customer │  │ quote        │  │ create_policy    │   │
         │  │ simulate     │  │_insurance    │  │                  │   │
         │  │ check_elig   │  │              │  │                  │   │
         │  │ create_appl  │  │              │  │                  │   │
         │  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘   │
         └─────────┼─────────────────┼───────────────────┼──────────────┘
                   │                 │                   │
                   ▼                 ▼                   ▼
         ┌─────────────────────────────────────────────────────────────┐
         │                    ToolBridge                                 │
         │  - get_openai_tools(domain=None) → filtered schemas          │
         │  - execute_tool(name, args) → injects hidden params          │
         │  - Domain filter: credit | insurance | None (all)            │
         └─────────────────────────┬───────────────────────────────────┘
                                   │
                                   ▼
         ┌─────────────────────────────────────────────────────────────┐
         │                    ChatService                                │
         │  - process_message() — two-phase loop                        │
         │  - _build_system_prompt(session) → domain-aware prompt       │
         │  - _update_session_state() → credit OR insurance transitions │
         │  - Domain routing via session.estado_actual                  │
         └─────────────────────────────────────────────────────────────┘
```

### Shared vs Insurance-specific

| Component | Domain | Notes |
|-----------|--------|-------|
| `ChatService` | Shared | Routes credit/insurance by state |
| `ToolBridge` | Shared | Domain filtering added |
| `AIClient` | Shared | Unchanged |
| `Session` model | Shared | New `insurance_profile` field |
| `FormSchema` (credit) | Credit only | Unchanged |
| `InsuranceFormSchema` | Insurance only | New, same pattern |
| `recommendation_engine` | Insurance only | New, pure functions |
| Insurance tools | Insurance only | New MCP tools |
| Credit tools | Credit only | Unchanged |

---

## 2. Recommendation Engine Design

**File**: `backend/app/services/recommendation_engine.py`

### Product catalog (in-memory dict — no DB dependency)

```python
PRODUCTS: dict[str, dict] = {
    "vida": {
        "nombre": "Seguro de Vida",
        "descripcion": "Respaldo económico para beneficiarios en caso de fallecimiento",
        "prima_base": 45_000,       # monthly COP
        "cobertura_max": 200_000_000,
        "categoria": "personal",
        "edad_min": 18, "edad_max": 70,
    },
    "accidentes": {
        "nombre": "Accidentes Personales",
        "descripcion": "Cobertura completa de accidentes individuales o familiares",
        "prima_base": 25_000,
        "cobertura_max": 50_000_000,
        "categoria": "personal",
        "edad_min": 18, "edad_max": 65,
    },
    "viajes": {
        "nombre": "Asistencia Médica Viajes",
        "descripcion": "Emergencias médicas en viajes nacionales e internacionales 24/7",
        "prima_base": 15_000,
        "cobertura_max": 30_000_000,
        "categoria": "personal",
    },
    "mascotas": {
        "nombre": "Seguro Mascotas",
        "descripcion": "Cobertura veterinaria y protección de daños para perros y gatos",
        "prima_base": 30_000,
        "cobertura_max": 5_000_000,
        "categoria": "mascotas",
    },
    "vida_deudor": {
        "nombre": "Vida Deudor",
        "descripcion": "Cancelación de deuda por fallecimiento o incapacidad",
        "prima_base": 20_000,
        "cobertura_max": 100_000_000,
        "categoria": "credito",
    },
    "hogar": {
        "nombre": "Seguro Hogar",
        "descripcion": "Protección para vivienda contra daños y siniestros",
        "prima_base": 35_000,
        "cobertura_max": 150_000_000,
        "categoria": "hogar",
    },
    "movilidad": {
        "nombre": "Seguro Movilidad",
        "descripcion": "Cobertura para vehículos: daños, robo, lesiones a terceros",
        "prima_base": 55_000,
        "cobertura_max": 80_000_000,
        "categoria": "movilidad",
    },
}
```

### Rule matching (`match_products`)

```python
RULES: list[tuple[str, Callable[[dict], bool]]] = [
    ("vida",       lambda p: p.get("familia_con_hijos") is True and p.get("preocupacion") == "proteger"),
    ("accidentes", lambda p: p.get("edad") in range(18, 36) and p.get("estado_civil") == "soltero"),
    ("viajes",     lambda p: p.get("viaja_frecuentemente") is True),
    ("mascotas",   lambda p: p.get("tiene_mascota") is True),
    ("vida_deudor",lambda p: p.get("tiene_deuda_activa") is True),
    ("hogar",      lambda p: p.get("es_propietario_vivienda") is True),
    ("movilidad",  lambda p: p.get("tiene_vehiculo") is not None),
]
```

### Rule implementation (7 rules from spec)

| Rule | Condition | Product | Confidence |
|------|-----------|---------|------------|
| R1 | `familia_con_hijos == true AND preocupacion == "proteger"` | Seguro de Vida | high |
| R2 | `edad in [18-35] AND estado_civil == "soltero"` | Accidentes Personales | medium |
| R3 | `viaja_frecuentemente == true` | Asistencia Médica Viajes | high |
| R4 | `tiene_mascota == true` | Seguro Mascotas | high |
| R5 | `tiene_deuda_activa == true` | Vida Deudor | high |
| R6 | `es_propietario_vivienda == true` | Seguro Hogar | high |
| R7 | `tiene_vehiculo != null` | Seguro Movilidad | high |

**Confidence assignment**: high for direct attribute matches (R1 with both conditions, R3-7 with single clear attribute), medium for partial matches (R2 needs both age + marital status). Matches are sorted by: high confidence first, then by `prima_base` descending (prioritizes higher-value products).

### Error handling

| Scenario | Behavior |
|----------|----------|
| Empty profile `{}` | Return `[]` — no rules matched |
| Unknown profile keys | Ignore unknown keys, match on known ones |
| Multiple matches | Return all ordered by confidence then prima_base |
| No matches at all | Return `[]` — AI handles gracefully ("no tengo recomendaciones para tu perfil actual") |

### Profile sufficiency determination

Determined by the AI, not hardcoded thresholds. The system prompt instructs:
- Once you have **at least one clear attribute** from the profile keys
- AND the user seems engaged/asking for recommendations
- Call `recommend_insurance(profile)` with whatever attributes you have
- If the result is empty, continue profiling

---

## 3. InsuranceFormSchema Design

**File**: `backend/app/services/insurance_schema.py`

### Schema structure

```
[Datos del Tomador]  (all required)
  - nombre (string) [REQ]
  - documento (string) [REQ]
  - email (email) [REQ]
  - telefono (string) [REQ]
  - fecha_nacimiento (date) [REQ]

[Cobertura]
  - tipo_cobertura (select) [REQ] — product-specific enums
  - suma_asegurada (number) [REQ] — product-specific ranges
  - coberturas_adicionales (select) [opt] — enum per product

[Beneficiario]  (conditional: only for Vida products)
  - beneficiario_nombre (string) [REQ if Vida]
  - beneficiario_parentesco (select) [opt]

[Pago]
  - forma_pago (select) [REQ] — "mensual" | "anual"
  - cuenta_pago (string) [opt]
  - acepta_terminos (boolean) [REQ]
```

### Product-specific field variants

```python
PRODUCT_FIELD_VARIANTS: dict[str, dict] = {
    "vida": {
        "suma_asegurada": {"min": 10_000_000, "max": 200_000_000,
                           "prompt_hint": "montos desde $10M hasta $200M"},
        "tipo_cobertura": {"enum": ["Fallecimiento", "Fallecimiento + Incapacidad",
                                     "Fallecimiento + Enfermedades Graves"]},
        "has_beneficiario": True,
    },
    "hogar": {
        "suma_asegurada": {"min": 20_000_000, "max": 150_000_000,
                           "prompt_hint": "montos desde $20M hasta $150M"},
        "tipo_cobertura": {"enum": ["Básica", "Amplia", "Todo Riesgo"]},
        "has_beneficiario": False,
    },
    "mascotas": {
        "suma_asegurada": {"min": 500_000, "max": 5_000_000,
                           "prompt_hint": "montos desde $500K hasta $5M"},
        "tipo_cobertura": {"enum": ["Básica", "Completa"]},
        "has_beneficiario": False,
    },
    # ... applies to accidentes, viajes, vida_deudor, movilidad
}
```

### Benficiary fields: conditional on product

The `InsuranceFormSchema.to_prompt_text()` includes the Beneficiario section **only** when the selected product has `has_beneficiario: True`. The AI receives the conditional logic in the system prompt and adapts its questions accordingly.

### Validation rules

| Field | Validation |
|-------|-----------|
| `nombre` | `pattern: r"^.{2,200}$"` |
| `documento` | `pattern: r"^[0-9]{5,15}$"` |
| `email` | email regex |
| `telefono` | `pattern: r"^\+?[0-9]{7,15}$"` |
| `suma_asegurada` | `min: product.min, max: product.max` |
| `acepta_terminos` | MUST be `true` for `create_policy()` |
| `fecha_nacimiento` | date format, age >= 18 |

### Dynamic loading integration

The generalized schema loader checks `session.estado_actual`:
- `recopilando_datos` → `credit_form.FormSchema`
- `recopilando_datos_seguro` → `insurance_schema.InsuranceFormSchema`

The `_compute_completitud_pct()` and `_parse_campos_actualizados()` methods in ChatService become domain-aware: they use the active schema's `campos_requeridos()` based on `estado_actual`.

---

## 4. State Machine Design

### State transition diagram

```
                    ┌────────────────────────────────────────────┐
                    │                 inicio                     │
                    └────────┬──────────────────┬────────────────┘
                             │                  │
                   intent:   │                  │  intent:
                   solicitar_│                  │  solicitar_
                   seguro    │                  │  credito
                             ▼                  ▼
                    ┌──────────────┐   ┌──────────────────────┐
                    │  perfilando  │   │ recopilando_datos    │
                    │  (insurance) │   │ (credit, existing)   │
                    └──────┬───────┘   └──────────────────────┘
                           │                    ... existing credit
              profile      │                      states below ...
              sufficient   │
                           ▼
                    ┌──────────────┐
              ┌────>│ recomendando │<────┐
              │     └──────┬───────┘     │
              │            │            │
              │   user     │ user       │ user wants
              │   declines │ selects    │ different
              │            │ product    │ product
              │            ▼            │
              │     ┌──────────────┐    │
              └─────│  cotizando   │────┘
                    └──────┬───────┘
                           │ user wants to buy
                           ▼
                    ┌──────────────────────────┐
                    │ recopilando_datos_seguro  │
                    │ (InsuranceFormSchema)     │
                    └──────┬───────────────────┘
                           │ confirmation
                           ▼
                    ┌──────────────────────┐
                    │ completado_seguro     │──> inicio (offer next steps)
                    └──────────────────────┘
```

### ChatService routing between domains

```python
# Inside _update_session_state()
INSURANCE_STATES = {"perfilando", "recomendando", "cotizando",
                    "recopilando_datos_seguro", "completado_seguro"}
CREDIT_STATES = {"recopilando_datos", "evaluando", "ofreciendo_producto", "completado"}

def _is_insurance_state(state: str) -> bool:
    return state in INSURANCE_STATES

# Transitions:
# inicio → perfilando: when AI detects insurance intent (solicitar_seguro)
# inicio → recopilando_datos: when AI detects credit intent (existing logic)
#
# Insurance transitions (when _is_insurance_state is True):
# perfilando → recomendando: when recommend_insurance tool is called
# recomendando → cotizando: when quote_insurance tool is called
# cotizando → recopilando_datos_seguro: when first save_form_field called (insurance schema)
# cotizando → recomendando: if user wants different product (chat pattern detection)
# recopilando_datos_seguro → completado_seguro: when create_policy succeeds
# recomendando → perfilando: if user declines (back to profiling)
```

### Profile sufficiency gate

No hardcoded backend gate. The AI controls the transition by calling `recommend_insurance()`. Once called, the session moves from `perfilando` → `recomendando`. This gives the AI full control over when profiling is "done enough."

### State → Tool filter mapping

| Session State | Active Tool Domain | Available Tools |
|--------------|-------------------|-----------------|
| `inicio` | all | credit + insurance tools |
| `perfilando` | insurance | `recommend_insurance` |
| `recomendando` | insurance | `recommend_insurance`, `quote_insurance` |
| `cotizando` | insurance | `quote_insurance` |
| `recopilando_datos_seguro` | insurance | `save_form_field`, `create_policy` |
| `completado_seguro` | none | no domain tools |
| (credit states) | credit | existing credit tools |

---

## 5. Tool Design

### `recommend_insurance(profile)`

```
Input:
  profile: dict   — demographic attributes from conversation

Output (success):
  [
    {
      "product_id": "vida",
      "nombre": "Seguro de Vida",
      "descripcion": "Respaldo económico para beneficiarios...",
      "categoria": "personal",
      "prima_base": 45000,
      "match_reason": "Tiene hijos y le preocupa protegerlos",
      "confidence": "high"
    }
  ]

Output (empty):
  [] — no products matched the profile

Errors:
  - Unexpected: handled by ToolBridge exception → "Error al ejecutar..."
```

### `quote_insurance(product_id, profile, coverage_level)`

```
Input:
  product_id: str       — "vida", "hogar", etc.
  profile: dict         — includes edad, suma_asegurada, etc.
  coverage_level: str   — "basica" | "estandar" | "premium"

Output (success):
  {
    "product_id": "vida",
    "nombre": "Seguro de Vida",
    "prima_mensual": 67500,
    "prima_anual": 810000,
    "cobertura_resumen": "Fallecimiento: $100M, Incapacidad: $100M",
    "deducible": "N/A",
    "vigencia": "Anual renovable"
  }

Errors:
  - {"error": "unknown_product"} — invalid product_id
  - {"error": "invalid_coverage"} — invalid coverage_level
```

### `create_policy(policy_data)`

```
Input:
  policy_data: dict
    customer_id: str     — customer UUID (from session)
    product_id: str      — insurance product UUID (from DB)
    form_data: dict      — collected campos_diligenciados
    debe_aceptar_terminos: true

Output (success):
  {
    "application_id": "uuid",
    "policy_id": "uuid",
    "numero_poliza": "POL-abc12345",
    "estado": "activo",
    "fecha_inicio": "2026-07-22T00:00:00"
  }

Errors:
  - {"error": "terms_not_accepted"} — forma_data.acepta_terminos is not true
  - {"error": "invalid_customer_id"} — customer not found
  - {"error": "invalid_product_id"} — product not found
  - {"error": "missing_required_fields"} — missing required insurance fields
```

Implementation: Creates `Application(tipo="seguro")` then `Policy` in atomic transaction. `numero_poliza` format: `POL-{uuid4 hex[:8].upper()}`.

### Tool injection strategy

| Session State | Tools Exposed | Hidden |
|--------------|---------------|--------|
| `inicio` | `get_products`, `get_customer`, `recommend_insurance` | credit-only tools hidden to reduce noise |
| `perfilando` | `recommend_insurance` | Only recommend visible (premature quote/create hidden) |
| `recomendando` | `recommend_insurance`, `quote_insurance` | create_policy hidden |
| `cotizando` | `quote_insurance` | Recommend visible only if user asks for alternatives |
| `recopilando_datos_seguro` | `save_form_field`, `create_policy` | recommend/quote hidden |
| `completado_seguro` | none | All hidden |

---

## 6. System Prompt Design

**File reference**: `backend/app/domain/prompts/insurance_system.md`

### Insurance fragment injected into `_build_system_prompt()`

Inserted as a section after the base Anna prompt and before tool instructions, gated by `_is_insurance_state(session.estado_actual)`:

```text
--- SEGUROS: CONTEXTO Y PERFILACIÓN ---

Ahora vas a ayudar al usuario a encontrar el seguro adecuado para él/ella/ su familia.
NO preguntes "qué seguro querés" — preguntá sobre su vida, su familia, su hogar.

PRODUCTOS DISPONIBLES:
- Seguro de Vida: respaldo económico para beneficiarios ($10M-$200M)
- Accidentes Personales: cobertura completa de accidentes
- Asistencia Médica Viajes: emergencias en viajes 24/7
- Seguro Mascotas: cobertura veterinaria para perros y gatos
- Vida Deudor: cancelación de deuda por fallecimiento
- Seguro Hogar: protección para vivienda
- Seguro Movilidad: cobertura para vehículos

PERFILACIÓN CONVERSACIONAL:
Preguntá de forma natural sobre:
- Familia: ¿tiene hijos? ¿está casado/a?
- Hogar: ¿vive en casa propia o arrendada?
- Movilidad: ¿tiene carro, moto? ¿viaja frecuentemente?
- Mascotas: ¿tiene mascotas?
- Deudas: ¿tiene algún crédito activo?
- Preocupaciones: ¿qué le gustaría proteger?

Segmento de referencia (contexto de población):
{CSV_SEGMENT_CONTEXT}  ← pre-computed text from offline analysis

REGLAS DE RECOMENDACIÓN:
1. Una vez que tengas al menos un atributo claro del perfil, llamá a
   `recommend_insurance(profile)` con los atributos disponibles.
2. Si el resultado está vacío, seguí preguntando amablemente.
3. Mostrá 1-3 opciones máximo. Nunca inventes productos.
4. Usá el contexto de segmento para dar contexto: "muchas familias como la tuya
   eligen..."
5. Para precios exactos, llamá a `quote_insurance(product_id, profile)`.
6. NUNca des precios exactos sin llamar a quote_insurance.
```

### CSV segment context

Pre-computed at deploy time from `colsubsidio_segments.csv`. A text snippet stored as a constant in `chat.py` or loaded from a `.txt` companion file. Example:

```text
Segmento: Familias Jóvenes (25-40 años, 1-2 hijos, ingresos medios)
Productos comunes: Seguro de Vida, Asistencia Médica Viajes, Seguro Mascotas
```

The CSV itself is never loaded at runtime — only the aggregated text fragment survives into the system prompt.

### Handling "I don't know"

The system prompt includes:

```text
Si el usuario no sabe o es vago ("no sé", "tal vez", "no estoy seguro"):
- Normalizalo: "tranquilo, no te preocupes — muchas personas no lo tienen claro"
- Reformulá: preguntá de otra forma, con ejemplos concretos
- Si realmente no responde pasá al siguiente tema
- Nunca presiones ni insistas más de 2 veces sobre el mismo tema
```

---

## 7. Data Model Changes

### Session model — `insurance_profile` JSON field

Field added:
```python
insurance_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
```

Structure (evolves per turn, AI updates via metadata in tool calls):
```json
{
  "edad": 35,
  "estado_civil": "casado",
  "familia_con_hijos": true,
  "tiene_mascota": false,
  "tiene_vehiculo": "auto",
  "es_propietario_vivienda": true,
  "viaja_frecuentemente": false,
  "tiene_deuda_activa": true,
  "preocupacion": "proteger"
}
```

All keys are optional. The JSON starts as `null` and is set to `{}` when profiling begins. Values are added incrementally by the AI.

### Insurance model — `insurance_category` field

Field added:
```python
insurance_category: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
```

Valid values: `"personal"`, `"hogar"`, `"movilidad"`, `"mascotas"`, `"credito"`.

### Session state machine — valid states extended

```python
VALID_STATES = {
    # Credit states (existing)
    "inicio", "recopilando_datos", "evaluando", "ofreciendo_producto", "completado",
    # Insurance states (new)
    "perfilando", "recomendando", "cotizando", "recopilando_datos_seguro", "completado_seguro",
}
```

### Intent values extended

```python
VALID_INTENTS = {
    # Existing
    "solicitar_credito", "consultar_producto", "simular_cuota", "ninguna",
    # New
    "solicitar_seguro", "info_producto_seguro", "cotizar_seguro",
}
```

---

## 8. Quote / Pricing Logic

**Inside**: `backend/app/services/recommendation_engine.py`

### Formula

```
prima_mensual = prima_base × coverage_multiplier(coverage_level) × age_multiplier(edad)
prima_anual = prima_mensual × 12
```

### Multipliers

**Coverage multiplier**:
| Level | Multiplier |
|-------|-----------|
| `basica` | 0.8× |
| `estandar` | 1.0× |
| `premium` | 1.5× |

**Age multiplier** (only for products with `edad_min`/`edad_max`):
| Age Range | Multiplier |
|-----------|-----------|
| 18-30 | 1.0× |
| 31-45 | 1.2× |
| 46-60 | 1.5× |
| 61+ | 2.0× |

**Number of beneficiaries multiplier** (only for Vida products):
| Beneficiaries | Multiplier |
|--------------|------------|
| 1 | 1.0× |
| 2 | 1.15× |
| 3+ | 1.3× |

### Implementation

```python
def quote_product(product_id: str, profile: dict,
                  coverage_level: str = "estandar") -> dict:
    product = PRODUCTS.get(product_id)
    if not product:
        return {"error": "unknown_product"}

    if coverage_level not in COVERAGE_MULTIPLIERS:
        return {"error": "invalid_coverage"}

    prima = product["prima_base"]
    prima *= COVERAGE_MULTIPLIERS[coverage_level]

    edad = profile.get("edad")
    if edad and "edad_min" in product:
        prima *= AGE_MULTIPLIER(edad)

    if product_id == "vida":
        num_beneficiarios = len(profile.get("beneficiarios", [1]))
        prima *= BENEFICIARY_MULTIPLIER(min(num_beneficiarios, 3))

    prima_mensual = round(prima, 0)
    return {
        "product_id": product_id,
        "nombre": product["nombre"],
        "prima_mensual": prima_mensual,
        "prima_anual": prima_mensual * 12,
        "cobertura_resumen": _cobertura_summary(product_id, coverage_level),
        "deducible": DEDUCIBLES.get(coverage_level, "N/A"),
        "vigencia": "Anual renovable",
    }
```

**Stub payment**: No real gateway. Payment method collected in InsuranceFormSchema but the policy is issued immediately. Payment processing is future scope.

---

## 9. Sequence Diagrams

### Happy path: Full insurance flow

```
User                    Anna/ChatService                       recommendation_engine       Database
 │                           │                                      │                       │
 │ "necesito un seguro"      │                                      │                       │
 │──────────────────────────►│                                      │                       │
 │                           │  Detect intent: solicitar_seguro     │                       │
 │                           │  estado_actual: inicio → perfilando  │                       │
 │                           │  Inject insurance prompt fragment    │                       │
 │                           │                                      │                       │
 │ "vivo con mi esposa       │                                      │                       │
 │  e hija pequeña"          │                                      │                       │
 │◄──────────────────────────┤                                      │                       │
 │──────────────────────────►│  Update session.insurance_profile    │                       │
 │                           │  {"familia_con_hijos": true}        │──────────────►         │
 │                           │                                      │                       │
 │ (more profiling...)       │                                      │                       │
 │                           │                                      │                       │
 │ Anna decides profile      │                                      │                       │
 │ is sufficient             │                                      │                       │
 │                           │  Phase 1: recommend_insurance(...)   │                       │
 │                           │─────────────────────────────────────►│                       │
 │                           │◄─────────────────────────────────────┤ [{vida, conf:high},   │
 │                           │                                        {accidentes, med}]   │
 │                           │  estado_actual: perfilando →          │                       │
 │                           │  recomendando                         │                       │
 │ "te recomiendo Seguro     │                                      │                       │
 │  de Vida — muchas         │                                      │                       │
 │  familias eligen...       │                                      │                       │
 │  ¿querés ver coberturas?" │                                      │                       │
 │◄──────────────────────────┤                                      │                       │
 │                           │                                      │                       │
 │ "sí, ¿cuánto cuesta?"     │                                      │                       │
 │──────────────────────────►│                                      │                       │
 │                           │  Phase 1: quote_insurance("vida",    │                       │
 │                           │            {edad:35, ...}, "estandar")│                      │
 │                           │─────────────────────────────────────►│                       │
 │                           │◄─────────────────────────────────────┤ prima: $54,000/mes    │
 │                           │  estado_actual: recomendando →       │                       │
 │                           │  cotizando                            │                       │
 │                           │                                      │                       │
 │ "$54.000/mes con          │                                      │                       │
 │  cobertura estándar...    │                                      │                       │
 │  ¿querés ajustar algo?"   │                                      │                       │
 │◄──────────────────────────┤                                      │                       │
 │                           │                                      │                       │
 │ "me interesa,              │                                      │                       │
 │  quiero contratarlo"      │                                      │                       │
 │──────────────────────────►│                                      │                       │
 │                           │  Load InsuranceFormSchema             │                       │
 │                           │  estado_actual: cotizando →          │                       │
 │                           │  recopilando_datos_seguro             │                       │
 │                           │                                      │                       │
 │ (fields collected         │                                      │                       │
 │  progressively via        │                                      │                       │
 │  save_form_field)         │                                      │                       │
 │                           │                                      │                       │
 │                           │  All required fields collected       │                       │
 │                           │  Summary + "¿Confirmás?"             │                       │
 │ "confirmo"               │                                      │                       │
 │──────────────────────────►│                                      │                       │
 │                           │  Phase 1: create_policy(...)         │                       │
 │                           │──────────────────────────────────────────────►              │
 │                           │◄─────────────────────────────────────────────── app_id     │
 │                           │                                              + policy_id   │
 │                           │  estado_actual: recopilando_datos_seguro →                 │
 │                           │  completado_seguro                                         │
 │                           │                                      │                       │
 │ "¡Póliza creada!          │                                      │                       │
 │  Número: POL-AB12...      │                                      │                       │
 │  ¿algo más?"             │                                      │                       │
 │◄──────────────────────────┤                                      │                       │
```

### Edge case: User doesn't know what they need

```
User                    Anna/ChatService                       recommendation_engine
 │                           │                                      │
 │ "quiero un seguro         │                                      │
 │  pero no sé cuál"         │                                      │
 │──────────────────────────►│                                      │
 │                           │  estado_actual: inicio → perfilando  │
 │                           │                                      │
 │ "tranquilo, contame       │                                      │
 │  de tu vida...            │                                      │
 │  ¿vivís solo o            │                                      │
 │  acompañado?"             │                                      │
 │◄──────────────────────────┤                                      │
 │                           │                                      │
 │ "vivo solo"               │                                      │
 │──────────────────────────►│  profile: {"estado_civil":"soltero"} │
 │                           │                                      │
 │ "genial! ¿y tenés         │                                      │
 │  mascota?"                │                                      │
 │◄──────────────────────────┤                                      │
 │                           │                                      │
 │ "no, no tengo"            │                                      │
 │──────────────────────────►│  profile += {"tiene_mascota": false} │
 │                           │                                      │
 │ "entendido, ¿viajás       │                                      │
 │  frecuentemente por       │                                      │
 │  trabajo o placer?"       │                                      │
 │◄──────────────────────────┤                                      │
 │                           │                                      │
 │ "sí, cada mes viajo"      │                                      │
 │──────────────────────────►│  profile += {"viaja_frecuentemente": │
 │                           │             true}                    │
 │                           │                                      │
 │                           │  Call recommend_insurance(profile)   │
 │                           │─────────────────────────────────────►│
 │                           │◄─────────────────────────────────────┤ [{viajes, conf:high}]
 │                           │                                      │
 │ "por lo que me contás,    │                                      │
 │  te recomiendo Asistencia │                                      │
 │  Médica Viajes...         │                                      │
 │  ¿querés que te cuente    │                                      │
 │  más?"                    │                                      │
 │◄──────────────────────────┤                                      │
```

---

## 10. Implementation Phases

### Phase 1: Data models + FormSchema (PR ~150 lines)

**Branches from**: `main`
**Files**:
- `backend/app/models/insurance.py` — add `insurance_category` column
- `backend/app/models/session.py` — add `insurance_profile` JSON column
- `backend/app/services/insurance_schema.py` — create InsuranceFormSchema
- `backend/tests/test_insurance_schema.py` — unit tests

**Deliverable**: Schema defined and testable. Models extended (additive, no migration needed). Credit flow unaffected.

### Phase 2: Recommendation engine + tools (PR ~250 lines)

**Branches from**: `main` (or Phase 1 branch if merged)
**Files**:
- `backend/app/services/recommendation_engine.py` — create pure functions, product catalog
- `backend/app/tools/domain_tools.py` — add `recommend_insurance()`, `quote_insurance()`, `create_policy()`
- `backend/tests/test_recommendation_engine.py` — unit tests

**Deliverable**: Tools registered and testable via FastMCP. Recommendation logic verified. Tools are inert (no ChatService integration yet).

### Phase 3: State machine + system prompt + flow wiring (PR ~200 lines)

**Branches from**: `main` (or after Phase 1+2 merged)
**Files**:
- `backend/app/services/chat.py` — insurance-aware `_build_system_prompt()`, `_update_session_state()` with 5 new states, domain-based tool filtering
- `backend/app/services/tool_bridge.py` — add `domain` filter to `get_openai_tools()`
- `backend/app/domain/prompts/insurance_system.md` — system prompt fragment
- `backend/data/colsubsidio_segments.csv` — offline segment analysis

**Deliverable**: Full conversational flow works end-to-end. Credit flow regression-tested.

### Phase 4: Tests (PR ~150 lines)

**Branches from**: `main` (or after Phase 3 merged)
**Files**:
- `backend/tests/test_insurance_flow.py` — integration tests (full happy path, unknown product, terms declined, profile empty)
- Extend existing `test_chat.py` with insurance state transition tests

**Deliverable**: All new scenarios covered. Existing credit tests still pass.

### Chain strategy

```
main ← Phase 1 (data models + schema)
     ← Phase 2 (engine + tools)
     ← Phase 3 (state machine + flow wiring)
     ← Phase 4 (tests)
```

Each phase merges to `main` independently (stacked-to-main). No long-lived feature branches. Each PR is reviewable in ≤60 minutes.

---

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | `match_products()` — all 7 rules, empty profile, multi-match | Pure functions, no DB needed — `test_recommendation_engine.py` |
| Unit | `quote_product()` — all multipliers, unknown product, invalid coverage | Pure functions, verify formula output — `test_recommendation_engine.py` |
| Unit | `InsuranceFormSchema.to_prompt_text()` — all sections, product variants | Verify output structure — `test_insurance_schema.py` |
| Unit | `InsuranceFormSchema.campos_requeridos()` — with conditional beneficiary fields | Verify dynamic required list per product — `test_insurance_schema.py` |
| Integration | Full happy path: profile → recommend → quote → collect → create_policy | Live DB with test data, mock AI calls — `test_insurance_flow.py` |
| Integration | Terms declined → no policy created | Verify atomic rollback — `test_insurance_flow.py` |
| Integration | Unknown insurance_id → error | Verify validation — `test_insurance_flow.py` |
| Integration | Credit flow regression: existing tests still pass | Run full test suite after each phase |
| Integration | `ToolBridge` domain filtering: insurance tools hidden in credit states | Verify filtered schema output — `test_tool_bridge.py` extension |

---

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. The insurance flow extends existing in-process Python components (ChatService, ToolBridge, FastMCP) with no new subprocess or shell execution paths.

---

## Migration / Rollout

| Step | Action | Risk |
|------|--------|------|
| 1 | Deploy model migrations (additive columns — `insurance_profile`, `insurance_category`) | None — nullable columns, existing rows unaffected |
| 2 | Deploy recommendation engine + tools | None — no ChatService changes yet, tools are inert |
| 3 | Deploy ChatService flow wiring | Low — insurance states only entered on insurance intent; credit sessions never hit insurance code paths |
| 4 | Deploy tests | Confirms regression safety |

**Rollback**: Revert the ChatService changes. Insurance states return to `inicio`. Insurance models and tools remain deployed but dormant. No data cleanup needed since no production insurance sessions exist pre-GA.

---

## Open Questions

- [ ] **Exact Colsubsidio product catalog IDs**: The PRODUCTS dict uses string keys (`"vida"`, `"hogar"`, etc.) but `create_policy` references `insurance_id` UUIDs from the DB. The tool needs to map between internal keys and DB UUIDs — either via a lookup dict or by querying the Insurance table by `insurance_category`.
- [ ] **CSV segment context format**: What level of detail should the injected text have? A short paragraph per segment or a table? Needs input from the business team on the offline analysis output format.
- [ ] **Coverage level enumeration**: Which products support which coverage levels? The current design assumes all products support `basica`/`estandar`/`premium` but this may vary per product family.

## Architecture Decisions

### Decision: Profile stored as flat JSON on Session

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Normalized profile table | Over-engineered for 9 optional keys | ❌ Rejected |
| **JSON field on Session** | Simple, flexible, no schema migration per key | ✅ **Chosen** |
| AI-injected metadata in conversation | Not queryable, fragile | ❌ Rejected |

### Decision: Product catalog hardcoded, not DB-loaded

| Option | Tradeoff | Decision |
|--------|----------|----------|
| **Hardcoded dict** | No DB call at inference, versioned with code | ✅ **Chosen** |
| DB Insurance table | Needs sync with catalog, DB dependency for every recommend | ❌ Rejected |
| Config file | Needs parsing, separate versioning concern | ❌ Rejected |

The DB Insurance table is for **issued/available products to reference** (via `insurance_id` in `create_policy`). The recommendation engine uses its own hardcoded catalog that mirrors the real Colsubsidio products.

### Decision: AI judges profile sufficiency, not hardcoded threshold

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Hardcoded minimum N attributes | May mismatch AI's conversational flow | ❌ Rejected |
| **AI decides when to call recommend_insurance()** | Natural, matches conversation pacing | ✅ **Chosen** |

### Decision: System prompt fragment as text constant, not loaded from file

| Option | Tradeoff | Decision |
|--------|----------|----------|
| **String constant in chat.py** | Simple, versioned with code | ✅ **Chosen** |
| External .md file | More maintenance, harder to reference inline | ❌ Rejected |
| DB-stored prompt | Over-engineered for MVP | ❌ Rejected |

The fragment is a Python constant string in `chat.py` alongside `BASE_SYSTEM_PROMPT`. The `.md` file in `domain/prompts/` serves as documentation source — the actual constant is inlined.
