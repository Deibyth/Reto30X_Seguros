# Design: Insurance Personalization by Category + Segment

> **Change:** `insurance-personalization-by-category`
> **Date:** 2026-07-23
> **Authors:** Architecture
> **Status:** Draft

---

## 1. Context

### 1.1 Problem

Today, `recommend_insurance()` applies the same conversational rules (R1-R7) to every affiliate regardless of income level or family composition. With 500K affiliates across 4 categories — 72.8% SIGMA (A), 16.4% PI (B), 9.8% ZETA (C), and 1% MU — recommendations miss the mark: offering premium coberturas to low-income members or basic protection to high-income ones.

### 1.2 Solution

Load the 500K affiliate dataset into memory at startup and add compound rules (R8-R13) that map `categoria_afiliacion × segmento_grupo_familiar → products`. Conversational rules remain as fallback. Existing architecture (pure functions, stateless engine, MCP tools, ChatService state machine) stays intact.

### 1.3 Scope Recap

| In Scope | Out of Scope |
|----------|--------------|
| `SegmentDataService` — load 500K CSV at startup | ML-based recommendation |
| Compound rules R8-R13 in recommendation engine | Adding `segmento_grupo_familiar` to Customer model |
| `match_products_by_segment()` new function | Real-time dataset refresh |
| `recommend_insurance(profile, documento?)` optional param | Multi-product cross-sell weighting |
| `load_segment_data` MCP tool | |
| Anonymous flow: salary → `_calcular_categoria()` | |
| Profile pre-seed from documento lookup | |

### 1.4 Key Decisions (Already Made)

| Decision | Rationale |
|----------|-----------|
| **MU(D) = "sin categoría"** | No new DB column. MU mapped to generic fallback. |
| **SEGMENTO_GRUPO_FAMILIAR is CSV-only** | Not added to Customer model. Only available via SegmentDataService. |
| **CSV loads once at startup** | Singleton, loaded in FastAPI lifespan startup event. Restart to reload. |
| **Anonymous users infer category via salary** | `_calcular_categoria(salario)` already exists. No document → Anna asks salary range. |
| **Existing `match_products()` stays unmodified** | New `match_products_by_segment()` is additive. Complete backward compatibility. |
| **Compound rules are additive, not overriding** | Conversational R1-R7 always apply as safety net. Compound rules add products. |

---

## 2. Architecture

### 2.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                          │
│                                                                     │
│  Startup (lifespan)                                                 │
│  ┌─────────────────────────────────────┐                            │
│  │  SegmentDataService.load()          │  reads                      │
│  │  ┌─────────────────────────────┐    │◄──────── CSV file          │
│  │  │  documento_index: dict[str] │    │  (gitignored)               │
│  │  │  aggregate_index: dict[tuple]│    │                            │
│  │  └─────────────────────────────┘    │                            │
│  └─────────────────────────────────────┘                            │
│                                                                     │
│  ┌──────────────┐    ┌───────────────────┐    ┌─────────────────┐   │
│  │  ChatService │───►│  ToolBridge       │───►│  domain_tools   │   │
│  │  (state mach)│    │  (OpenAI schema   │    │  (MCP tools)    │   │
│  │              │    │   → execute)      │    │                 │   │
│  └──────┬───────┘    └───────────────────┘    └────────┬────────┘   │
│         │                                              │            │
│         │  reads/writes                                │  calls     │
│         ▼                                              ▼            │
│  ┌──────────────┐    ┌──────────────────────────────┐                │
│  │  Session (DB) │    │  recommendation_engine.py    │               │
│  │  .insurance_  │    │  match_products()            │               │
│  │  profile      │    │  match_products_by_segment() │               │
│  └──────────────┘    └──────────────────────────────┘                │
│                               ▲                                      │
│                               │ imports singleton                    │
│                               │                                      │
│                      ┌────────┴────────┐                             │
│                      │ SegmentDataSvc  │                             │
│                      │ (app.state /    │                             │
│                      │  module-level)  │                             │
│                      └─────────────────┘                             │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
                    ┌──────┐
                    │ User │
                    └──┬───┘
                       │ "quiero un seguro"
                       ▼
               ┌─────────────────┐
               │  ChatService    │  estado_actual = "inicio"
               │  classify_intent│  → "perfilando"
               └────────┬────────┘
                        │
             ╔══════════╧══════════╗
             ║  1. WITH documento ║
             ╚══════════╤══════════╝
                        │
               ┌────────▼────────┐
               │ get_customer()  │──► Customer DB
               │ SegmentDataSvc  │──► documento_index[doc]
               │   .lookup_by_   │    → {categoria, segmento}
               │    documento()  │
               └────────┬────────┘
                        │
               ┌────────▼────────┐
               │ Pre-seed        │
               │ insurance_      │
               │ profile with    │
               │ categoria + seg │
               └────────┬────────┘
                        │
             ╔══════════╧══════════╗
             ║  2. WITHOUT doc    ║
             ╚══════════╤══════════╝
                        │
               ┌────────▼────────┐
               │ Anna asks       │
               │ salary range    │
               └────────┬────────┘
                        │
               ┌────────▼────────┐
               │ _calcular_      │
               │ categoria(sal)   │──► "A" | "B" | "C"
               └────────┬────────┘
                        │
                        ▼
               ┌─────────────────┐
               │ recommend_      │
               │ insurance(      │
               │  profile,       │
               │  documento?)    │
               └────────┬────────┘
                        │
               ┌────────▼────────┐
               │ recommendation_ │
               │ engine          │
               │                 │
               │ 1. categoria?   │──NO──► match_products(profile)
               │    YES          │       (R1-R7 only)
               │ 2. match_       │
               │    products_by_ │
               │    segment()    │
               │    → R8-R13     │
               │    → R1-R7      │
               │    → merge +    │
               │      sort       │
               └─────────────────┘
```

---

## 3. Component Design

### 3.1 SegmentDataService (`backend/app/services/segment_data.py`)

#### 3.1.1 Interface

```python
class SegmentDataService:
    def __init__(self, csv_path: str | None = None) -> None: ...
    async def load(self) -> None: ...
    def lookup_by_documento(self, documento: str) -> dict | None: ...
    def get_aggregate_stats(
        self, categoria: str | None = None, segmento: str | None = None
    ) -> list[dict]: ...
    def is_loaded(self) -> bool: ...
```

#### 3.1.2 Internal Data Structures

```python
# documento_index: documento -> per-member data
# Built from CSV rows, one entry per documento
documento_index: dict[str, dict] = {
    "100000001": {
        "categoria": "A",                # normalized from SIGMA/SIGMA__A
        "segmento": "LAMBDA",            # normalized uppercase
        "consumos": {                    # product category purchase counts
            "drogueria": 12,
            "seguros": 3,
            "vivienda": 1,
            # ... column-per-product-category from CSV
        },
        "prima_promedio": 45000.0,       # nullable float
        "edad": 34,                      # nullable int
    },
    # ... 500K entries
}

# aggregate_index: (categoria, segmento) -> aggregate stats
# Built by grouping documento_index by (cat, seg)
aggregate_index: dict[tuple[str, str], dict] = {
    ("A", "LAMBDA"): {
        "total_afiliados": 185000,
        "producto_counts": {             # summed counts across all members
            "drogueria": 2450000,
            "seguros": 720000,
            "vivienda": 310000,
        },
        "prima_promedio": 42300.0,       # average of per-member prima_promedio
    },
    ("A", "RHO"): { ... },
    # ... all (cat, seg) combinations present in data
}
```

#### 3.1.3 Load Lifecycle

```
FastAPI startup
    │
    ├─ lifespan() begins
    │
    ├─ init_engine()
    │
    ├─ create_all tables
    │
    ├─ init FastMCP
    │
    ├─ SegmentDataService(csv_path)     ← instantiate
    │
    ├─ await segment_data.load()        ← read CSV, build indexes
    │    │
    │    ├─ FileNotFoundError?
    │    │   └─ log WARNING, is_loaded = False, return
    │    │
    │    ├─ Missing columns?
    │    │   └─ log WARNING with details, is_loaded = False, return
    │    │
    │    ├─ Malformed row?
    │    │   └─ log WARNING per row, skip row, continue
    │    │
    │    ├─ Normalize categoria (SIGMA→A, PI→B, ZETA→C, MU→MU)
    │    │
    │    ├─ Build documento_index (dict per row)
    │    │
    │    ├─ Build aggregate_index (group by cat×seg)
    │    │
    │    └─ is_loaded = True
    │
    └─ app.state.segment_data = segment_data
```

**Thread safety**: Both indexes are built once during `load()` and never mutated thereafter. All query methods are read-only. Python dict reads are thread-safe (GIL-protected).

#### 3.1.4 CSV Format Expected

The CSV is expected at `backend/data/Usos_Productos_Afiliados_SIN_ID2.csv` with these columns (case-insensitive header matching):

| Column | Type | Normalized To |
|--------|------|---------------|
| `documento` | string | Used as-is (key) |
| `categoria` | string | A/B/C/MU (SIGMA→A, PI→B, ZETA→C) |
| `segmento_grupo_familiar` | string | LAMBDA/RHO/EPSILON/IOTA/CHI/THETA/PI |
| `producto_*` | integer | Stored in `consumos` dict |
| `prima_promedio` | float | Stored as float or None |
| `edad` | integer | Stored as int or None |

#### 3.1.5 Error Handling Matrix

| Condition | Behavior |
|-----------|----------|
| File not found | `log.warning()`, `is_loaded=False`, no-op |
| File corrupt (not parseable) | `log.warning()`, `is_loaded=False`, no-op |
| Missing required columns | `log.warning()` with column list, `is_loaded=False` |
| Malformed row (wrong count) | `log.warning()` with row info, skip, continue |
| Unknown categoria value | Normalize to MU (generic fallback) |
| Empty/missing segmento | Store as `None` |

### 3.2 Extended Recommendation Engine (`backend/app/services/recommendation_engine.py`)

#### 3.2.1 New Constants

```python
# Compound rules: (categoria, segmento_or_any, product_ids, confidence, reason_template)
# ordem: more specific (cat+seg) first, then cat-only, then any+seg
SEGMENT_RULES: list[tuple] = [
    # R8:  A + LAMBDA  → vida, hogar
    ("A", "LAMBDA", ["vida", "hogar"], "medium",
     "Producto popular en afiliados categoría A sin grupo familiar"),

    # R9:  A + RHO     → vida, accidentes
    ("A", "RHO", ["vida", "accidentes"], "medium",
     "Común en afiliados categoría A con perfil monoparental"),

    # R10: A + EPSILON → vida, hogar
    ("A", "EPSILON", ["vida", "hogar"], "medium",
     "Producto popular en afiliados categoría A con familia nuclear"),

    # R11: B + any     → accidentes, movilidad
    ("B", None, ["accidentes", "movilidad"], "medium",
     "Producto popular en tu categoría de afiliación (B)"),

    # R12: C + any     → all 6 products (vida+hogar high, rest medium)
    ("C", None, ["vida", "hogar", "movilidad", "accidentes", "viajes", "mascotas"], "mixed",
     "Cobertura premium disponible para tu categoría (C)"),

    # R13: any + IOTA  → vida, hogar
    (None, "IOTA", ["vida", "hogar"], "medium",
     "Común en afiliados con perfil de pareja"),
]
```

**Rule matching algorithm**:
1. Iterate `SEGMENT_RULES` in definition order
2. For each rule, check `categoria` match (None = any) AND `segmento` match (None = any)
3. Multiple rules can match the same categoria+segmento (e.g., C+EPSILON matches R12 AND R13)
4. Collect unique product_ids from all matching rules
5. For products matched by multiple rules, use highest confidence
6. R12 special case: vida+hogar = "high", rest = "medium"

#### 3.2.2 New Function: `match_products_by_segment()`

```python
def match_products_by_segment(
    profile: dict,
    categoria: str | None = None,
    segmento: str | None = None,
) -> list[dict]:
    """Apply compound rules (R8-R13) + conversational rules (R1-R7).

    Algorithm:
    1. If categoria is None / "MU" / unknown → skip compound rules
    2. Apply SEGMENT_RULES matching (categoria, segmento)
    3. Collect matched products with (confidence, match_reason)
    4. Apply R1-R7 conversational rules (always, as safety net)
    5. Merge: conversational wins on confidence when same product matches both
    6. Apply segment weighting modifiers (reorder only, never exclude)
    7. Sort: confidence desc, then boosted products first, then prima_base desc

    Parameters
    ----------
    profile : dict
        Conversational profile attributes (same as match_products).
    categoria : str | None
        One of "A", "B", "C", or None/MU for fallback.
    segmento : str | None
        Family segment label or None if unknown.

    Returns
    -------
    list[dict]
        Merged, sorted product list. Same schema as match_products().
    """
    ...
```

**Confidence merge rules**:

| Conversational | Compound | Result |
|----------------|----------|--------|
| high | — | high (conversational wins) |
| — | medium | medium (added via segment) |
| high | medium | high (conversational confirmed) |
| medium (fallback) | medium | medium (both agree) |
| — | — | excluded |

#### 3.2.3 Confidence Table (from spec)

| Source | confidence | match_reason |
|--------|------------|-------------|
| R1-R7 match | high | Existing reason unchanged |
| Compound (categoria only) | medium | "Producto popular en tu categoría de afiliación ({categoria})" |
| Compound (categoria + segmento) | medium | "Común en afiliados {categoria} con perfil {segmento_label}" |
| Conversational + compound overlap | high | Original reason + "y está alineado con tu categoría" |
| R1-R7 (fallback, no categoria) | medium | Existing reason + "(perfil general)" |

#### 3.2.4 Segment Weighting Modifiers

Segment modifiers are applied AFTER the initial match phase:

```python
SEGMENT_BOOST: dict[str, list[str]] = {
    "LAMBDA": ["vida", "hogar"],         # singles → basic protection first
    "RHO":    ["vida", "accidentes"],    # monoparental → life + accident
    "EPSILON": ["vida", "hogar"],        # nuclear → home + life
    "IOTA":   ["vida", "hogar"],         # couples → home + life
    # CHI/THETA/PI → no boost
}
```

When `segmento` is known (not None, not CHI/THETA/PI/PI), boosted products are sorted BEFORE non-boosted products at the same confidence level. This is purely a **reorder**, never an exclusion.

#### 3.2.5 Backward Compatibility Guarantees

- `match_products(profile)` — **unmodified** in code and behavior
- `PRODUCTS` dict — **unchanged**
- `RULES` list — **unchanged**
- `quote_product()` — **unchanged**
- Profiles without `categoria_afiliacion` key → R1-R7 only
- Empty profile → `[]` always
- `match_products_by_segment({}, None, None)` → same as `match_products({})` → `[]`

### 3.3 Extended MCP Tools (`backend/app/tools/domain_tools.py`)

#### 3.3.1 `recommend_insurance()` — Optional `documento` Param

```python
@mcp.tool()
async def recommend_insurance(
    profile: dict,
    documento: str | None = None,
) -> str:
    """Recommend insurance products based on profile + optional category/segment.

    When documento is provided:
    1. Look up categoria + segmento from SegmentDataService
    2. Call match_products_by_segment(profile, categoria, segmento)
    3. Include category note in output

    When documento is not provided but profile has categoria_afiliacion:
    1. Use profile's categoria_afiliacion directly
    2. Call match_products_by_segment(profile, profile_categoria, None)
    3. Include category note in output

    When neither documento nor profile categoria:
    1. Call match_products(profile) — existing behavior
    2. No category note

    When documento not found in dataset:
    1. Log warning
    2. Fall back to match_products(profile) — existing behavior
    """
```

**Flow diagram**:

```
recommend_insurance(profile, documento?)
    │
    ├─ documento provided?
    │   ├─ YES → segment_data.lookup_by_documento(documento)
    │   │         ├─ found? → match_products_by_segment(profile, cat, seg)
    │   │         └─ not found? → log warning + match_products(profile)
    │   │
    │   └─ NO  → profile has categoria_afiliacion?
    │               ├─ YES → match_products_by_segment(profile, cat, None)
    │               └─ NO  → match_products(profile)   [existing behavior]
    │
    └─ Format output with category note when applicable
```

**Important**: Change from sync to async. The existing `recommend_insurance` is a sync `@mcp.tool()` because it only calls pure functions. With the optional `documento` param, it needs to potentially call `segment_data.lookup_by_documento()` (sync, since SegmentDataService is in-memory — but accessing through `app.state` requires async context in some setups). Either keep it sync and import the singleton directly, or make it `async`. Decision: **keep it sync** since SegmentDataService lookups are pure dict reads — no I/O.

Actually, wait: looking at the existing pattern, `recommend_insurance` is sync (no `async`). But if we need `app.state.segment_data`, that's available. Or we can import the singleton from a module-level reference. Let me check how the tools access services...

Looking at `domain_tools.py`, tools access `async_session_maker` via a module-level import: `from app.database import async_session_maker`. We can do the same for `segment_data`:

```python
from app.services.segment_data import segment_data  # module-level singleton
```

This keeps `recommend_insurance` sync. Clean.

#### 3.3.2 New `load_segment_data()` Tool

```python
from app.services.segment_data import segment_data

@mcp.tool()
def load_segment_data(documento: str | None = None) -> str:
    """Return aggregate product consumption patterns per segment.

    Parameters
    ----------
    documento : str | None
        If provided, returns stats for that member's segment.
        If omitted, returns a summary of all segments.
    """
    if not segment_data.is_loaded():
        return "Datos de segmentación no disponibles. El archivo CSV no fue cargado."

    if documento:
        info = segment_data.lookup_by_documento(documento)
        if not info:
            return f"No se encontraron datos para el documento '{documento}'."

        stats = segment_data.get_aggregate_stats(info["categoria"], info["segmento"])
        # format: "El segmento {segmento_label} (categoría {categoria}) suele comprar: ..."
    else:
        stats = segment_data.get_aggregate_stats()
        # format: table all segments sorted by total_afiliados desc
```

**Segment label mapping**:
```python
SEGMENTO_LABELS: dict[str | None, str] = {
    "LAMBDA": "Sin grupo familiar",
    "RHO": "Monoparental",
    "EPSILON": "Nuclear",
    "IOTA": "Pareja",
    "CHI": "No especificado",
    "THETA": "No especificado",
    "PI": "No especificado",
    None: "No disponible",
}
```

#### 3.3.3 `get_customer()` — Enriched Output

Append a segment line when segment data is available:

```python
# After existing customer output lines:
info = segment_data.lookup_by_documento(documento_identidad)
if info and info.get("segmento"):
    segmento_label = SEGMENTO_LABELS.get(info["segmento"], "No especificado")
    result += f"\n**Segmento familiar:** {segmento_label}"
```

This line only appears when:
1. `segment_data.is_loaded() == True`
2. `lookup_by_documento()` returns non-None
3. The returned dict has a non-None `segmento`

### 3.4 Modified Chat Flow (`backend/app/services/chat.py`)

#### 3.4.1 Profile Pre-Seed on Documento Resolution

When Anna calls `get_customer(documento)` and the customer is found, the ChatService shall pre-seed `insurance_profile` with category + segment from SegmentDataService.

**Where to hook**: After `get_customer()` tool execution in the Phase 1 → Phase 2 loop. The simplest approach: in `_update_session_state()`, after detecting `get_customer` was called, look up the documento from the tool arguments and pre-seed.

However, this is fragile. Better approach: **in `domain_tools.py` itself**, when `get_customer` resolves a documento successfully, also call `segment_data.lookup_by_documento()` and include the result in the tool output. Anna (the AI) then sees the category and segmento in the text output and can naturally incorporate it.

Actually, the cleanest design: **The AI drives the profile**. `get_customer` returns enriched text (including segmento). Anna sees it and the `insurance_profile` gets populated naturally through Anna's conversation. But we want this to be automatic, not dependent on Anna deciding to save it.

So the correct hook is in `ChatService._update_session_state()`:

```python
# After detecting get_customer was called, extract documento from args,
# look up in SegmentDataService, pre-seed insurance_profile
if "get_customer" in tool_names:
    for tc in tool_calls:
        if tc.function.name == "get_customer":
            try:
                args = json.loads(tc.function.arguments)
                doc = args.get("documento_identidad")
                if doc:
                    info = segment_data.lookup_by_documento(doc)
                    if info:
                        profile = session.insurance_profile or {}
                        profile["categoria_afiliacion"] = info["categoria"]
                        profile["segmento_grupo_familiar"] = info["segmento"]
                        session.insurance_profile = profile
            except (json.JSONDecodeError, KeyError):
                pass
```

**Alternative (preferred)**: Do this in `domain_tools.py`'s `get_customer()` return. Since `get_customer` is called by the AI and its result is returned as tool output, we can also have it write to `insurance_profile`. But `domain_tools.py` doesn't have access to session state directly.

**Chosen approach**: Hook in `_update_session_state()` as shown above. It's the natural place since it already processes tool results to update session state.

#### 3.4.2 Anonymous Flow — Salary Question

New profiling instructions for Anna in the system prompt:

> **PERFILACIÓN SIN DOCUMENTO:**
> Si el usuario NO ha proporcionado su número de documento, preguntá por su rango salarial aproximado para determinar su categoría de afiliación.
> Preguntas naturales:
> - "¿En qué rango están tus ingresos mensuales aproximadamente?"
> - "¿Ganás más o menos de 3 millones y medio al mes?"
>
> Una vez tengas el salario, usá `recommend_insurance(profile)` — la función detectará `categoria_afiliacion` en el profile si se guardó con `save_form_field`.

**Integration into existing profiling instructions**: Add a section to `_build_profiling_instructions()` for the case when no documento is known. This is detected by checking `session.insurance_profile` for the absence of `categoria_afiliacion` and the absence of a linked customer.

Actually, the cleanest: the profiling instructions should guide Anna to ask for the salary range naturally during profiling. After the user responds, she calls `save_form_field(campo="salario", valor=...)` which saves it. Then `recommend_insurance` gets called with the profile containing `salario`. The engine's `_calcular_categoria()` is called internally.

Wait — looking at the spec more carefully: `_calcular_categoria(salario)` is imported from `domain_tools.py`. The recommendation engine is pure functions. So the question is: **who calls `_calcular_categoria`?**

Option A: In `recommendation_engine.py`, when `match_products_by_segment()` sees `salario` in profile but no `categoria_afiliacion`, it calls `_calcular_categoria()` itself. But this couples the engine to domain_tools.

Option B: In `domain_tools.py`'s `recommend_insurance()`, before calling `match_products_by_segment()`, check if profile has `salario` but no `categoria_afiliacion`, call `_calcular_categoria()` and inject it.

Option C: In `ChatService._update_session_state()`, when `save_form_field` saves `salario`, automatically compute categoria and save it to profile.

**Decision: Option B** — `recommend_insurance()` in `domain_tools.py` handles the salario → categoria inference. This keeps the recommendation engine pure and the logic in the tool layer where `_calcular_categoria()` already lives.

```python
def recommend_insurance(profile: dict, documento: str | None = None) -> str:
    # ... resolve categoria ...
    if not categoria and profile.get("salario"):
        categoria = _calcular_categoria(profile["salario"])

    if categoria and categoria in ("A", "B", "C"):
        products = match_products_by_segment(profile, categoria, None)
    else:
        products = match_products(profile)
    # ... format ...
```

### 3.5 Startup Integration (`backend/app/main.py`)

Add SegmentDataService initialization to the lifespan:

```python
# In lifespan(), after ToolBridge init, before ChatService init:
segment_data = SegmentDataService()
try:
    await segment_data.load()
except Exception:
    logger.warning("Segment data loading failed — running without personalization")
    segment_data = SegmentDataService()  # fresh instance, is_loaded=False
app.state.segment_data = segment_data

# Also export at module level for sync imports:
from app.services.segment_data import _set_instance
_set_instance(segment_data)
```

**Module-level singleton pattern**: Since MCP tools in `domain_tools.py` are sync functions that can't access `app.state`, we need a module-level reference:

```python
# backend/app/services/segment_data.py
_instance: "SegmentDataService | None" = None

def get_instance() -> "SegmentDataService | None":
    return _instance

def _set_instance(instance: "SegmentDataService") -> None:
    global _instance
    _instance = instance
```

Then in `domain_tools.py`:
```python
from app.services.segment_data import get_instance
segment_data = get_instance()
```

---

## 4. Decision Tree

```
                         ┌──────────────┐
                         │  recommend_  │
                         │  insurance() │
                         │  or match_   │
                         │  products_   │
                         │  by_segment()│
                         └──────┬───────┘
                                │
                    ┌───────────┴───────────┐
                    │  categoria known?     │
                    │  (A/B/C, not MU/None) │
                    └───────┬───────┬───────┘
                            │       │
                          YES      NO
                            │       │
                    ┌───────┘       └───────┐
                    │                       │
            ┌───────▼────────┐    ┌─────────▼──────────┐
            │ Apply R8-R13   │    │ Apply R1-R7 only   │
            │ compound rules  │    │ (conversational)   │
            └───────┬────────┘    └─────────┬──────────┘
                    │                       │
            ┌───────▼────────┐             │
            │ segmento known? │             │
            │ (non-None,     │             │
            │  not CHI/THETA)│             │
            └───────┬───────┘             │
                    │      │               │
                  YES     NO              │
                    │      │               │
            ┌───────┘      │               │
            │              │               │
     ┌──────▼─────┐  ┌────▼─────┐         │
     │ Apply seg  │  │ No seg   │         │
     │ weighting  │  │ modifier │         │
     │ (reorder)  │  │          │         │
     └──────┬─────┘  └────┬─────┘         │
            │             │               │
            └─────────────┘               │
                    │                     │
            ┌───────▼─────────────────────▼───┐
            │ Merge: always apply R1-R7      │
            │ as safety net (medium if no    │
            │ categoria, high if matched)    │
            │                                │
            │ Deduplicate by product_id      │
            │ Keep highest confidence        │
            │ Merge match_reason for overlap │
            └───────────────┬────────────────┘
                            │
                     ┌──────▼──────┐
                     │ Sort:       │
                     │ 1. conf desc│
                     │ 2. boosted  │
                     │    first    │
                     │ 3. prima_   │
                     │    base desc│
                     └─────────────┘
```

---

## 5. Interfaces

### 5.1 SegmentDataService Public API

| Method | Signature | Returns | Thread-safe |
|--------|-----------|---------|-------------|
| `load()` | `async () -> None` | Nothing (raises no exception on error) | N/A (called once) |
| `lookup_by_documento()` | `(documento: str) -> dict \| None` | `{categoria, segmento, consumos, prima_promedio, edad}` or None | Yes (read-only) |
| `get_aggregate_stats()` | `(categoria=None, segmento=None) -> list[dict]` | List of aggregate stats dicts | Yes (read-only) |
| `is_loaded()` | `() -> bool` | Whether CSV was loaded successfully | Yes (read-only) |

### 5.2 recommendation_engine.py New API

| Symbol | Type | Description |
|--------|------|-------------|
| `SEGMENT_RULES` | `list[tuple]` | Compound rules table (R8-R13) |
| `match_products_by_segment()` | `(profile, categoria, segmento) -> list[dict]` | Compound + conversational merge |
| `SEGMENT_BOOST` | `dict[str, list[str]]` | Segment → boosted product IDs |
| `SEGMENTO_LABELS` | `dict[str \| None, str]` | Segment code → human label |

### 5.3 domain_tools.py Modified API

| Tool | Change |
|------|--------|
| `recommend_insurance(profile, documento?)` | New optional `documento` param. Async not needed (sync lookups). |
| `load_segment_data(documento?)` | New tool. Returns formatted segment stats. |
| `get_customer(documento_identidad)` | Appends `**Segmento familiar:**` line when data available. |

### 5.4 ChatService Modified Behavior

| Hook | Change |
|------|--------|
| `_update_session_state()` | After `get_customer` tool call, pre-seed `insurance_profile.categoria_afiliacion` + `segmento_grupo_familiar` |
| `_build_profiling_instructions()` | Add salary-range question when no documento and no profile categoria |

### 5.5 Session Model (no changes)

```python
# insurance_profile JSON — extended keys:
{
    "product_context": "movilidad",       # existing: product detected at intent
    "categoria_afiliacion": "A",          # NEW: from documento lookup or salary inference
    "segmento_grupo_familiar": "LAMBDA",  # NEW: from documento lookup only (CSV)
    "salario": 2000000,                   # NEW: from anonymous flow (save_form_field)
    # ... conversational keys (familia_con_hijos, etc.) set by Anna naturally
}
```

---

## 6. Backward Compatibility

### 6.1 What Breaks When CSV Is Missing

| Component | Behavior |
|-----------|----------|
| `SegmentDataService` | `is_loaded()` = False. All queries return None/empty. |
| `recommend_insurance(profile, documento)` | Warning logged. Falls back to `match_products(profile)`. |
| `load_segment_data()` | Returns "Datos de segmentación no disponibles." |
| `get_customer()` | No segmento line appended. Existing output unchanged. |
| `ChatService` | No profile pre-seed. Anna proceeds without category. |

### 6.2 What Breaks When Document Is Not In Dataset

| Component | Behavior |
|-----------|----------|
| `lookup_by_documento(doc)` | Returns `None` |
| `recommend_insurance(profile, doc)` | Logs warning. Falls back to `match_products(profile)`. |
| `get_customer(doc)` | Existing output unchanged (no segmento line). |
| Profile pre-seed | Not done (no data to seed from). |

### 6.3 What Breaks When Categoria Is MU / Unknown

- `match_products_by_segment(profile, "MU", ...)` → No compound rules match → Falls through to R1-R7 only
- Same behavior as `categoria=None`

### 6.4 Rollback Plan

1. Revert `backend/app/services/recommendation_engine.py` — remove `SEGMENT_RULES`, `match_products_by_segment()`, `SEGMENT_BOOST`
2. Remove `backend/app/services/segment_data.py`
3. Revert `backend/app/tools/domain_tools.py` — remove `documento` param from `recommend_insurance`, remove `load_segment_data` tool, remove `get_customer` enrichment
4. Revert `backend/app/services/chat.py` — remove profile pre-seed hook
5. Revert `backend/app/main.py` — remove SegmentDataService init

All existing tests pass without changes. No data migration needed.

---

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| 500K CSV not available in repo | Medium | Low — no personalization | Graceful degradation: `is_loaded()`=False, all fallback to R1-R7 |
| CSV format doesn't match expected columns | Low | Medium — loader fails | Clear error logging with missing column names |
| Category × segment rules produce empty results | Low | Low — safety net | R1-R7 always apply as fallback |
| CSV loading slows startup (>3s) | Low | Medium — boot time | Progress logging at 100K rows. Could move to background task if needed. |
| Anonymous user refuses salary question | Medium | Low — no category | Anna doesn't push. Proceeds with R1-R7 only. |
| Segment weighting causes unexpected reorder | Low | Medium — UX confusion | Test coverage for all segment × category combinations |
| `recommend_insurance` signature change breaks existing calls | Low | High — AI tool error | Optional param with default None. Existing callers unaffected. |

---

## 8. Testing Strategy

### 8.1 Test Layers

| Layer | Location | What to Test |
|-------|----------|--------------|
| **SegmentDataService** | `tests/test_segment_data.py` | Load, lookup, aggregate, empty file, corrupt file, normalization |
| **Recommendation engine** | `tests/test_recommendation.py` | Compound rules per (cat,seg), merge logic, confidence, backward compat |
| **MCP tools** | `tests/test_domain_tools.py` | `recommend_insurance` with documento, `load_segment_data`, `get_customer` enriched |
| **Chat flow** | `tests/test_chat.py` | Profile pre-seed, anonymous salary flow |

### 8.2 Test Cases for SegmentDataService

**Unit tests** (no CSV file needed — use a test CSV fixture):

1. `test_load_success` — valid CSV → `is_loaded()=True`, documento lookup works
2. `test_lookup_found` — existing documento → returns shape with all keys
3. `test_lookup_not_found` — nonexistent documento → None
4. `test_aggregate_by_segment` — filtered aggregate stats return correct shape
5. `test_aggregate_all` — unfiltered returns sorted list
6. `test_load_file_not_found` — missing file → warning logged, `is_loaded()=False`
7. `test_load_corrupt_csv` — unparseable → warning, `is_loaded()=False`
8. `test_load_missing_columns` — missing required columns → warning, `is_loaded()=False`
9. `test_categoria_normalization` — SIGMA→A, PI→B, ZETA→C, MU→MU, unknown→MU
10. `test_empty_segmento` — empty/missing → stored as None
11. `test_concurrent_reads` — multiple coroutines reading simultaneously → no errors

### 8.3 Test Cases for Extended Engine

**Unit tests** (pure functions, no DB, no CSV needed):

1. `test_r8_a_lambda` — `match_products_by_segment({}, "A", "LAMBDA")` → vida + hogar
2. `test_r9_a_rho` — `match_products_by_segment({}, "A", "RHO")` → vida + accidentes
3. `test_r10_a_epsilon` — `match_products_by_segment({}, "A", "EPSILON")` → vida + hogar
4. `test_r11_b_any` — `match_products_by_segment({}, "B", None)` → accidentes + movilidad
5. `test_r12_c_any` — vida+hogar high, rest medium, all 6 products
6. `test_r13_any_iota` — any category + IOTA → vida + hogar
7. `test_mu_fallback` — `match_products_by_segment({}, "MU", None)` → R1-R7 only
8. `test_none_fallback` — `match_products_by_segment({}, None, None)` → R1-R7 only
9. `test_merge_conversational_wins` — product matched by both → keep conversational confidence
10. `test_segment_boost_sorting` — boosted products reorder correctly
11. `test_backward_compat_empty_profile` — `match_products_by_segment({})` → []
12. `test_existing_r1_r7_pass` — All existing test cases from `TestMatchProducts` still pass
13. `test_all_rules_table_unchanged` — `match_products` vs `match_products_by_segment` with no cat/seg → same results
14. `test_confidence_for_compound_only` — compound match with no conversational → "medium"
15. `test_confidence_for_overlap` — conversational + compound → "high"

### 8.4 Test Cases for MCP Tools

**Integration-adjacent** (sync functions, can test with mocked segment_data):

1. `test_recommend_insurance_with_documento` — mock lookup → expects category note in output
2. `test_recommend_insurance_documento_not_found` — mock returns None → falls back to existing
3. `test_recommend_insurance_no_documento` — no param → existing behavior unchanged
4. `test_recommend_insurance_salario_infer_categoria` — profile with salario → category inferred
5. `test_load_segment_data_by_documento` — returns segment-specific stats
6. `test_load_segment_data_all` — returns summary of all segments
7. `test_load_segment_data_unavailable` — `is_loaded()=False` → "no disponibles"
8. `test_get_customer_with_segmento` — customer found + segmento in dataset → segmento line present
9. `test_get_customer_without_segmento` — customer found, no segment data → no segmento line
10. `test_get_customer_no_csv` — `is_loaded()=False` → no segmento line

### 8.5 Test Cases for Chat Flow

**Integration tests** (need ChatService + mocked AI):

1. `test_profile_preseed_on_get_customer` — tool call to get_customer → categoria auto-populated
2. `test_anonymous_salary_flow` — user provides salary → categoria inferred via B
3. `test_anonymous_no_salary` — user declines salary → no categoria → R1-R7 only
4. `test_profile_preseed_from_span>documento` — multiple get_customer → correct merge

---

## 9. Implementation Order

| Step | File | Dependencies |
|------|------|--------------|
| 1 | `segment_data.py` + `test_segment_data.py` | None |
| 2 | `recommendation_engine.py` — add `SEGMENT_RULES`, `match_products_by_segment()` | Step 1 (import) |
| 3 | `tests/test_recommendation.py` — add compound rule tests | Step 2 |
| 4 | `main.py` — add SegmentDataService init to lifespan | Step 1 |
| 5 | `domain_tools.py` — `recommend_insurance` +documento, `load_segment_data` | Step 2, 4 |
| 6 | `tests/test_domain_tools.py` — MCP tool tests | Step 5 |
| 7 | `chat.py` — profile pre-seed hook, salary profiling instructions | Step 5 |
| 8 | `tests/test_chat.py` — chat flow tests | Step 7 |
| 9 | Seed data (`seed.py`) — realistic category + segment data | Step 1 |
| 10 | CSV sample/doc — header-only sample for reference | Step 1 |

---

## 10. Acceptance Criteria

- [x] **SC1**: Profile with `categoria=A, segmento_familiar=LAMBDA` → vida + hogar before viajes
- [x] **SC2**: Profile with `categoria=B, segmento_familiar=RHO` → accidentes + movilidad
- [x] **SC3**: Profile with `categoria=C` → all 6 products, vida+hogar "high"
- [x] **SC4**: Profile without categoria → R1-R7 only (backward compat)
- [x] **SC5**: Anonymous user → salary asked → `_calcular_categoria()` → personalized
- [x] **SC6**: CSV loads at startup without crash; missing file = log warning + no-op
- [x] **SC7**: All existing `test_recommendation_engine.py` tests pass unchanged
- [x] **SC8**: `match_products(profile)` unchanged — same API, same behavior
- [x] **SC9**: Documento not found in dataset → warning + fallback to existing
- [x] **SC10**: MU or None categoria → R1-R7 only, no compound rules
- [x] **SC11**: Segment boost reorders, never excludes
- [x] **SC12**: Compound rule + conversational overlap → highest confidence wins
